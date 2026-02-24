from __future__ import annotations

import json
import threading
import time
from pathlib import Path
import sys
from decimal import Decimal

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from csm.repository import CsmRuntimeRepository
from kia.api_client import RoutingKiaApiClient
from kia.contracts import FetchQuoteRequest, PollQuotesRequest, SubmitOrderRequest
from kia.errors import KiaError
from kia.gateway import DefaultKiaGateway


def _write_runtime_files(tmp_path: Path, *, mode: str, credential: dict) -> CsmRuntimeRepository:
    runtime = tmp_path / "runtime" / "config"
    runtime.mkdir(parents=True, exist_ok=True)

    (runtime / "settings.local.json").write_text(
        json.dumps(
            {
                "mode": mode,
                "watchSymbols": ["005930"],
                "liveModeConfirmed": mode == "live",
            }
        ),
        encoding="utf-8",
    )
    (runtime / "credentials.local.json").write_text(json.dumps({"credential": credential}), encoding="utf-8")

    return CsmRuntimeRepository(
        settings_path=str(runtime / "settings.local.json"),
        credentials_path=str(runtime / "credentials.local.json"),
    )


def test_gateway_falls_back_to_mock_when_live_credentials_missing(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "",
            "appSecret": "",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    gateway = DefaultKiaGateway(csm_repository=repo)
    quote = gateway.fetch_quote(FetchQuoteRequest(mode=None, symbol="005930"))

    assert quote.symbol == "005930"
    assert str(quote.price) == "70000"


def test_live_quote_401_triggers_single_force_refresh_and_retry(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    calls: list[tuple[str, str, dict[str, str], dict | None]] = []
    token_issue_count = 0
    quote_count = 0

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        nonlocal token_issue_count, quote_count
        calls.append((method, url, headers, payload))
        if url.endswith("/oauth2/token"):
            token_issue_count += 1
            return 200, {"token": f"token-{token_issue_count}", "expires_in": 120}
        if url.endswith("/api/dostk/mrkcond"):
            quote_count += 1
            if quote_count == 1:
                return 401, {"error": "expired"}
            return 200, {
                "symbol": payload["stk_cd"],
                "cur_prc": "70100",
                "hts_kor_isnm": "삼성전자",
                "tick_size": 1,
                "as_of": "2026-02-17T09:00:00+00:00",
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=lambda _seconds: None,
            rand_fn=lambda _a, _b: 0,
        )
    )

    quote = gateway.fetch_quote(FetchQuoteRequest(mode="live", symbol="005930"))

    assert quote.symbol == "005930"
    assert quote.symbol_name == "삼성전자"
    assert str(quote.price) == "70100"
    assert token_issue_count == 2
    assert quote_count == 2
    assert any(
        headers.get("Authorization") == "Bearer token-1" or headers.get("authorization") == "Bearer token-1"
        for _, _, headers, _ in calls
    )
    assert any(
        headers.get("Authorization") == "Bearer token-2" or headers.get("authorization") == "Bearer token-2"
        for _, _, headers, _ in calls
    )
    quote_api_ids = [headers.get("api-id") for _, url, headers, _ in calls if url.endswith("/api/dostk/mrkcond")]
    assert quote_api_ids == ["ka10007", "ka10007"]
    quote_payloads = [payload for _, url, _, payload in calls if url.endswith("/api/dostk/mrkcond")]
    assert quote_payloads == [{"stk_cd": "005930_AL"}, {"stk_cd": "005930_AL"}]


def test_live_429_is_mapped_and_retried(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )
    quote_attempts = 0

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        nonlocal quote_attempts
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/mrkcond"):
            quote_attempts += 1
            return 429, {"error": "too many requests"}
        raise AssertionError("unexpected URL")

    client = RoutingKiaApiClient(
        csm_repository=repo,
        transport=transport,
        retry_attempts=3,
        retry_base_delay_seconds=0,
        retry_max_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
        rand_fn=lambda _a, _b: 0,
    )

    with pytest.raises(KiaError) as captured:
        client.fetch_quote_raw(mode="live", symbol="005930")

    assert captured.value.code == "KIA_RATE_LIMITED"
    assert captured.value.retryable is True
    assert quote_attempts == 3


def test_fetch_quotes_batch_returns_partial_with_symbol_errors(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    quote_api_ids: list[str | None] = []

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/mrkcond"):
            quote_api_ids.append(headers.get("api-id"))
            symbol = str((payload or {}).get("stk_cd"))
            base_symbol = symbol[:-3] if symbol.endswith("_AL") else symbol
            if base_symbol == "NOT_FOUND":
                return 404, {"error": "not found"}
            return 200, {
                "symbol": base_symbol,
                "cur_prc": "70100",
                "tick_size": 1,
                "as_of": "2026-02-17T09:00:00+00:00",
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=lambda _seconds: None,
            rand_fn=lambda _a, _b: 0,
        )
    )

    result = gateway.fetch_quotes_batch(
        PollQuotesRequest(mode="live", symbols=["005930", "NOT_FOUND"], poll_cycle_id="cycle-1", timeout_ms=1000)
    )

    assert result.poll_cycle_id == "cycle-1"
    assert result.partial is True
    assert [quote.symbol for quote in result.quotes] == ["005930"]
    assert len(result.errors) == 1
    assert result.errors[0].symbol == "NOT_FOUND"
    assert result.errors[0].code == "KIA_QUOTE_SYMBOL_NOT_FOUND"
    assert result.errors[0].retryable is False
    assert quote_api_ids == ["ka10007", "ka10007"]


def test_fetch_quotes_batch_falls_back_to_request_symbol_when_missing_in_response(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/mrkcond"):
            return 200, {
                "cur_prc": "70100",
                "tick_size": 1,
                "as_of": "2026-02-17T09:00:00+00:00",
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=lambda _seconds: None,
            rand_fn=lambda _a, _b: 0,
        )
    )

    result = gateway.fetch_quotes_batch(
        PollQuotesRequest(mode="live", symbols=["005930", "000660"], poll_cycle_id="cycle-fallback", timeout_ms=1000)
    )

    assert [quote.symbol for quote in result.quotes] == ["005930", "000660"]
    assert result.partial is False


def test_fetch_quotes_batch_enforces_one_request_per_symbol_per_second(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    clock = {"now": 0.0}
    sleep_calls: list[float] = []

    def fake_monotonic() -> float:
        return clock["now"]

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock["now"] += seconds

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/mrkcond"):
            symbol = str((payload or {}).get("stk_cd"))
            return 200, {
                "symbol": symbol,
                "cur_prc": "70100",
                "tick_size": 1,
                "as_of": "2026-02-17T09:00:00+00:00",
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=fake_sleep,
            rand_fn=lambda _a, _b: 0,
            monotonic_fn=fake_monotonic,
            quote_min_interval_seconds=1.0,
        )
    )

    result = gateway.fetch_quotes_batch(
        PollQuotesRequest(mode="live", symbols=["005930", "000660", "035420"], poll_cycle_id="cycle-1s", timeout_ms=1000)
    )

    assert [quote.symbol for quote in result.quotes] == ["005930", "000660", "035420"]
    assert result.errors == []
    assert result.partial is False
    assert len(sleep_calls) == 2
    assert all(delay == pytest.approx(0.25) for delay in sleep_calls)


def test_quote_waits_while_order_request_is_in_flight(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    order_started = threading.Event()
    allow_order_finish = threading.Event()

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/ordr"):
            order_started.set()
            assert allow_order_finish.wait(timeout=1.0)
            return 200, {
                "ord_no": "ORD-1",
                "client_order_id": "CID-ORDER",
                "status": "ACCEPTED",
                "accepted_at": "2026-02-17T09:00:00+00:00",
            }
        if url.endswith("/api/dostk/mrkcond"):
            assert allow_order_finish.is_set() is True
            return 200, {
                "symbol": str((payload or {}).get("stk_cd", "005930")),
                "cur_prc": "70100",
                "tick_size": 1,
                "as_of": "2026-02-17T09:00:00+00:00",
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=lambda _seconds: None,
            rand_fn=lambda _a, _b: 0,
            quote_min_interval_seconds=0.0,
        )
    )

    order_error: list[Exception] = []
    quote_error: list[Exception] = []
    quote_done = threading.Event()

    def run_order() -> None:
        try:
            gateway.submit_order(
                SubmitOrderRequest(
                    mode="live",
                    account_no="12345678",
                    symbol="005930",
                    side="BUY",
                    order_type="LIMIT",
                    price=Decimal("70000"),
                    quantity=1,
                    client_order_id="CID-ORDER",
                )
            )
        except Exception as exc:  # pragma: no cover
            order_error.append(exc)

    def run_quote() -> None:
        try:
            gateway.fetch_quote(FetchQuoteRequest(mode="live", symbol="005930"))
            quote_done.set()
        except Exception as exc:  # pragma: no cover
            quote_error.append(exc)
            quote_done.set()

    order_thread = threading.Thread(target=run_order)
    order_thread.start()
    assert order_started.wait(timeout=1.0)

    quote_thread = threading.Thread(target=run_quote)
    quote_thread.start()

    time.sleep(0.05)

    allow_order_finish.set()

    order_thread.join(timeout=1.0)
    quote_thread.join(timeout=1.0)

    assert not order_error
    assert not quote_error
    assert quote_done.is_set() is True


def test_fetch_quotes_batch_validates_input() -> None:
    gateway = DefaultKiaGateway()

    with pytest.raises(KiaError) as empty_cycle:
        gateway.fetch_quotes_batch(PollQuotesRequest(mode="mock", symbols=["005930"], poll_cycle_id="", timeout_ms=1000))
    assert empty_cycle.value.code == "KIA_INVALID_REQUEST"

    with pytest.raises(KiaError) as too_many_symbols:
        gateway.fetch_quotes_batch(
            PollQuotesRequest(
                mode="mock",
                symbols=[f"S{index:02d}" for index in range(21)],
                poll_cycle_id="cycle-2",
                timeout_ms=1000,
            )
        )
    assert too_many_symbols.value.code == "KIA_INVALID_REQUEST"


def test_fetch_quotes_batch_timeout_or_429_retries_only_once(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )
    quote_attempts = 0
    clock = {"now": 0.0}
    sleep_calls: list[float] = []

    def fake_monotonic() -> float:
        return clock["now"]

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock["now"] += seconds

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        nonlocal quote_attempts
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/mrkcond"):
            quote_attempts += 1
            return 429, {"error": "too many requests"}
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=fake_sleep,
            rand_fn=lambda _a, _b: 0,
            monotonic_fn=fake_monotonic,
            quote_min_interval_seconds=1.0,
        )
    )

    result = gateway.fetch_quotes_batch(PollQuotesRequest(mode="live", symbols=["005930"], poll_cycle_id="cycle-r1", timeout_ms=1000))

    assert quote_attempts == 2
    assert result.partial is True
    assert result.quotes == []
    assert len(result.errors) == 1
    assert result.errors[0].code == "KIA_RATE_LIMITED"
    assert sleep_calls == [pytest.approx(1.0)]


