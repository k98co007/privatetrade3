from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tse.rules import (
    calc_profit_preservation_rate,
    should_emit_sell_signal,
    should_enter_buy_candidate,
    should_lock_min_profit,
    should_trigger_rebound_buy,
)
from tse.service import TseService
from tse.models import PositionUpdateEvent, QuoteEvent


def _dt(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 2, 17, hour, minute, second, tzinfo=timezone.utc)


def test_rule_thresholds_with_eps() -> None:
    assert should_enter_buy_candidate(Decimal("1.0000")) is True
    assert should_enter_buy_candidate(Decimal("0.9999")) is True
    assert should_trigger_rebound_buy(Decimal("0.2000")) is True
    assert should_trigger_rebound_buy(Decimal("0.1998")) is False
    assert should_lock_min_profit(Decimal("1.0000")) is True


def test_sell_signal_rule_and_validation() -> None:
    assert (
        should_emit_sell_signal(
            min_profit_locked=True,
            current_profit_rate=Decimal("0.80"),
            max_profit_rate=Decimal("1.00"),
        )
        is True
    )
    assert (
        should_emit_sell_signal(
            min_profit_locked=True,
            current_profit_rate=Decimal("0.81"),
            max_profit_rate=Decimal("1.00"),
        )
        is False
    )

    with pytest.raises(ValueError):
        calc_profit_preservation_rate(Decimal("0.5"), Decimal("0"))


def test_buy_transition_with_reference_drop_rebound() -> None:
    service = TseService(trading_date=date(2026, 2, 17), watch_symbols=["005930"])

    output = service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 2, 59),
            symbol="005930",
            current_price=Decimal("100.0"),
            sequence=1,
        )
    )
    assert output.commands == []

    service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 3, 0),
            symbol="005930",
            current_price=Decimal("100.0"),
            sequence=2,
        )
    )

    output = service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 0),
            symbol="005930",
            current_price=Decimal("99.0"),
            sequence=3,
        )
    )
    assert any(event.event_type == "BUY_CANDIDATE_ENTERED" for event in output.strategy_events)

    output = service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 10),
            symbol="005930",
            current_price=Decimal("99.198"),
            sequence=4,
        )
    )

    assert len(output.commands) == 1
    command = output.commands[0]
    assert command.symbol == "005930"
    assert command.reason_code == "TSE_REBOUND_BUY_SIGNAL"
    assert service.ctx.portfolio.active_symbol == "005930"
    assert service.ctx.portfolio.gate_open is False


def test_single_position_constraint_first_match_only() -> None:
    service = TseService(trading_date=date(2026, 2, 17), watch_symbols=["005930", "000660"])

    for symbol in ["005930", "000660"]:
        service.on_quote(
            QuoteEvent(
                trading_date=date(2026, 2, 17),
                occurred_at=_dt(9, 3, 0),
                symbol=symbol,
                current_price=Decimal("100.0"),
                sequence=1,
            )
        )

    service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 0),
            symbol="005930",
            current_price=Decimal("99.0"),
            sequence=5,
        )
    )
    service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 0),
            symbol="000660",
            current_price=Decimal("99.0"),
            sequence=5,
        )
    )

    first = service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 10),
            symbol="005930",
            current_price=Decimal("99.2"),
            sequence=6,
        )
    )
    second = service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 10),
            symbol="000660",
            current_price=Decimal("99.2"),
            sequence=6,
        )
    )

    assert len(first.commands) == 1
    assert first.commands[0].symbol == "005930"
    assert second.commands == []


def test_profit_lock_then_sell_signal_once() -> None:
    service = TseService(trading_date=date(2026, 2, 17), watch_symbols=["005930"])
    service.ctx.portfolio.active_symbol = "005930"
    service.ctx.portfolio.gate_open = False
    service.ctx.portfolio.state = "POSITION_OPEN"

    output = service.on_position_update(
        PositionUpdateEvent(
            trading_date=date(2026, 2, 17),
            symbol="005930",
            position_state="LONG_OPEN",
            avg_buy_price=Decimal("100.0"),
            current_price=Decimal("101.0"),
            current_profit_rate=Decimal("1.00"),
            max_profit_rate=Decimal("1.00"),
            min_profit_locked=False,
            updated_at=_dt(10, 0),
        )
    )

    assert any(event.event_type == "MIN_PROFIT_LOCKED" for event in output.strategy_events)

    output = service.on_position_update(
        PositionUpdateEvent(
            trading_date=date(2026, 2, 17),
            symbol="005930",
            position_state="LONG_OPEN",
            avg_buy_price=Decimal("100.0"),
            current_price=Decimal("100.8"),
            current_profit_rate=Decimal("0.80"),
            max_profit_rate=Decimal("1.00"),
            min_profit_locked=True,
            updated_at=_dt(10, 1),
        )
    )

    assert len(output.commands) == 1
    assert output.commands[0].reason_code == "TSE_PROFIT_PRESERVATION_BREAK"

    repeated = service.on_position_update(
        PositionUpdateEvent(
            trading_date=date(2026, 2, 17),
            symbol="005930",
            position_state="LONG_OPEN",
            avg_buy_price=Decimal("100.0"),
            current_price=Decimal("100.7"),
            current_profit_rate=Decimal("0.70"),
            max_profit_rate=Decimal("1.00"),
            min_profit_locked=True,
            updated_at=_dt(10, 2),
        )
    )
    assert repeated.commands == []


def test_watch_symbol_count_validation() -> None:
    with pytest.raises(ValueError):
        TseService(trading_date=date(2026, 2, 17), watch_symbols=[])

    symbols = [f"S{i:02d}" for i in range(21)]
    with pytest.raises(ValueError):
        TseService(trading_date=date(2026, 2, 17), watch_symbols=symbols)


def test_degraded_block_prevents_new_buy_signal() -> None:
    service = TseService(trading_date=date(2026, 2, 17), watch_symbols=["005930"])

    service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 3, 0),
            symbol="005930",
            current_price=Decimal("100.0"),
            sequence=1,
        )
    )

    service.set_buy_entry_blocked_by_degraded(True)
    dropped = service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 0),
            symbol="005930",
            current_price=Decimal("99.0"),
            sequence=2,
        )
    )
    rebounded = service.on_quote(
        QuoteEvent(
            trading_date=date(2026, 2, 17),
            occurred_at=_dt(9, 4, 10),
            symbol="005930",
            current_price=Decimal("99.2"),
            sequence=3,
        )
    )

    assert dropped.commands == []
    assert rebounded.commands == []
    assert service.ctx.symbols["005930"].state == "TRACKING"
