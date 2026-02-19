from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kia.gateway import DefaultKiaGateway
from kia.contracts import MarketQuote, OrderResult
from tse.models import PlaceBuyOrderCommand
from tse.service import TseService
from uag.bootstrap import create_app
from uag.models import MonitoringSnapshot
from uag.service import UagService


def _create_client(tmp_path: Path) -> TestClient:
    app = create_app(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )
    return TestClient(app)


def test_settings_endpoint_contract(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    try:
        response = client.post(
            "/api/settings",
            json={
                "watchSymbols": ["005930", "000660"],
                "mode": "mock",
                "liveModeConfirmed": False,
                "credential": {
                    "appKey": "demo-key",
                    "appSecret": "demo-secret",
                    "accountNo": "1234-5678",
                    "userId": "demo-user",
                },
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["mode"] == "mock"
        assert payload["data"]["watchSymbols"] == ["005930", "000660"]
        assert "requestId" in payload
    finally:
        client.close()


def test_mode_switch_requires_live_confirmation(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    try:
        response = client.post(
            "/api/mode/switch",
            json={"targetMode": "live", "liveModeConfirmed": False},
        )

        assert response.status_code == 400
        payload = response.json()
        assert payload["success"] is False
        assert payload["error"]["code"] == "CSM_LIVE_CONFIRM_REQUIRED"
    finally:
        client.close()


def test_trading_start_contract_and_duplicate_guard(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    try:
        first = client.post("/api/trading/start", json={"tradingDate": "2026-02-17", "dryRun": True})
        assert first.status_code == 202
        first_payload = first.json()
        assert first_payload["success"] is True
        assert first_payload["data"]["engineState"] == "RUNNING"
        assert first_payload["data"]["safeMode"] is True

        second = client.post("/api/trading/start", json={"tradingDate": "2026-02-17", "dryRun": True})
        assert second.status_code == 409
        second_payload = second.json()
        assert second_payload["success"] is False
        assert second_payload["error"]["code"] == "UAG_ENGINE_ALREADY_RUNNING"
    finally:
        client.close()


def test_monitor_and_report_endpoints_contract(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    try:
        status_response = client.get("/api/monitor/status")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["success"] is True
        assert "engineState" in status_payload["data"]
        assert "mode" in status_payload["data"]
        assert "monitoringRows" in status_payload["data"]

        daily_response = client.get("/api/reports/daily?date=2026-02-17")
        assert daily_response.status_code == 200
        daily_payload = daily_response.json()
        assert daily_payload["success"] is True
        assert daily_payload["data"]["tradingDate"] == "2026-02-17"
        assert "totalNetPnl" in daily_payload["data"]
        assert "monitoringRows" in daily_payload["data"]

        trades_response = client.get("/api/reports/trades?date=2026-02-17")
        assert trades_response.status_code == 200
        trades_payload = trades_response.json()
        assert trades_payload["success"] is True
        assert trades_payload["data"]["tradingDate"] == "2026-02-17"
        assert "items" in trades_payload["data"]
        assert "monitoringRows" in trades_payload["data"]
    finally:
        client.close()


def test_ui_home_contains_auto_refresh_and_required_monitor_columns(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    try:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert "setInterval(loadStatus, 3000);" in html
        assert "종목명" in html
        assert "종목코드" in html
        assert "9시3분 가격" in html
        assert "현재 가격" in html
        assert "전저점 시간" in html
        assert "전저점 가격" in html
        assert "매수 시간" in html
        assert "매수 가격" in html
        assert "전고점 시간" in html
        assert "전고점 가격" in html
        assert "매도 시간" in html
        assert "매도 가격" in html
    finally:
        client.close()


def test_start_trading_connects_quote_monitoring_loop(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    try:
        start = client.post("/api/trading/start", json={"tradingDate": "2026-02-17", "dryRun": True})
        assert start.status_code == 202

        time.sleep(0.05)
        status = client.get("/api/monitor/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["success"] is True

        quote_monitoring = payload["data"].get("quoteMonitoring")
        assert quote_monitoring is not None
        assert quote_monitoring["loopState"] in {"RUNNING", "DEGRADED", "STOPPED"}
        assert isinstance(quote_monitoring["cyclesTotal"], int)
    finally:
        client.close()


def test_uag_executes_tse_buy_command_via_opm_and_kia(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime" / "state" / "prp.db"
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(db_path),
    )

    service._order_gateway = DefaultKiaGateway(csm_repository=service.repository)

    command = PlaceBuyOrderCommand(
        command_id="2026-02-17-005930-BUY-1",
        trading_date=date(2026, 2, 17),
        symbol="005930",
        order_price=Decimal("70000"),
        reason_code="TEST",
    )

    service._execute_tse_command(command)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT status, client_order_key
            FROM order_events
            WHERE client_order_key = ?
            ORDER BY occurred_at ASC
            """,
            (command.command_id,),
        ).fetchall()
    finally:
        conn.close()

    statuses = [row["status"] for row in rows]
    assert statuses == ["PENDING_SUBMIT", "SUBMITTED", "ACCEPTED"]


def test_uag_buy_quantity_uses_max_affordable_from_buy_budget(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime" / "state" / "prp.db"
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(db_path),
    )

    service.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "buyBudget": "210000",
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )

    service._order_gateway = DefaultKiaGateway(csm_repository=service.repository)

    command = PlaceBuyOrderCommand(
        command_id="2026-02-17-005930-BUY-2",
        trading_date=date(2026, 2, 17),
        symbol="005930",
        order_price=Decimal("70000"),
        reason_code="TEST",
    )

    service._execute_tse_command(command)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT status, quantity
            FROM order_events
            WHERE client_order_key = ?
            ORDER BY occurred_at ASC
            """,
            (command.command_id,),
        ).fetchall()
    finally:
        conn.close()

    statuses = [row["status"] for row in rows]
    quantities = [row["quantity"] for row in rows]
    assert statuses == ["PENDING_SUBMIT", "SUBMITTED", "ACCEPTED"]
    assert set(quantities) == {3}


def test_report_monitoring_rows_use_close_price_as_current_price(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )

    service.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )
    service.state.trading_date = date(2026, 2, 17)
    service.state.monitoring_snapshots["005930"] = MonitoringSnapshot(
        symbol_code="005930",
        symbol_name="005930",
        price_at_0903=Decimal("70000"),
        current_price=Decimal("71000"),
        current_price_at_close=Decimal("70500"),
        previous_low_time=datetime(2026, 2, 17, 9, 15, 1, tzinfo=timezone(timedelta(hours=9))),
        previous_low_price=Decimal("69300"),
        buy_time=datetime(2026, 2, 17, 9, 22, 10, tzinfo=timezone(timedelta(hours=9))),
        buy_price=Decimal("70020"),
        previous_high_time=datetime(2026, 2, 17, 11, 0, 0, tzinfo=timezone(timedelta(hours=9))),
        previous_high_price=Decimal("71500"),
        sell_time=datetime(2026, 2, 17, 14, 10, 59, tzinfo=timezone(timedelta(hours=9))),
        sell_price=Decimal("71200"),
    )

    report = service.get_daily_report(date(2026, 2, 17))
    assert len(report["monitoringRows"]) == 1
    row = report["monitoringRows"][0]
    assert row["currentPrice"] == "70500"
    assert row["buyTime"] == "09:22:10"
    assert row["sellTime"] == "14:10:59"
    assert row["previousLowPrice"] == "69300"
    assert row["previousHighPrice"] == "71500"


def test_monitoring_rows_hide_previous_low_and_high_when_previous_low_not_below_0903(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )

    service.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )
    service.state.trading_date = date(2026, 2, 17)
    service.state.monitoring_snapshots["005930"] = MonitoringSnapshot(
        symbol_code="005930",
        symbol_name="005930",
        price_at_0903=Decimal("70000"),
        current_price=Decimal("70500"),
        previous_low_time=datetime(2026, 2, 17, 9, 20, 0, tzinfo=timezone(timedelta(hours=9))),
        previous_low_price=Decimal("69950"),
        previous_high_time=datetime(2026, 2, 17, 10, 30, 0, tzinfo=timezone(timedelta(hours=9))),
        previous_high_price=Decimal("71000"),
    )

    status = service.monitor_status()
    row = status["monitoringRows"][0]
    assert row["priceAt0903"] == "70000"
    assert row["previousLowTime"] is None
    assert row["previousLowPrice"] is None
    assert row["previousHighTime"] is None
    assert row["previousHighPrice"] is None


def test_monitoring_rows_hide_previous_high_when_previous_low_not_bought(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )

    service.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )
    service.state.trading_date = date(2026, 2, 17)
    service.state.monitoring_snapshots["005930"] = MonitoringSnapshot(
        symbol_code="005930",
        symbol_name="005930",
        price_at_0903=Decimal("70000"),
        current_price=Decimal("70500"),
        previous_low_time=datetime(2026, 2, 17, 9, 20, 0, tzinfo=timezone(timedelta(hours=9))),
        previous_low_price=Decimal("69300"),
        previous_high_time=datetime(2026, 2, 17, 10, 30, 0, tzinfo=timezone(timedelta(hours=9))),
        previous_high_price=Decimal("71000"),
    )

    status = service.monitor_status()
    row = status["monitoringRows"][0]
    assert row["priceAt0903"] == "70000"
    assert row["previousLowTime"] == "09:20:00"
    assert row["previousLowPrice"] == "69300"
    assert row["buyTime"] is None
    assert row["buyPrice"] is None
    assert row["previousHighTime"] is None
    assert row["previousHighPrice"] is None


def test_monitoring_rows_hide_previous_high_when_before_buy_time_or_below_min_profit(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )

    service.save_settings(
        {
            "watchSymbols": ["005930", "000660"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )
    service.state.trading_date = date(2026, 2, 17)
    kst = timezone(timedelta(hours=9))

    service.state.monitoring_snapshots["005930"] = MonitoringSnapshot(
        symbol_code="005930",
        symbol_name="005930",
        price_at_0903=Decimal("100"),
        current_price=Decimal("101.5"),
        previous_low_time=datetime(2026, 2, 17, 9, 10, 0, tzinfo=kst),
        previous_low_price=Decimal("98.0"),
        buy_time=datetime(2026, 2, 17, 9, 20, 0, tzinfo=kst),
        buy_price=Decimal("100"),
        previous_high_time=datetime(2026, 2, 17, 9, 19, 59, tzinfo=kst),
        previous_high_price=Decimal("101.5"),
    )
    service.state.monitoring_snapshots["000660"] = MonitoringSnapshot(
        symbol_code="000660",
        symbol_name="000660",
        price_at_0903=Decimal("100"),
        current_price=Decimal("100.9"),
        previous_low_time=datetime(2026, 2, 17, 9, 10, 0, tzinfo=kst),
        previous_low_price=Decimal("98.0"),
        buy_time=datetime(2026, 2, 17, 9, 20, 0, tzinfo=kst),
        buy_price=Decimal("100"),
        previous_high_time=datetime(2026, 2, 17, 9, 21, 0, tzinfo=kst),
        previous_high_price=Decimal("100.9"),
    )

    status = service.monitor_status()
    by_symbol = {row["symbolCode"]: row for row in status["monitoringRows"]}

    assert by_symbol["005930"]["previousHighTime"] is None
    assert by_symbol["005930"]["previousHighPrice"] is None
    assert by_symbol["000660"]["previousHighTime"] is None
    assert by_symbol["000660"]["previousHighPrice"] is None


def test_update_monitoring_snapshots_tracks_previous_high_only_after_buy_and_plus_one_percent(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )

    kst = timezone(timedelta(hours=9))

    pre_buy_cycle = SimpleNamespace(
        quotes=[
            MarketQuote(
                symbol="005930",
                symbol_name="삼성전자",
                price=Decimal("105"),
                tick_size=1,
                as_of=datetime(2026, 2, 17, 9, 10, 0, tzinfo=kst),
            )
        ],
        outputs=[],
    )
    service._update_monitoring_snapshots(pre_buy_cycle)
    snapshot = service.state.monitoring_snapshots["005930"]
    assert snapshot.previous_high_price is None

    buy_signal_time = datetime(2026, 2, 17, 9, 20, 0, tzinfo=kst)
    buy_cycle = SimpleNamespace(
        quotes=[],
        outputs=[
            SimpleNamespace(
                strategy_events=[
                    SimpleNamespace(
                        event_type="BUY_SIGNAL",
                        symbol="005930",
                        occurred_at=buy_signal_time,
                    )
                ],
                commands=[
                    PlaceBuyOrderCommand(
                        command_id="2026-02-17-005930-BUY-1",
                        trading_date=date(2026, 2, 17),
                        symbol="005930",
                        order_price=Decimal("100"),
                        reason_code="TEST",
                    )
                ],
            )
        ],
    )
    service._update_monitoring_snapshots(buy_cycle)
    snapshot = service.state.monitoring_snapshots["005930"]
    assert snapshot.buy_time == buy_signal_time
    assert snapshot.buy_price == Decimal("100")
    assert snapshot.previous_high_time is None
    assert snapshot.previous_high_price is None

    below_threshold_cycle = SimpleNamespace(
        quotes=[
            MarketQuote(
                symbol="005930",
                symbol_name="삼성전자",
                price=Decimal("100.9"),
                tick_size=1,
                as_of=datetime(2026, 2, 17, 9, 21, 0, tzinfo=kst),
            )
        ],
        outputs=[],
    )
    service._update_monitoring_snapshots(below_threshold_cycle)
    snapshot = service.state.monitoring_snapshots["005930"]
    assert snapshot.previous_high_time is None
    assert snapshot.previous_high_price is None

    valid_cycle = SimpleNamespace(
        quotes=[
            MarketQuote(
                symbol="005930",
                symbol_name="삼성전자",
                price=Decimal("101.0"),
                tick_size=1,
                as_of=datetime(2026, 2, 17, 9, 22, 0, tzinfo=kst),
            )
        ],
        outputs=[],
    )
    service._update_monitoring_snapshots(valid_cycle)
    snapshot = service.state.monitoring_snapshots["005930"]
    assert snapshot.previous_high_time == datetime(2026, 2, 17, 9, 22, 0, tzinfo=kst)
    assert snapshot.previous_high_price == Decimal("101.0")


def test_update_monitoring_snapshots_does_not_update_previous_low_after_buy(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
        monitoring_state_path=str(tmp_path / "runtime" / "state" / "uag_monitoring_state.json"),
    )

    kst = timezone(timedelta(hours=9))
    first_low_time = datetime(2026, 2, 17, 9, 10, 0, tzinfo=kst)

    pre_buy_cycle = SimpleNamespace(
        quotes=[
            MarketQuote(
                symbol="005930",
                symbol_name="삼성전자",
                price=Decimal("100"),
                tick_size=1,
                as_of=first_low_time,
            )
        ],
        outputs=[],
    )
    service._update_monitoring_snapshots(pre_buy_cycle)

    buy_signal_time = datetime(2026, 2, 17, 9, 20, 0, tzinfo=kst)
    buy_cycle = SimpleNamespace(
        quotes=[],
        outputs=[
            SimpleNamespace(
                strategy_events=[
                    SimpleNamespace(
                        event_type="BUY_SIGNAL",
                        symbol="005930",
                        occurred_at=buy_signal_time,
                    )
                ],
                commands=[
                    PlaceBuyOrderCommand(
                        command_id="2026-02-17-005930-BUY-LOW-FREEZE",
                        trading_date=date(2026, 2, 17),
                        symbol="005930",
                        order_price=Decimal("101"),
                        reason_code="TEST",
                    )
                ],
            )
        ],
    )
    service._update_monitoring_snapshots(buy_cycle)

    post_buy_lower_quote_cycle = SimpleNamespace(
        quotes=[
            MarketQuote(
                symbol="005930",
                symbol_name="삼성전자",
                price=Decimal("99"),
                tick_size=1,
                as_of=datetime(2026, 2, 17, 9, 25, 0, tzinfo=kst),
            )
        ],
        outputs=[],
    )
    service._update_monitoring_snapshots(post_buy_lower_quote_cycle)

    snapshot = service.state.monitoring_snapshots["005930"]
    assert snapshot.buy_time == buy_signal_time
    assert snapshot.previous_low_price == Decimal("100")
    assert snapshot.previous_low_time == first_low_time


def test_monitoring_rows_use_symbol_name_from_quote_metadata(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )

    cycle = SimpleNamespace(
        quotes=[
            MarketQuote(
                symbol="005930",
                symbol_name="삼성전자",
                price=Decimal("70000"),
                tick_size=1,
                as_of=datetime(2026, 2, 17, 9, 4, 0, tzinfo=timezone(timedelta(hours=9))),
            )
        ],
        outputs=[],
    )

    service._update_monitoring_snapshots(cycle)
    status = service.monitor_status()
    assert status["monitoringRows"][0]["symbolCode"] == "005930"
    assert status["monitoringRows"][0]["symbolName"] == "삼성전자"


def test_report_monitoring_rows_render_hms_in_kst_even_when_snapshot_is_utc(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
    )

    service.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )
    service.state.trading_date = date(2026, 2, 17)
    service.state.monitoring_snapshots["005930"] = MonitoringSnapshot(
        symbol_code="005930",
        symbol_name="005930",
        price_at_0903=Decimal("100"),
        previous_low_time=datetime(2026, 2, 17, 0, 0, 1, tzinfo=timezone.utc),
        previous_low_price=Decimal("99"),
        buy_time=datetime(2026, 2, 17, 0, 22, 10, tzinfo=timezone.utc),
        buy_price=Decimal("100"),
        previous_high_time=datetime(2026, 2, 17, 2, 0, 0, tzinfo=timezone.utc),
        previous_high_price=Decimal("101"),
        sell_time=datetime(2026, 2, 17, 5, 10, 59, tzinfo=timezone.utc),
    )

    report = service.get_daily_report(date(2026, 2, 17))
    row = report["monitoringRows"][0]
    assert row["previousLowTime"] == "09:00:01"
    assert row["buyTime"] == "09:22:10"
    assert row["previousHighTime"] == "11:00:00"
    assert row["sellTime"] == "14:10:59"


def test_uag_buy_order_attempt_still_occurs_when_gateway_rejects(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime" / "state" / "prp.db"
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(db_path),
    )

    class _RejectGateway:
        def __init__(self) -> None:
            self.called = 0

        def submit_order(self, _req):
            self.called += 1
            return OrderResult(
                broker_order_id="rej-1",
                client_order_id="buy-reject",
                status="REJECTED",
                accepted_at=None,
            )

    reject_gateway = _RejectGateway()
    service._order_gateway = reject_gateway  # type: ignore[assignment]

    command = PlaceBuyOrderCommand(
        command_id="buy-reject",
        trading_date=date(2026, 2, 17),
        symbol="005930",
        order_price=Decimal("70000"),
        reason_code="TEST",
    )
    service._execute_tse_command(command)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT status
            FROM order_events
            WHERE client_order_key = ?
            ORDER BY occurred_at ASC
            """,
            (command.command_id,),
        ).fetchall()
    finally:
        conn.close()

    assert reject_gateway.called == 1
    statuses = [row["status"] for row in rows]
    assert statuses == ["PENDING_SUBMIT", "SUBMITTED", "REJECTED"]


def test_monitoring_rows_persist_across_service_restart_for_same_day(tmp_path: Path) -> None:
    trading_date = date.today()
    settings_path = tmp_path / "runtime" / "config" / "settings.local.json"
    credentials_path = tmp_path / "runtime" / "config" / "credentials.local.json"
    prp_db_path = tmp_path / "runtime" / "state" / "prp.db"
    monitoring_state_path = tmp_path / "runtime" / "state" / "uag_monitoring_state.json"

    first = UagService(
        settings_path=str(settings_path),
        credentials_path=str(credentials_path),
        prp_db_path=str(prp_db_path),
        monitoring_state_path=str(monitoring_state_path),
    )
    first.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )
    first.state.trading_date = trading_date
    first.state.monitoring_snapshots["005930"] = MonitoringSnapshot(
        symbol_code="005930",
        symbol_name="005930",
        price_at_0903=Decimal("70000"),
        current_price=Decimal("71000"),
        previous_low_time=datetime.now(tz=timezone.utc),
        previous_low_price=Decimal("69900"),
    )
    first._persist_monitoring_state()

    second = UagService(
        settings_path=str(settings_path),
        credentials_path=str(credentials_path),
        prp_db_path=str(prp_db_path),
        monitoring_state_path=str(monitoring_state_path),
    )
    status = second.monitor_status()
    assert status["tradingDate"] == trading_date.isoformat()
    assert len(status["monitoringRows"]) == 1
    assert status["monitoringRows"][0]["symbolCode"] == "005930"
    assert status["monitoringRows"][0]["currentPrice"] == "71000"


def test_monitoring_rows_stale_day_is_not_restored_on_restart(tmp_path: Path) -> None:
    settings_path = tmp_path / "runtime" / "config" / "settings.local.json"
    credentials_path = tmp_path / "runtime" / "config" / "credentials.local.json"
    prp_db_path = tmp_path / "runtime" / "state" / "prp.db"
    monitoring_state_path = tmp_path / "runtime" / "state" / "uag_monitoring_state.json"

    first = UagService(
        settings_path=str(settings_path),
        credentials_path=str(credentials_path),
        prp_db_path=str(prp_db_path),
        monitoring_state_path=str(monitoring_state_path),
    )
    first.save_settings(
        {
            "watchSymbols": ["005930"],
            "mode": "mock",
            "liveModeConfirmed": False,
            "credential": {
                "appKey": "A" * 16,
                "appSecret": "B" * 16,
                "accountNo": "12345678",
                "userId": "demo",
            },
        }
    )
    first.state.trading_date = date.today() - timedelta(days=1)
    first.state.monitoring_snapshots["005930"] = MonitoringSnapshot(
        symbol_code="005930",
        symbol_name="005930",
        current_price=Decimal("71000"),
    )
    first._persist_monitoring_state()

    second = UagService(
        settings_path=str(settings_path),
        credentials_path=str(credentials_path),
        prp_db_path=str(prp_db_path),
        monitoring_state_path=str(monitoring_state_path),
    )
    status = second.monitor_status()
    assert status["tradingDate"] is None
    assert len(status["monitoringRows"]) == 1
    assert status["monitoringRows"][0]["currentPrice"] is None
    assert monitoring_state_path.exists() is False


def test_initialize_reference_prices_backfills_0903_when_started_after_reference_time(tmp_path: Path) -> None:
    service = UagService(
        settings_path=str(tmp_path / "runtime" / "config" / "settings.local.json"),
        credentials_path=str(tmp_path / "runtime" / "config" / "credentials.local.json"),
        prp_db_path=str(tmp_path / "runtime" / "state" / "prp.db"),
        monitoring_state_path=str(tmp_path / "runtime" / "state" / "uag_monitoring_state.json"),
    )
    service.state.trading_date = date(2026, 2, 17)

    tse_service = TseService(trading_date=date(2026, 2, 17), watch_symbols=["005930"])

    class _Gateway:
        def fetch_reference_price_0903(self, *, mode, symbol):
            assert mode == "live"
            assert symbol == "005930"
            return Decimal("70100")

    service._initialize_reference_prices(
        tse_service=tse_service,
        kia_gateway=_Gateway(),  # type: ignore[arg-type]
        mode="live",
        watch_symbols=["005930"],
        now_value=datetime(2026, 2, 17, 9, 10, 0, tzinfo=timezone(timedelta(hours=9))),
    )

    snapshot = service.state.monitoring_snapshots["005930"]
    assert snapshot.price_at_0903 == Decimal("70100")
    assert tse_service.ctx.symbols["005930"].reference_price == Decimal("70100")
    assert tse_service.ctx.symbols["005930"].state == "TRACKING"