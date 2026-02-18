from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from .models import DailyReport, ExecutionEvent, TradeDetail

SELL_TAX_RATE = Decimal("0.002")
SELL_FEE_RATE = Decimal("0.00011")
AMOUNT_Q = Decimal("0.01")
RETURN_Q = Decimal("0.0001")


def q_amount(value: Decimal) -> Decimal:
    return value.quantize(AMOUNT_Q, rounding=ROUND_HALF_UP)


def q_return(value: Decimal) -> Decimal:
    return value.quantize(RETURN_Q, rounding=ROUND_HALF_UP)


def calc_buy_amount(buy_price: Decimal, quantity: int) -> Decimal:
    return q_amount(buy_price * Decimal(quantity))


def calc_sell_amount(sell_price: Decimal, quantity: int) -> Decimal:
    return q_amount(sell_price * Decimal(quantity))


def calc_sell_tax(sell_amount: Decimal) -> Decimal:
    return q_amount(sell_amount * SELL_TAX_RATE)


def calc_sell_fee(sell_amount: Decimal) -> Decimal:
    return q_amount(sell_amount * SELL_FEE_RATE)


def calc_net_pnl(buy_amount: Decimal, sell_amount: Decimal, sell_tax: Decimal, sell_fee: Decimal) -> Decimal:
    return q_amount(sell_amount - buy_amount - sell_tax - sell_fee)


def calc_return_rate(net_pnl: Decimal, buy_amount: Decimal) -> Decimal:
    if buy_amount == Decimal("0"):
        return Decimal("0.0000")
    return q_return((net_pnl / buy_amount) * Decimal("100"))


def calc_trade_detail(buy_price: Decimal, sell_price: Decimal, quantity: int) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    buy_amount = calc_buy_amount(buy_price, quantity)
    sell_amount = calc_sell_amount(sell_price, quantity)
    sell_tax = calc_sell_tax(sell_amount)
    sell_fee = calc_sell_fee(sell_amount)
    net_pnl = calc_net_pnl(buy_amount, sell_amount, sell_tax, sell_fee)
    return_rate = calc_return_rate(net_pnl, buy_amount)
    return buy_amount, sell_amount, sell_tax, sell_fee, net_pnl, return_rate


def build_trade_details(executions: list[ExecutionEvent]) -> list[TradeDetail]:
    sorted_events = sorted(executions, key=lambda event: (event.occurred_at, event.event_id))
    buy_queues: dict[str, deque[dict[str, object]]] = defaultdict(deque)
    trade_details: list[TradeDetail] = []

    for event in sorted_events:
        side = event.side.upper()
        if side == "BUY":
            buy_queues[event.symbol].append(
                {
                    "occurred_at": event.occurred_at,
                    "price": event.execution_price,
                    "remaining_qty": event.execution_qty,
                }
            )
            continue

        if side != "SELL":
            continue

        remaining_sell_qty = event.execution_qty
        queue = buy_queues[event.symbol]
        part = 0

        while remaining_sell_qty > 0 and queue:
            buy_lot = queue[0]
            buy_remaining = int(buy_lot["remaining_qty"])
            matched_qty = min(buy_remaining, remaining_sell_qty)
            buy_price = Decimal(str(buy_lot["price"]))
            buy_time = buy_lot["occurred_at"]

            buy_amount, sell_amount, sell_tax, sell_fee, net_pnl, return_rate = calc_trade_detail(
                buy_price=buy_price,
                sell_price=event.execution_price,
                quantity=matched_qty,
            )
            detail_id = f"{event.execution_id}-{part}"
            trade_details.append(
                TradeDetail(
                    id=detail_id,
                    trading_date=event.trading_date,
                    symbol=event.symbol,
                    buy_executed_at=buy_time,
                    sell_executed_at=event.occurred_at,
                    quantity=matched_qty,
                    buy_price=buy_price,
                    sell_price=event.execution_price,
                    buy_amount=buy_amount,
                    sell_amount=sell_amount,
                    sell_tax=sell_tax,
                    sell_fee=sell_fee,
                    net_pnl=net_pnl,
                    return_rate=return_rate,
                )
            )

            buy_lot["remaining_qty"] = buy_remaining - matched_qty
            if int(buy_lot["remaining_qty"]) <= 0:
                queue.popleft()

            remaining_sell_qty -= matched_qty
            part += 1

    return trade_details


def aggregate_daily_report(trade_details: list[TradeDetail], trading_date) -> DailyReport:
    total_buy_amount = q_amount(sum((detail.buy_amount for detail in trade_details), Decimal("0")))
    total_sell_amount = q_amount(sum((detail.sell_amount for detail in trade_details), Decimal("0")))
    total_sell_tax = q_amount(sum((detail.sell_tax for detail in trade_details), Decimal("0")))
    total_sell_fee = q_amount(sum((detail.sell_fee for detail in trade_details), Decimal("0")))
    total_net_pnl = q_amount(sum((detail.net_pnl for detail in trade_details), Decimal("0")))

    if total_buy_amount == Decimal("0"):
        total_return_rate = Decimal("0.0000")
    else:
        total_return_rate = q_return((total_net_pnl / total_buy_amount) * Decimal("100"))

    return DailyReport(
        trading_date=trading_date,
        total_buy_amount=total_buy_amount,
        total_sell_amount=total_sell_amount,
        total_sell_tax=total_sell_tax,
        total_sell_fee=total_sell_fee,
        total_net_pnl=total_net_pnl,
        total_return_rate=total_return_rate,
        generated_at=datetime.now(timezone.utc),
    )


def generate_daily_report(executions: list[ExecutionEvent], trading_date) -> tuple[list[TradeDetail], DailyReport]:
    details = build_trade_details([event for event in executions if event.trading_date == trading_date])
    report = aggregate_daily_report(details, trading_date)
    return details, report
