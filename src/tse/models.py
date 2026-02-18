from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

SymbolState = Literal[
    "WAIT_REFERENCE",
    "TRACKING",
    "BUY_CANDIDATE",
    "BUY_TRIGGERED",
    "BUY_BLOCKED",
]

PortfolioState = Literal[
    "NO_POSITION",
    "BUY_REQUESTED",
    "POSITION_OPEN",
    "SELL_REQUESTED",
    "POSITION_CLOSED",
]


@dataclass
class SymbolContext:
    symbol: str
    watch_rank: int
    state: SymbolState = "WAIT_REFERENCE"
    reference_price: Decimal | None = None
    tracked_low: Decimal | None = None
    last_quote_at: datetime | None = None
    last_sequence: int = 0


@dataclass
class PortfolioContext:
    state: PortfolioState = "NO_POSITION"
    gate_open: bool = True
    active_symbol: str | None = None
    min_profit_locked: bool = False
    sell_signaled: bool = False


@dataclass(frozen=True)
class QuoteEvent:
    trading_date: date
    occurred_at: datetime
    symbol: str
    current_price: Decimal
    sequence: int


@dataclass(frozen=True)
class PositionUpdateEvent:
    trading_date: date
    symbol: str
    position_state: Literal["BUY_REQUESTED", "LONG_OPEN", "SELL_REQUESTED", "CLOSED", "BUY_FAILED"]
    avg_buy_price: Decimal
    current_price: Decimal
    current_profit_rate: Decimal
    max_profit_rate: Decimal
    min_profit_locked: bool
    updated_at: datetime


@dataclass(frozen=True)
class PlaceBuyOrderCommand:
    command_id: str
    trading_date: date
    symbol: str
    order_price: Decimal
    reason_code: str


@dataclass(frozen=True)
class PlaceSellOrderCommand:
    command_id: str
    trading_date: date
    symbol: str
    order_price: Decimal
    reason_code: str


@dataclass(frozen=True)
class StrategyEvent:
    event_type: str
    trading_date: date
    symbol: str
    occurred_at: datetime
    strategy_state: str
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceOutput:
    commands: list[PlaceBuyOrderCommand | PlaceSellOrderCommand] = field(default_factory=list)
    strategy_events: list[StrategyEvent] = field(default_factory=list)


@dataclass
class DailyContext:
    trading_date: date
    symbols: dict[str, SymbolContext]
    portfolio: PortfolioContext = field(default_factory=PortfolioContext)
