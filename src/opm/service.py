from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

from prp.models import ExecutionEvent, OrderEvent, PositionSnapshot

from .models import ExecutionFill, OrderAggregate, PositionModel, Side
from .state_machine import transition_order_status
from .tick_rules import compute_sell_limit_price


def _to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    if text.startswith("+"):
        text = text[1:]
    try:
        return Decimal(text)
    except Exception:
        return default


class OpmService:
    def __init__(self, prp_repository, *, kia_gateway: Any | None = None) -> None:
        self.prp_repository = prp_repository
        self.kia_gateway = kia_gateway

    def create_order(
        self,
        *,
        trading_date: date,
        symbol: str,
        side: Side,
        requested_price: Decimal,
        requested_qty: int,
        now: datetime,
        client_order_id: str | None = None,
    ) -> OrderAggregate:
        order_id = f"opm-{trading_date.isoformat()}-{symbol}-{side}-{uuid4().hex[:8]}"
        order = OrderAggregate(
            order_aggregate_id=order_id,
            trading_date=trading_date,
            symbol=symbol,
            side=side,
            order_type="LIMIT",
            requested_price=requested_price,
            requested_qty=requested_qty,
            status="PENDING_SUBMIT",
            broker_order_id=None,
            client_order_id=client_order_id or f"{trading_date.isoformat()}-{symbol}-{side}-{uuid4().hex[:6]}",
            cum_executed_qty=0,
            avg_executed_price=Decimal("0"),
            remaining_qty=requested_qty,
            last_error_code=None,
            last_updated_at=now,
        )
        self._persist_order_event(order)
        return order

    def move_order_status(
        self,
        *,
        order: OrderAggregate,
        next_status: str,
        now: datetime,
        broker_order_id: str | None = None,
        last_error_code: str | None = None,
    ) -> OrderAggregate:
        order = transition_order_status(order, next_status, now)
        if broker_order_id:
            order.broker_order_id = broker_order_id
        if last_error_code:
            order.last_error_code = last_error_code
        self._persist_order_event(order)
        return order

    def compute_sell_price(self, *, current_price: Decimal) -> Decimal:
        return compute_sell_limit_price(current_price)

    def reconcile_execution_events(
        self,
        *,
        order: OrderAggregate,
        position: PositionModel,
        fills: list[ExecutionFill],
        broker_remaining_qty: int,
        latest_market_price: Decimal,
    ) -> tuple[OrderAggregate, PositionModel, int]:
        applied_fill_count = 0

        for fill in fills:
            persisted = self.prp_repository.append_execution_event(
                ExecutionEvent(
                    event_id=f"evt-exe-{uuid4().hex[:12]}",
                    execution_id=fill.execution_id,
                    order_id=order.order_aggregate_id,
                    occurred_at=fill.executed_at,
                    trading_date=order.trading_date,
                    symbol=fill.symbol,
                    side=fill.side,
                    execution_price=fill.price,
                    execution_qty=fill.qty,
                    cum_qty=order.cum_executed_qty + fill.qty,
                    remaining_qty=max(order.requested_qty - (order.cum_executed_qty + fill.qty), 0),
                )
            )
            if not persisted:
                continue

            applied_fill_count += 1
            self._apply_fill_to_order(order=order, fill=fill)
            self._apply_fill_to_position(position=position, side=order.side, fill=fill)

        order.remaining_qty = max(broker_remaining_qty, 0)
        if order.remaining_qty == 0 and order.cum_executed_qty >= order.requested_qty:
            if order.status in {"ACCEPTED", "PARTIALLY_FILLED", "RECONCILING"}:
                order.status = "FILLED"
        elif order.cum_executed_qty > 0:
            if order.status in {"ACCEPTED", "RECONCILING"}:
                order.status = "PARTIALLY_FILLED"

        order.last_updated_at = datetime.now(order.last_updated_at.tzinfo)
        self._persist_order_event(order)

        position.current_price = latest_market_price
        self._refresh_interim_metrics(position)
        position.updated_at = datetime.now(position.updated_at.tzinfo)
        self._persist_position_snapshot(position=position, last_order_id=order.order_aggregate_id)

        return order, position, applied_fill_count

    def _apply_fill_to_order(self, *, order: OrderAggregate, fill: ExecutionFill) -> None:
        prev_qty = order.cum_executed_qty
        new_qty = prev_qty + fill.qty
        if new_qty <= 0:
            return

        total_notional = (order.avg_executed_price * Decimal(prev_qty)) + (fill.price * Decimal(fill.qty))
        order.avg_executed_price = (total_notional / Decimal(new_qty)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        order.cum_executed_qty = new_qty
        order.remaining_qty = max(order.requested_qty - order.cum_executed_qty, 0)

    def _apply_fill_to_position(self, *, position: PositionModel, side: Side, fill: ExecutionFill) -> None:
        if side == "BUY":
            prior_qty = position.quantity
            new_qty = prior_qty + fill.qty
            position.buy_notional += fill.price * Decimal(fill.qty)
            position.quantity = new_qty
            if new_qty > 0:
                position.avg_buy_price = (position.buy_notional / Decimal(new_qty)).quantize(
                    Decimal("0.0001"),
                    rounding=ROUND_HALF_UP,
                )
            position.state = "LONG_OPEN"
        else:
            fill_qty = min(fill.qty, position.quantity)
            position.sell_notional += fill.price * Decimal(fill_qty)
            position.sell_quantity += fill_qty
            position.quantity -= fill_qty
            if position.sell_quantity > 0:
                position.avg_sell_price = (position.sell_notional / Decimal(position.sell_quantity)).quantize(
                    Decimal("0.0001"),
                    rounding=ROUND_HALF_UP,
                )
            position.state = "CLOSED" if position.quantity == 0 else "EXITING"

        position.state_version += 1

    def _refresh_interim_metrics(self, position: PositionModel) -> None:
        quantity_decimal = Decimal(position.quantity)
        mark_to_market = position.current_price * quantity_decimal
        position.gross_interim_pnl = mark_to_market - (position.avg_buy_price * quantity_decimal)
        position.estimated_sell_tax = (mark_to_market * Decimal("0.002")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        position.estimated_sell_fee = (mark_to_market * Decimal("0.00011")).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        position.net_interim_pnl = position.gross_interim_pnl - position.estimated_sell_tax - position.estimated_sell_fee

        buy_notional = position.avg_buy_price * quantity_decimal
        if buy_notional > 0:
            position.current_profit_rate = ((position.net_interim_pnl / buy_notional) * Decimal("100")).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
        else:
            position.current_profit_rate = Decimal("0")

        if position.current_profit_rate > position.max_profit_rate:
            position.max_profit_rate = position.current_profit_rate
        position.min_profit_locked = position.current_profit_rate >= Decimal("1.0")

    def _persist_order_event(self, order: OrderAggregate) -> None:
        self.prp_repository.append_order_event(
            OrderEvent(
                event_id=f"evt-ord-{uuid4().hex[:12]}",
                order_id=order.order_aggregate_id,
                occurred_at=order.last_updated_at,
                trading_date=order.trading_date,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                order_price=order.requested_price,
                quantity=order.requested_qty,
                status=order.status,
                client_order_key=order.client_order_id,
                reason_code=order.last_error_code,
                reason_message=None,
            )
        )

    def _persist_position_snapshot(self, *, position: PositionModel, last_order_id: str | None) -> None:
        self.prp_repository.save_state_snapshot(
            PositionSnapshot(
                snapshot_id=f"snap-{uuid4().hex[:12]}",
                saved_at=position.updated_at,
                trading_date=position.trading_date,
                symbol=position.symbol,
                avg_buy_price=position.avg_buy_price,
                quantity=position.quantity,
                current_profit_rate=position.current_profit_rate,
                max_profit_rate=position.max_profit_rate,
                min_profit_locked=position.min_profit_locked,
                last_order_id=last_order_id,
                state_version=position.state_version,
            )
        )
