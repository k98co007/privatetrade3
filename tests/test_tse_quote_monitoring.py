from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kia.contracts import PollQuotesRequest, PollQuotesResult, PollQuoteError, MarketQuote
from tse.quote_monitoring import QuoteMonitoringConfig, QuoteMonitoringLoop
from tse.service import TseService


class _FakeKiaGateway:
    def __init__(self, results: list[PollQuotesResult]) -> None:
        self._results = results
        self.requests: list[PollQuotesRequest] = []

    def fetch_quotes_batch(self, req: PollQuotesRequest) -> PollQuotesResult:
        self.requests.append(req)
        if not self._results:
            raise RuntimeError("no more fake results")
        return self._results.pop(0)


def _quote(symbol: str, price: str, hour: int, minute: int, second: int) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        price=Decimal(price),
        tick_size=1,
        as_of=datetime(2026, 2, 17, hour, minute, second, tzinfo=timezone.utc),
    )


def test_quote_monitor_loop_transitions_degraded_and_recovers() -> None:
    service = TseService(trading_date=date(2026, 2, 17), watch_symbols=["005930"])
    fake_gateway = _FakeKiaGateway(
        [
            PollQuotesResult(
                poll_cycle_id="c1",
                quotes=[_quote("005930", "100", 9, 3, 0)],
                errors=[PollQuoteError(symbol="005930", code="KIA_API_TIMEOUT", retryable=True)],
                partial=True,
            ),
            PollQuotesResult(
                poll_cycle_id="c2",
                quotes=[_quote("005930", "100", 9, 3, 1)],
                errors=[],
                partial=False,
            ),
        ]
    )

    loop = QuoteMonitoringLoop(
        tse_service=service,
        kia_gateway=fake_gateway,
        config=QuoteMonitoringConfig(
            mode="mock",
            consecutive_error_threshold=1,
            recovery_success_threshold=1,
        ),
        now_fn=lambda: datetime(2026, 2, 17, 9, 3, 0, tzinfo=timezone.utc),
        sleep_fn=lambda _seconds: None,
    )

    first = loop.run_cycle()
    assert first.state == "DEGRADED"
    assert service.buy_entry_blocked_by_degraded is True

    second = loop.run_cycle()
    assert second.state == "RUNNING"
    assert service.buy_entry_blocked_by_degraded is False


def test_quote_monitor_loop_uses_watch_symbols_and_generates_cycle_id() -> None:
    service = TseService(trading_date=date(2026, 2, 17), watch_symbols=["005930", "000660"])
    fake_gateway = _FakeKiaGateway(
        [
            PollQuotesResult(
                poll_cycle_id="ignored-by-fake",
                quotes=[
                    _quote("005930", "100", 9, 3, 0),
                    _quote("000660", "200", 9, 3, 0),
                ],
                errors=[],
                partial=False,
            )
        ]
    )

    loop = QuoteMonitoringLoop(
        tse_service=service,
        kia_gateway=fake_gateway,
        config=QuoteMonitoringConfig(mode="mock"),
        now_fn=lambda: datetime(2026, 2, 17, 9, 3, 5, tzinfo=timezone.utc),
        sleep_fn=lambda _seconds: None,
    )

    cycle = loop.run_cycle()

    assert cycle.poll_cycle_id == "poll-20260217-090305-001"
    assert len(fake_gateway.requests) == 1
    assert fake_gateway.requests[0].symbols == ["005930", "000660"]
    assert fake_gateway.requests[0].poll_cycle_id == "poll-20260217-090305-001"
    assert fake_gateway.requests[0].timeout_ms == 700
