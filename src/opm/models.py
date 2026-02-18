from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

Side = Literal["BUY", "SELL"]
OrderType = Literal["LIMIT"]
OrderStatus = Literal[
    "PENDING_SUBMIT",
    "SUBMITTED",
    "ACCEPTED",
    "PARTIALLY_FILLED",
    "FILLED",
    "REJECTED",
    "CANCELED",
    "RECONCILING",
]
PositionState = Literal["FLAT", "LONG_OPEN", "EXITING", "CLOSED"]


@dataclass
class OrderAggregate:
    order_aggregate_id: str
    trading_date: date
    symbol: str
    side: Side
    order_type: OrderType
    requested_price: Decimal
    requested_qty: int
    status: OrderStatus
    broker_order_id: str | None
    client_order_id: str
    cum_executed_qty: int
    avg_executed_price: Decimal
    remaining_qty: int
    last_error_code: str | None
    last_updated_at: datetime


@dataclass
class PositionModel:
    position_id: str
    trading_date: date
    symbol: str
    state: PositionState
    quantity: int
    avg_buy_price: Decimal
    buy_notional: Decimal
    sell_quantity: int
    avg_sell_price: Decimal
    sell_notional: Decimal
    current_price: Decimal
    gross_interim_pnl: Decimal
    estimated_sell_tax: Decimal
    estimated_sell_fee: Decimal
    net_interim_pnl: Decimal
    current_profit_rate: Decimal
    max_profit_rate: Decimal
    min_profit_locked: bool
    state_version: int
    updated_at: datetime


@dataclass(frozen=True)
class ExecutionFill:
    execution_id: str
    broker_order_id: str
    symbol: str
    side: Side
    price: Decimal
    qty: int
    executed_at: datetime


def create_empty_position(*, trading_date: date, symbol: str, now: datetime) -> PositionModel:
    return PositionModel(
        position_id=f"pos-{trading_date.isoformat()}-{symbol}",
        trading_date=trading_date,
        symbol=symbol,
        state="FLAT",
        quantity=0,
        avg_buy_price=Decimal("0"),
        buy_notional=Decimal("0"),
        sell_quantity=0,
        avg_sell_price=Decimal("0"),
        sell_notional=Decimal("0"),
        current_price=Decimal("0"),
        gross_interim_pnl=Decimal("0"),
        estimated_sell_tax=Decimal("0"),
        estimated_sell_fee=Decimal("0"),
        net_interim_pnl=Decimal("0"),
        current_profit_rate=Decimal("0"),
        max_profit_rate=Decimal("0"),
        min_profit_locked=False,
        state_version=0,
        updated_at=now,
    )
