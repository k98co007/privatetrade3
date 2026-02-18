from __future__ import annotations

from datetime import date
from decimal import Decimal

from .constants import MAX_WATCH_SYMBOLS, REFERENCE_CAPTURE_TIME
from .models import (
    DailyContext,
    PlaceBuyOrderCommand,
    PlaceSellOrderCommand,
    PortfolioContext,
    PositionUpdateEvent,
    QuoteEvent,
    ServiceOutput,
    StrategyEvent,
    SymbolContext,
)
from .rules import (
    calc_drop_rate,
    calc_profit_preservation_rate,
    calc_rebound_rate,
    is_positive_price,
    should_emit_sell_signal,
    should_enter_buy_candidate,
    should_lock_min_profit,
    should_trigger_rebound_buy,
    should_update_tracked_low,
)
from .scheduler import SymbolScanScheduler


class TseService:
    def __init__(self, *, trading_date: date, watch_symbols: list[str]) -> None:
        if not 1 <= len(watch_symbols) <= MAX_WATCH_SYMBOLS:
            raise ValueError("watch_symbols size must be between 1 and 20")

        self.ctx = DailyContext(
            trading_date=trading_date,
            symbols={
                symbol: SymbolContext(symbol=symbol, watch_rank=index + 1)
                for index, symbol in enumerate(watch_symbols)
            },
            portfolio=PortfolioContext(),
        )
        self.scheduler = SymbolScanScheduler()
        self._command_sequence = 0
        self._buy_entry_blocked_by_degraded = False

    def on_day_changed(self, trading_date: date) -> None:
        watch_symbols = [ctx.symbol for ctx in sorted(self.ctx.symbols.values(), key=lambda item: item.watch_rank)]
        self.__init__(trading_date=trading_date, watch_symbols=watch_symbols)

    def set_buy_entry_blocked_by_degraded(self, blocked: bool) -> None:
        self._buy_entry_blocked_by_degraded = blocked

    @property
    def buy_entry_blocked_by_degraded(self) -> bool:
        return self._buy_entry_blocked_by_degraded

    def on_quote(self, event: QuoteEvent) -> ServiceOutput:
        output = ServiceOutput()

        if event.trading_date != self.ctx.trading_date:
            return output
        if event.symbol not in self.ctx.symbols:
            return output
        if not is_positive_price(event.current_price):
            return output
        if event.occurred_at.time() < REFERENCE_CAPTURE_TIME:
            return output

        symbol_ctx = self.ctx.symbols[event.symbol]
        symbol_ctx.last_quote_at = event.occurred_at
        symbol_ctx.last_sequence = event.sequence

        if symbol_ctx.reference_price is None:
            symbol_ctx.reference_price = event.current_price
            symbol_ctx.state = "TRACKING"
            return output

        if self._buy_entry_blocked_by_degraded:
            return output

        if self.ctx.portfolio.gate_open and self.ctx.portfolio.state == "NO_POSITION":
            self._evaluate_buy_candidate(symbol_ctx=symbol_ctx, event=event, output=output)
            self._flush_buy_candidate(event=event, output=output)

        return output

    def on_position_update(self, event: PositionUpdateEvent) -> ServiceOutput:
        output = ServiceOutput()

        if event.trading_date != self.ctx.trading_date:
            return output
        if self.ctx.portfolio.active_symbol and event.symbol != self.ctx.portfolio.active_symbol:
            return output

        if event.position_state == "BUY_REQUESTED":
            self.ctx.portfolio.state = "BUY_REQUESTED"
        elif event.position_state == "LONG_OPEN":
            self.ctx.portfolio.state = "POSITION_OPEN"
        elif event.position_state == "SELL_REQUESTED":
            self.ctx.portfolio.state = "SELL_REQUESTED"
        elif event.position_state == "CLOSED":
            self.ctx.portfolio.state = "POSITION_CLOSED"
        elif event.position_state == "BUY_FAILED":
            self.ctx.portfolio.state = "NO_POSITION"
            self.ctx.portfolio.gate_open = True
            self.ctx.portfolio.active_symbol = None

        if should_lock_min_profit(event.current_profit_rate) and not self.ctx.portfolio.min_profit_locked:
            self.ctx.portfolio.min_profit_locked = True
            output.strategy_events.append(
                StrategyEvent(
                    event_type="MIN_PROFIT_LOCKED",
                    trading_date=event.trading_date,
                    symbol=event.symbol,
                    occurred_at=event.updated_at,
                    strategy_state=self.ctx.portfolio.state,
                    metrics={"currentProfitRate": event.current_profit_rate},
                )
            )

        if should_emit_sell_signal(
            min_profit_locked=self.ctx.portfolio.min_profit_locked,
            current_profit_rate=event.current_profit_rate,
            max_profit_rate=event.max_profit_rate,
        ) and not self.ctx.portfolio.sell_signaled:
            self.ctx.portfolio.sell_signaled = True
            command = PlaceSellOrderCommand(
                command_id=self._next_command_id(event.trading_date, event.symbol, "SELL"),
                trading_date=event.trading_date,
                symbol=event.symbol,
                order_price=event.current_price,
                reason_code="TSE_PROFIT_PRESERVATION_BREAK",
            )
            output.commands.append(command)
            output.strategy_events.append(
                StrategyEvent(
                    event_type="SELL_SIGNAL",
                    trading_date=event.trading_date,
                    symbol=event.symbol,
                    occurred_at=event.updated_at,
                    strategy_state=self.ctx.portfolio.state,
                    metrics={
                        "currentProfitRate": event.current_profit_rate,
                        "maxProfitRate": event.max_profit_rate,
                        "profitPreservationRate": calc_profit_preservation_rate(
                            event.current_profit_rate,
                            event.max_profit_rate,
                        ),
                    },
                )
            )

        return output

    def _evaluate_buy_candidate(self, *, symbol_ctx: SymbolContext, event: QuoteEvent, output: ServiceOutput) -> None:
        if symbol_ctx.reference_price is None:
            return

        drop_rate = calc_drop_rate(symbol_ctx.reference_price, event.current_price)

        if symbol_ctx.state in {"TRACKING", "BUY_CANDIDATE"} and should_enter_buy_candidate(drop_rate):
            if symbol_ctx.state != "BUY_CANDIDATE":
                symbol_ctx.state = "BUY_CANDIDATE"
                symbol_ctx.tracked_low = event.current_price
                output.strategy_events.append(
                    StrategyEvent(
                        event_type="BUY_CANDIDATE_ENTERED",
                        trading_date=event.trading_date,
                        symbol=event.symbol,
                        occurred_at=event.occurred_at,
                        strategy_state=symbol_ctx.state,
                        metrics={"dropRate": drop_rate},
                    )
                )

        if symbol_ctx.state != "BUY_CANDIDATE" or symbol_ctx.tracked_low is None:
            return

        if should_update_tracked_low(event.current_price, symbol_ctx.tracked_low):
            symbol_ctx.tracked_low = event.current_price
            output.strategy_events.append(
                StrategyEvent(
                    event_type="LOCAL_LOW_UPDATED",
                    trading_date=event.trading_date,
                    symbol=event.symbol,
                    occurred_at=event.occurred_at,
                    strategy_state=symbol_ctx.state,
                    metrics={"trackedLow": symbol_ctx.tracked_low},
                )
            )

        rebound_rate = calc_rebound_rate(symbol_ctx.tracked_low, event.current_price)
        if should_trigger_rebound_buy(rebound_rate):
            self.scheduler.enqueue_candidate(
                occurred_at=event.occurred_at,
                sequence=event.sequence,
                watch_rank=symbol_ctx.watch_rank,
                symbol=event.symbol,
                current_price=event.current_price,
                rebound_rate=rebound_rate,
            )

    def _flush_buy_candidate(self, *, event: QuoteEvent, output: ServiceOutput) -> None:
        if not self.ctx.portfolio.gate_open or self.ctx.portfolio.state != "NO_POSITION":
            return

        candidate = self.scheduler.pop_next()
        if candidate is None:
            return

        symbol_ctx = self.ctx.symbols[candidate.symbol]
        if symbol_ctx.state != "BUY_CANDIDATE":
            return

        self.ctx.portfolio.gate_open = False
        self.ctx.portfolio.state = "BUY_REQUESTED"
        self.ctx.portfolio.active_symbol = candidate.symbol
        symbol_ctx.state = "BUY_TRIGGERED"

        command = PlaceBuyOrderCommand(
            command_id=self._next_command_id(event.trading_date, candidate.symbol, "BUY"),
            trading_date=event.trading_date,
            symbol=candidate.symbol,
            order_price=candidate.current_price,
            reason_code="TSE_REBOUND_BUY_SIGNAL",
        )
        output.commands.append(command)
        output.strategy_events.append(
            StrategyEvent(
                event_type="BUY_SIGNAL",
                trading_date=event.trading_date,
                symbol=candidate.symbol,
                occurred_at=candidate.key.occurred_at,
                strategy_state=symbol_ctx.state,
                metrics={"reboundRate": candidate.rebound_rate, "trackedLow": symbol_ctx.tracked_low},
            )
        )

    def _next_command_id(self, trading_date: date, symbol: str, side: str) -> str:
        self._command_sequence += 1
        return f"{trading_date.isoformat()}-{symbol}-{side}-{self._command_sequence}"