def test_order_timeout_uses_idempotency_cache_instead_of_retrying_order(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    order_calls = 0
    timeout_on_order = False

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        nonlocal order_calls, timeout_on_order
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/ordr"):
            order_calls += 1
            if timeout_on_order:
                raise TimeoutError("simulated timeout")
            return 200, {
                "ord_no": "ORD-1",
                "client_order_id": "CID-1",
                "status": "ACCEPTED",
                "accepted_at": "2026-02-17T09:00:00+00:00",
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_attempts=3,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=lambda _seconds: None,
            rand_fn=lambda _a, _b: 0,
        )
    )

    req = SubmitOrderRequest(
        mode="live",
        account_no="12345678",
        symbol="005930",
        side="BUY",
        order_type="LIMIT",
        price=Decimal("70000"),
        quantity=1,
        client_order_id="CID-1",
    )

    first = gateway.submit_order(req)
    timeout_on_order = True
    second = gateway.submit_order(req)

    assert first.broker_order_id == "ORD-1"
    assert second.broker_order_id == "ORD-1"
    assert order_calls == 2


def test_mode_switch_invalidates_previous_mode_token_cache(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    issued = 0

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        nonlocal issued
        if url.endswith("/oauth2/token"):
            issued += 1
            return 200, {"token": f"token-{issued}", "expires_in": 120}
        if url.endswith("/api/dostk/mrkcond"):
            return 200, {
                "symbol": payload["stk_cd"],
                "cur_prc": "70100",
                "tick_size": 1,
                "as_of": "2026-02-17T09:00:00+00:00",
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=lambda _seconds: None,
            rand_fn=lambda _a, _b: 0,
        )
    )

    gateway.fetch_quote(FetchQuoteRequest(mode="live", symbol="005930"))
    gateway.fetch_quote(FetchQuoteRequest(mode="mock", symbol="005930"))
    gateway.fetch_quote(FetchQuoteRequest(mode="live", symbol="005930"))

    assert issued == 2


