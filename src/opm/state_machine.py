from __future__ import annotations

from datetime import datetime

from .models import OrderAggregate, OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    "PENDING_SUBMIT": {"SUBMITTED"},
    "SUBMITTED": {"ACCEPTED", "REJECTED", "RECONCILING"},
    "ACCEPTED": {"PARTIALLY_FILLED", "FILLED", "CANCELED", "RECONCILING"},
    "PARTIALLY_FILLED": {"FILLED", "CANCELED", "RECONCILING"},
    "RECONCILING": {"ACCEPTED", "PARTIALLY_FILLED", "FILLED", "REJECTED"},
    "FILLED": set(),
    "REJECTED": set(),
    "CANCELED": set(),
}


def transition_order_status(order: OrderAggregate, next_status: OrderStatus, now: datetime) -> OrderAggregate:
    if next_status not in ALLOWED_TRANSITIONS[order.status]:
        raise ValueError(f"invalid transition: {order.status} -> {next_status}")
    order.status = next_status
    order.last_updated_at = now
    return order
