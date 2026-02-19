from __future__ import annotations

from decimal import Decimal


def resolve_kospi_tick_size(price: Decimal) -> Decimal:
    if price < Decimal("1000"):
        return Decimal("1")
    if price < Decimal("5000"):
        return Decimal("5")
    if price < Decimal("10000"):
        return Decimal("10")
    if price < Decimal("50000"):
        return Decimal("50")
    if price < Decimal("100000"):
        return Decimal("100")
    if price < Decimal("500000"):
        return Decimal("500")
    return Decimal("1000")


def align_to_tick_down(price: Decimal, tick_size: Decimal) -> Decimal:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    units = price // tick_size
    return units * tick_size


def compute_sell_limit_price(current_price: Decimal) -> Decimal:
    tick = resolve_kospi_tick_size(current_price)
    raw_sell_price = current_price - (Decimal("2") * tick)
    sell_price = align_to_tick_down(raw_sell_price, tick)
    if sell_price <= 0:
        raise ValueError("OPM_INVALID_SELL_PRICE")
    return sell_price


def compute_buy_limit_price(current_price: Decimal, *, ticks_up: int = 2) -> Decimal:
    if current_price <= 0:
        raise ValueError("OPM_INVALID_BUY_PRICE")
    if ticks_up < 0:
        raise ValueError("ticks_up must be non-negative")

    buy_price = current_price
    for _ in range(ticks_up):
        tick = resolve_kospi_tick_size(buy_price)
        buy_price += tick

    return buy_price
