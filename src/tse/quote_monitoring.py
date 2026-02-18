from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import sleep as default_sleep
from typing import Callable, Literal

from kia.contracts import KiaGateway, Mode, PollQuotesRequest
from kia.contracts import MarketQuote

from .constants import (
    QUOTE_CONSECUTIVE_ERROR_THRESHOLD,
    QUOTE_POLL_INTERVAL_MS,
    QUOTE_POLL_TIMEOUT_MS,
    QUOTE_RECOVERY_SUCCESS_THRESHOLD,
)
from .models import QuoteEvent, ServiceOutput
from .service import TseService

LoopState = Literal["RUNNING", "DEGRADED", "STOPPED"]


@dataclass(frozen=True)
class QuoteMonitoringConfig:
    mode: Mode | None
    poll_interval_ms: int = QUOTE_POLL_INTERVAL_MS
    poll_timeout_ms: int = QUOTE_POLL_TIMEOUT_MS
    consecutive_error_threshold: int = QUOTE_CONSECUTIVE_ERROR_THRESHOLD
    recovery_success_threshold: int = QUOTE_RECOVERY_SUCCESS_THRESHOLD


@dataclass
class QuoteCycleResult:
    poll_cycle_id: str
    state: LoopState
    partial: bool
    quote_count: int
    error_count: int
    quotes: list[MarketQuote] = field(default_factory=list)
    outputs: list[ServiceOutput] = field(default_factory=list)
    fetch_error: str | None = None


class QuoteMonitoringLoop:
    def __init__(
        self,
        *,
        tse_service: TseService,
        kia_gateway: KiaGateway,
        config: QuoteMonitoringConfig,
        now_fn: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._tse_service = tse_service
        self._kia_gateway = kia_gateway
        self._config = config
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._sleep_fn = sleep_fn or default_sleep

        self.state: LoopState = "STOPPED"
        self._consecutive_errors = 0
        self._consecutive_success = 0
        self._cycle_seq = 0

    @property
    def poll_interval_seconds(self) -> float:
        return self._config.poll_interval_ms / 1000

    def start(self) -> None:
        self.state = "RUNNING"
        self._consecutive_errors = 0
        self._consecutive_success = 0
        self._cycle_seq = 0
        self._tse_service.set_buy_entry_blocked_by_degraded(False)

    def stop(self) -> None:
        self.state = "STOPPED"
        self._tse_service.set_buy_entry_blocked_by_degraded(False)

    def run_cycle(self) -> QuoteCycleResult:
        if self.state == "STOPPED":
            self.start()

        self._cycle_seq += 1
        now = self._now_fn()
        poll_cycle_id = f"poll-{self._tse_service.ctx.trading_date.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{self._cycle_seq:03d}"

        try:
            result = self._kia_gateway.fetch_quotes_batch(
                PollQuotesRequest(
                    mode=self._config.mode,
                    symbols=self._watch_symbols(),
                    poll_cycle_id=poll_cycle_id,
                    timeout_ms=self._config.poll_timeout_ms,
                )
            )
        except Exception as exc:
            self._on_cycle_failure()
            return QuoteCycleResult(
                poll_cycle_id=poll_cycle_id,
                state=self.state,
                partial=True,
                quote_count=0,
                error_count=1,
                quotes=[],
                outputs=[],
                fetch_error=str(exc),
            )

        outputs: list[ServiceOutput] = []
        for index, quote in enumerate(result.quotes, start=1):
            output = self._tse_service.on_quote(
                QuoteEvent(
                    trading_date=self._tse_service.ctx.trading_date,
                    occurred_at=quote.as_of,
                    symbol=quote.symbol,
                    current_price=quote.price,
                    sequence=index,
                )
            )
            outputs.append(output)

        if result.partial:
            self._on_cycle_failure()
        else:
            self._on_cycle_success()

        return QuoteCycleResult(
            poll_cycle_id=poll_cycle_id,
            state=self.state,
            partial=result.partial,
            quote_count=len(result.quotes),
            error_count=len(result.errors),
            quotes=result.quotes,
            outputs=outputs,
            fetch_error=None,
        )

    def run_forever(self, *, max_cycles: int | None = None) -> list[QuoteCycleResult]:
        if self.state == "STOPPED":
            self.start()

        cycles: list[QuoteCycleResult] = []
        while self.state in {"RUNNING", "DEGRADED"}:
            if max_cycles is not None and len(cycles) >= max_cycles:
                break
            cycles.append(self.run_cycle())
            if self.state == "STOPPED":
                break
            self._sleep_fn(self._config.poll_interval_ms / 1000)
        return cycles

    def _watch_symbols(self) -> list[str]:
        return [ctx.symbol for ctx in sorted(self._tse_service.ctx.symbols.values(), key=lambda item: item.watch_rank)]

    def _on_cycle_success(self) -> None:
        self._consecutive_errors = 0
        self._consecutive_success += 1
        if self.state == "DEGRADED" and self._consecutive_success >= self._config.recovery_success_threshold:
            self.state = "RUNNING"
            self._tse_service.set_buy_entry_blocked_by_degraded(False)

    def _on_cycle_failure(self) -> None:
        self._consecutive_success = 0
        self._consecutive_errors += 1
        if self._consecutive_errors >= self._config.consecutive_error_threshold:
            self.state = "DEGRADED"
            self._tse_service.set_buy_entry_blocked_by_degraded(True)
