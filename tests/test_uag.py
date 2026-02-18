from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import time

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kia.gateway import DefaultKiaGateway
from kia.contracts import OrderResult
from tse.models import PlaceBuyOrderCommand
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
        previous_low_time=datetime(2026, 2, 17, 9, 15, 1, tzinfo=timezone.utc),
        previous_low_price=Decimal("69500"),
        buy_time=datetime(2026, 2, 17, 9, 22, 10, tzinfo=timezone.utc),
        buy_price=Decimal("70020"),
        previous_high_time=datetime(2026, 2, 17, 11, 0, 0, tzinfo=timezone.utc),
        previous_high_price=Decimal("71500"),
        sell_time=datetime(2026, 2, 17, 14, 10, 59, tzinfo=timezone.utc),
        sell_price=Decimal("71200"),
    )

    report = service.get_daily_report(date(2026, 2, 17))
    assert len(report["monitoringRows"]) == 1
    row = report["monitoringRows"][0]
    assert row["currentPrice"] == "70500"
    assert row["buyTime"] == "09:22:10"
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