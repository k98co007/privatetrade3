from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .constants import (
    DROP_THRESHOLD_PCT,
    EPS,
    MIN_PROFIT_LOCK_PCT,
    PCT_Q,
    PROFIT_PRESERVATION_SELL_PCT,
    REBOUND_THRESHOLD_PCT,
)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(PCT_Q, rounding=ROUND_HALF_UP)


def is_positive_price(price: Decimal) -> bool:
    return price > 0


def calc_drop_rate(base_price: Decimal, current_price: Decimal) -> Decimal:
    if base_price <= 0:
        raise ValueError("base_price must be > 0")
    return _q4((base_price - current_price) / base_price * Decimal("100"))


def calc_rebound_rate(local_low: Decimal, current_price: Decimal) -> Decimal:
    if local_low <= 0:
        raise ValueError("local_low must be > 0")
    return _q4((current_price - local_low) / local_low * Decimal("100"))


def calc_profit_preservation_rate(current_profit_rate: Decimal, max_profit_rate: Decimal) -> Decimal:
    if max_profit_rate <= 0:
        raise ValueError("max_profit_rate must be > 0")
    return _q4(current_profit_rate / max_profit_rate * Decimal("100"))


def ge_with_eps(left: Decimal, right: Decimal, eps: Decimal = EPS) -> bool:
    return left >= (right - eps)


def le_with_eps(left: Decimal, right: Decimal, eps: Decimal = EPS) -> bool:
    return left <= (right + eps)


def should_enter_buy_candidate(drop_rate: Decimal) -> bool:
    return ge_with_eps(drop_rate, DROP_THRESHOLD_PCT)


def should_update_tracked_low(current_price: Decimal, tracked_low: Decimal) -> bool:
    return current_price < tracked_low


def should_trigger_rebound_buy(rebound_rate: Decimal) -> bool:
    return ge_with_eps(rebound_rate, REBOUND_THRESHOLD_PCT)


def should_lock_min_profit(current_profit_rate: Decimal) -> bool:
    return ge_with_eps(current_profit_rate, MIN_PROFIT_LOCK_PCT)


def should_emit_sell_signal(
    *,
    min_profit_locked: bool,
    current_profit_rate: Decimal,
    max_profit_rate: Decimal,
) -> bool:
    if not min_profit_locked:
        return False
    if max_profit_rate <= 0:
        return False
    preservation = calc_profit_preservation_rate(current_profit_rate, max_profit_rate)
    return le_with_eps(preservation, PROFIT_PRESERVATION_SELL_PCT)
