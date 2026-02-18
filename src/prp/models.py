from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class StrategyEvent:
    event_id: str
    occurred_at: datetime
    trading_date: date
    symbol: str
    event_type: str
    base_price: Decimal | None = None
    local_low: Decimal | None = None
    current_price: Decimal | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class OrderEvent:
    event_id: str
    order_id: str
    occurred_at: datetime
    trading_date: date
    symbol: str
    side: str
    order_type: str
    order_price: Decimal
    quantity: int
    status: str
    client_order_key: str
    reason_code: str | None = None
    reason_message: str | None = None


@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    execution_id: str
    order_id: str
    occurred_at: datetime
    trading_date: date
    symbol: str
    side: str
    execution_price: Decimal
    execution_qty: int
    cum_qty: int
    remaining_qty: int


@dataclass(frozen=True)
class PositionSnapshot:
    snapshot_id: str
    saved_at: datetime
    trading_date: date
    symbol: str
    avg_buy_price: Decimal
    quantity: int
    current_profit_rate: Decimal
    max_profit_rate: Decimal
    min_profit_locked: bool
    last_order_id: str | None
    state_version: int


@dataclass(frozen=True)
class TradeDetail:
    id: str
    trading_date: date
    symbol: str
    buy_executed_at: datetime
    sell_executed_at: datetime
    quantity: int
    buy_price: Decimal
    sell_price: Decimal
    buy_amount: Decimal
    sell_amount: Decimal
    sell_tax: Decimal
    sell_fee: Decimal
    net_pnl: Decimal
    return_rate: Decimal


@dataclass(frozen=True)
class DailyReport:
    trading_date: date
    total_buy_amount: Decimal
    total_sell_amount: Decimal
    total_sell_tax: Decimal
    total_sell_fee: Decimal
    total_net_pnl: Decimal
    total_return_rate: Decimal
    generated_at: datetime
