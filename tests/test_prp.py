from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prp.bootstrap import run_migrations
from prp.models import ExecutionEvent, PositionSnapshot
from prp.repository import PrpRepository


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 2, 17, hour, minute, tzinfo=timezone.utc)


def create_repo() -> PrpRepository:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return PrpRepository(conn=conn)


def test_schema_and_execution_idempotency() -> None:
    repo = create_repo()
    try:
        first = repo.append_execution_event(
            ExecutionEvent(
                event_id="evt-1",
                execution_id="exe-1",
                order_id="ord-1",
                occurred_at=_dt(9),
                trading_date=date(2026, 2, 17),
                symbol="005930",
                side="BUY",
                execution_price=Decimal("10000"),
                execution_qty=10,
                cum_qty=10,
                remaining_qty=0,
            )
        )
        second = repo.append_execution_event(
            ExecutionEvent(
                event_id="evt-2",
                execution_id="exe-1",
                order_id="ord-2",
                occurred_at=_dt(9, 1),
                trading_date=date(2026, 2, 17),
                symbol="005930",
                side="BUY",
                execution_price=Decimal("10020"),
                execution_qty=10,
                cum_qty=10,
                remaining_qty=0,
            )
        )

        assert first is True
        assert second is False
        assert repo.exists_execution("exe-1") is True
    finally:
        repo.close()


def test_snapshot_save_and_load_latest() -> None:
    repo = create_repo()
    try:
        trading_date = date(2026, 2, 17)

        repo.save_state_snapshot(
            PositionSnapshot(
                snapshot_id="snap-1",
                saved_at=_dt(10, 0),
                trading_date=trading_date,
                symbol="005930",
                avg_buy_price=Decimal("10000"),
                quantity=10,
                current_profit_rate=Decimal("0.5000"),
                max_profit_rate=Decimal("0.9000"),
                min_profit_locked=False,
                last_order_id="ord-1",
                state_version=1,
            )
        )
        repo.save_state_snapshot(
            PositionSnapshot(
                snapshot_id="snap-2",
                saved_at=_dt(10, 5),
                trading_date=trading_date,
                symbol="005930",
                avg_buy_price=Decimal("10000"),
                quantity=8,
                current_profit_rate=Decimal("0.7000"),
                max_profit_rate=Decimal("1.2000"),
                min_profit_locked=True,
                last_order_id="ord-2",
                state_version=2,
            )
        )

        latest = repo.load_latest_state_snapshot(trading_date)
        assert latest is not None
        assert latest.snapshot_id == "snap-2"
        assert latest.min_profit_locked is True
        assert latest.quantity == 8
    finally:
        repo.close()


def test_generate_daily_report_with_tax_and_fee() -> None:
    repo = create_repo()
    try:
        trading_date = date(2026, 2, 17)

        buy_inserted = repo.append_execution_event(
            ExecutionEvent(
                event_id="evt-b1",
                execution_id="exe-b1",
                order_id="ord-b1",
                occurred_at=_dt(9, 0),
                trading_date=trading_date,
                symbol="005930",
                side="BUY",
                execution_price=Decimal("10000"),
                execution_qty=10,
                cum_qty=10,
                remaining_qty=0,
            )
        )
        sell_inserted = repo.append_execution_event(
            ExecutionEvent(
                event_id="evt-s1",
                execution_id="exe-s1",
                order_id="ord-s1",
                occurred_at=_dt(14, 30),
                trading_date=trading_date,
                symbol="005930",
                side="SELL",
                execution_price=Decimal("10100"),
                execution_qty=10,
                cum_qty=10,
                remaining_qty=0,
            )
        )

        assert buy_inserted is True
        assert sell_inserted is True

        report = repo.generate_daily_report(trading_date)

        assert report.total_buy_amount == Decimal("100000.00")
        assert report.total_sell_amount == Decimal("101000.00")
        assert report.total_sell_tax == Decimal("202.00")
        assert report.total_sell_fee == Decimal("11.11")
        assert report.total_net_pnl == Decimal("786.89")
        assert report.total_return_rate == Decimal("0.7869")

        details = repo.list_trade_details(trading_date)
        assert len(details) == 1
        assert details[0].sell_tax == Decimal("202.00")
        assert details[0].sell_fee == Decimal("11.11")
    finally:
        repo.close()
