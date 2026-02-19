from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opm.models import ExecutionFill, create_empty_position
from opm.service import OpmService
from opm.tick_rules import compute_buy_limit_price, compute_sell_limit_price
from prp.bootstrap import run_migrations
from prp.repository import PrpRepository


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 2, 17, hour, minute, tzinfo=timezone.utc)


def _repo() -> PrpRepository:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return PrpRepository(conn=conn)


def test_sell_price_computation_with_simplified_kospi_tick() -> None:
    assert compute_sell_limit_price(Decimal("71000")) == Decimal("70800")
    assert compute_sell_limit_price(Decimal("9980")) == Decimal("9960")


def test_buy_price_computation_with_plus_two_ticks() -> None:
    assert compute_buy_limit_price(Decimal("71000")) == Decimal("71200")
    assert compute_buy_limit_price(Decimal("4995")) == Decimal("5010")


def test_order_lifecycle_transition_guard() -> None:
    repo = _repo()
    try:
        service = OpmService(prp_repository=repo)

        order = service.create_order(
            trading_date=date(2026, 2, 17),
            symbol="005930",
            side="BUY",
            requested_price=Decimal("10000"),
            requested_qty=10,
            now=_dt(9, 0),
        )

        order = service.move_order_status(order=order, next_status="SUBMITTED", now=_dt(9, 1))
        order = service.move_order_status(order=order, next_status="ACCEPTED", now=_dt(9, 2), broker_order_id="BRK-1")
        assert order.status == "ACCEPTED"

        with pytest.raises(ValueError):
            service.move_order_status(order=order, next_status="SUBMITTED", now=_dt(9, 3))
    finally:
        repo.close()


def test_reconcile_execution_idempotency_position_tracking_and_prp_hooks() -> None:
    repo = _repo()
    try:
        service = OpmService(prp_repository=repo)
        trading_date = date(2026, 2, 17)

        buy_order = service.create_order(
            trading_date=trading_date,
            symbol="005930",
            side="BUY",
            requested_price=Decimal("10000"),
            requested_qty=10,
            now=_dt(9, 0),
        )
        buy_order = service.move_order_status(order=buy_order, next_status="SUBMITTED", now=_dt(9, 1))
        buy_order = service.move_order_status(order=buy_order, next_status="ACCEPTED", now=_dt(9, 2), broker_order_id="BRK-BUY")

        position = create_empty_position(trading_date=trading_date, symbol="005930", now=_dt(9, 0))

        buy_fill = ExecutionFill(
            execution_id="EXE-BUY-1",
            broker_order_id="BRK-BUY",
            symbol="005930",
            side="BUY",
            price=Decimal("10000"),
            qty=10,
            executed_at=_dt(9, 5),
        )

        buy_order, position, applied = service.reconcile_execution_events(
            order=buy_order,
            position=position,
            fills=[buy_fill, buy_fill],
            broker_remaining_qty=0,
            latest_market_price=Decimal("10100"),
        )
        assert applied == 1
        assert buy_order.status == "FILLED"
        assert buy_order.cum_executed_qty == 10
        assert position.quantity == 10
        assert position.state == "LONG_OPEN"
        assert repo.exists_execution("EXE-BUY-1") is True

        buy_order, position, applied_again = service.reconcile_execution_events(
            order=buy_order,
            position=position,
            fills=[buy_fill],
            broker_remaining_qty=0,
            latest_market_price=Decimal("10100"),
        )
        assert applied_again == 0

        sell_order = service.create_order(
            trading_date=trading_date,
            symbol="005930",
            side="SELL",
            requested_price=Decimal("10100"),
            requested_qty=10,
            now=_dt(10, 0),
        )
        sell_order = service.move_order_status(order=sell_order, next_status="SUBMITTED", now=_dt(10, 1))
        sell_order = service.move_order_status(order=sell_order, next_status="ACCEPTED", now=_dt(10, 2), broker_order_id="BRK-SELL")

        sell_fill = ExecutionFill(
            execution_id="EXE-SELL-1",
            broker_order_id="BRK-SELL",
            symbol="005930",
            side="SELL",
            price=Decimal("10100"),
            qty=10,
            executed_at=_dt(10, 5),
        )

        sell_order, position, sell_applied = service.reconcile_execution_events(
            order=sell_order,
            position=position,
            fills=[sell_fill],
            broker_remaining_qty=0,
            latest_market_price=Decimal("10100"),
        )
        assert sell_applied == 1
        assert sell_order.status == "FILLED"
        assert position.quantity == 0
        assert position.state == "CLOSED"
        assert position.sell_quantity == 10
        assert position.avg_sell_price == Decimal("10100.0000")

        execution_count = repo.conn.execute("SELECT COUNT(*) AS n FROM execution_events").fetchone()["n"]
        order_count = repo.conn.execute("SELECT COUNT(*) AS n FROM order_events").fetchone()["n"]
        snapshot_count = repo.conn.execute("SELECT COUNT(*) AS n FROM position_snapshots").fetchone()["n"]

        assert execution_count == 2
        assert order_count >= 6
        assert snapshot_count >= 3
    finally:
        repo.close()