def test_fetch_reference_price_0830_uses_ka10080_chart_and_returns_latest_trade(tmp_path: Path) -> None:
    repo = _write_runtime_files(
        tmp_path,
        mode="live",
        credential={
            "appKey": "APPKEY",
            "appSecret": "APPSECRET",
            "liveBaseUrl": "https://live.example",
            "mockBaseUrl": "https://mock.example",
        },
    )

    captured_api_ids: list[str | None] = []
    captured_payloads: list[dict | None] = []

    def transport(method: str, url: str, headers: dict[str, str], payload: dict | None, query: dict | None, timeout: float):
        if url.endswith("/oauth2/token"):
            return 200, {"token": "token-1", "expires_in": 120}
        if url.endswith("/api/dostk/chart"):
            captured_api_ids.append(headers.get("api-id"))
            captured_payloads.append(payload)
            return 200, {
                "stk_min_pole_chart_qry": [
                    {"cntr_tm": "20260219090500", "cur_prc": "70200"},
                    {"cntr_tm": "20260219083005", "cur_prc": "70110"},
                    {"cntr_tm": "20260219083001", "cur_prc": "70100"},
                    {"cntr_tm": "20260219082959", "cur_prc": "70090"},
                ]
            }
        raise AssertionError("unexpected URL")

    gateway = DefaultKiaGateway(
        api_client=RoutingKiaApiClient(
            csm_repository=repo,
            transport=transport,
            retry_base_delay_seconds=0,
            retry_max_delay_seconds=0,
            sleep_fn=lambda _seconds: None,
            rand_fn=lambda _a, _b: 0,
        )
    )

    reference = gateway.fetch_reference_price_0830(mode="live", symbol="005930")

    assert reference == Decimal("70110")
    assert captured_api_ids == ["ka10080"]
    assert captured_payloads and captured_payloads[0] is not None
    assert captured_payloads[0]["stk_cd"] == "005930"
    assert captured_payloads[0]["tic_scope"] == "1"
    assert captured_payloads[0]["upd_stkpc_tp"] == "1"
    assert len(str(captured_payloads[0]["base_dt"])) == 8


