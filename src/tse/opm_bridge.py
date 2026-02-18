from __future__ import annotations

from datetime import datetime

from opm.models import PositionModel

from .models import PositionUpdateEvent


def map_opm_position_event(position: PositionModel, *, updated_at: datetime | None = None) -> PositionUpdateEvent:
    if position.state == "FLAT":
        mapped_state = "BUY_FAILED"
    elif position.state == "LONG_OPEN":
        mapped_state = "LONG_OPEN"
    elif position.state == "EXITING":
        mapped_state = "SELL_REQUESTED"
    elif position.state == "CLOSED":
        mapped_state = "CLOSED"
    else:
        mapped_state = "BUY_REQUESTED"

    return PositionUpdateEvent(
        trading_date=position.trading_date,
        symbol=position.symbol,
        position_state=mapped_state,
        avg_buy_price=position.avg_buy_price,
        current_price=position.current_price,
        current_profit_rate=position.current_profit_rate,
        max_profit_rate=position.max_profit_rate,
        min_profit_locked=position.min_profit_locked,
        updated_at=updated_at or position.updated_at,
    )
