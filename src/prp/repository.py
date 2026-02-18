from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal

from .bootstrap import initialize_database
from .models import DailyReport, ExecutionEvent, OrderEvent, PositionSnapshot, StrategyEvent, TradeDetail
from .reporting import generate_daily_report


def _to_decimal(value) -> Decimal:
    return Decimal(str(value))


class PrpRepository:
    def __init__(self, conn: sqlite3.Connection | None = None, db_path: str = "runtime/state/prp.db") -> None:
        self.conn = conn or initialize_database(db_path)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "PrpRepository":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def append_strategy_event(self, event: StrategyEvent) -> None:
        payload_json = None
        if event.payload is not None:
            payload_json = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO strategy_events(
                    event_id, trading_date, occurred_at, symbol, event_type,
                    base_price, local_low, current_price, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.trading_date.isoformat(),
                    event.occurred_at.isoformat(),
                    event.symbol,
                    event.event_type,
                    str(event.base_price) if event.base_price is not None else None,
                    str(event.local_low) if event.local_low is not None else None,
                    str(event.current_price) if event.current_price is not None else None,
                    payload_json,
                ),
            )

    def append_order_event(self, event: OrderEvent) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO order_events(
                    event_id, order_id, trading_date, occurred_at, symbol, side,
                    order_type, order_price, quantity, status, client_order_key,
                    reason_code, reason_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.order_id,
                    event.trading_date.isoformat(),
                    event.occurred_at.isoformat(),
                    event.symbol,
                    event.side,
                    event.order_type,
                    str(event.order_price),
                    event.quantity,
                    event.status,
                    event.client_order_key,
                    event.reason_code,
                    event.reason_message,
                ),
            )

    def append_execution_event(self, event: ExecutionEvent) -> bool:
        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO execution_events(
                        event_id, execution_id, order_id, trading_date, occurred_at,
                        symbol, side, execution_price, execution_qty, cum_qty, remaining_qty
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.execution_id,
                        event.order_id,
                        event.trading_date.isoformat(),
                        event.occurred_at.isoformat(),
                        event.symbol,
                        event.side,
                        str(event.execution_price),
                        event.execution_qty,
                        event.cum_qty,
                        event.remaining_qty,
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def save_state_snapshot(self, snapshot: PositionSnapshot) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO position_snapshots(
                    snapshot_id, saved_at, trading_date, symbol, avg_buy_price, quantity,
                    current_profit_rate, max_profit_rate, min_profit_locked, last_order_id, state_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.saved_at.isoformat(),
                    snapshot.trading_date.isoformat(),
                    snapshot.symbol,
                    str(snapshot.avg_buy_price),
                    snapshot.quantity,
                    str(snapshot.current_profit_rate),
                    str(snapshot.max_profit_rate),
                    1 if snapshot.min_profit_locked else 0,
                    snapshot.last_order_id,
                    snapshot.state_version,
                ),
            )

    def load_latest_state_snapshot(self, trading_date: date) -> PositionSnapshot | None:
        row = self.conn.execute(
            """
            SELECT snapshot_id, saved_at, trading_date, symbol, avg_buy_price, quantity,
                   current_profit_rate, max_profit_rate, min_profit_locked, last_order_id, state_version
            FROM position_snapshots
            WHERE trading_date = ?
            ORDER BY saved_at DESC
            LIMIT 1
            """,
            (trading_date.isoformat(),),
        ).fetchone()

        if not row:
            return None

        return PositionSnapshot(
            snapshot_id=row["snapshot_id"],
            saved_at=datetime.fromisoformat(row["saved_at"]),
            trading_date=date.fromisoformat(row["trading_date"]),
            symbol=row["symbol"],
            avg_buy_price=_to_decimal(row["avg_buy_price"]),
            quantity=int(row["quantity"]),
            current_profit_rate=_to_decimal(row["current_profit_rate"]),
            max_profit_rate=_to_decimal(row["max_profit_rate"]),
            min_profit_locked=bool(row["min_profit_locked"]),
            last_order_id=row["last_order_id"],
            state_version=int(row["state_version"]),
        )

    def exists_execution(self, execution_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM execution_events WHERE execution_id = ? LIMIT 1",
            (execution_id,),
        ).fetchone()
        return row is not None

    def list_strategy_events(
        self,
        *,
        trading_date: date | None = None,
        limit: int = 50,
        event_types: list[str] | None = None,
    ) -> list[StrategyEvent]:
        safe_limit = max(1, min(limit, 500))
        clauses: list[str] = []
        args: list[object] = []

        if trading_date is not None:
            clauses.append("trading_date = ?")
            args.append(trading_date.isoformat())
        if event_types:
            placeholders = ",".join("?" for _ in event_types)
            clauses.append(f"event_type IN ({placeholders})")
            args.extend(event_types)

        where_sql = ""
        if clauses:
            where_sql = "WHERE " + " AND ".join(clauses)

        rows = self.conn.execute(
            f"""
            SELECT event_id, occurred_at, trading_date, symbol, event_type,
                   base_price, local_low, current_price, payload_json
            FROM strategy_events
            {where_sql}
            ORDER BY occurred_at DESC, event_id DESC
            LIMIT ?
            """,
            (*args, safe_limit),
        ).fetchall()

        result: list[StrategyEvent] = []
        for row in rows:
            payload = None
            payload_json = row["payload_json"]
            if payload_json:
                try:
                    parsed = json.loads(payload_json)
                    payload = parsed if isinstance(parsed, dict) else None
                except Exception:
                    payload = None

            result.append(
                StrategyEvent(
                    event_id=row["event_id"],
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    trading_date=date.fromisoformat(row["trading_date"]),
                    symbol=row["symbol"],
                    event_type=row["event_type"],
                    base_price=_to_decimal(row["base_price"]) if row["base_price"] is not None else None,
                    local_low=_to_decimal(row["local_low"]) if row["local_low"] is not None else None,
                    current_price=_to_decimal(row["current_price"]) if row["current_price"] is not None else None,
                    payload=payload,
                )
            )
        return result

    def _list_executions_for_date(self, trading_date: date) -> list[ExecutionEvent]:
        rows = self.conn.execute(
            """
            SELECT event_id, execution_id, order_id, trading_date, occurred_at, symbol,
                   side, execution_price, execution_qty, cum_qty, remaining_qty
            FROM execution_events
            WHERE trading_date = ?
            ORDER BY occurred_at ASC, event_id ASC
            """,
            (trading_date.isoformat(),),
        ).fetchall()

        executions: list[ExecutionEvent] = []
        for row in rows:
            executions.append(
                ExecutionEvent(
                    event_id=row["event_id"],
                    execution_id=row["execution_id"],
                    order_id=row["order_id"],
                    trading_date=date.fromisoformat(row["trading_date"]),
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    symbol=row["symbol"],
                    side=row["side"],
                    execution_price=_to_decimal(row["execution_price"]),
                    execution_qty=int(row["execution_qty"]),
                    cum_qty=int(row["cum_qty"]),
                    remaining_qty=int(row["remaining_qty"]),
                )
            )
        return executions

    def _upsert_trade_details(self, trading_date: date, details: list[TradeDetail]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM trade_details WHERE trading_date = ?", (trading_date.isoformat(),))
            for detail in details:
                self.conn.execute(
                    """
                    INSERT INTO trade_details(
                        id, trading_date, symbol, buy_executed_at, sell_executed_at,
                        quantity, buy_price, sell_price, buy_amount, sell_amount,
                        sell_tax, sell_fee, net_pnl, return_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        detail.id,
                        detail.trading_date.isoformat(),
                        detail.symbol,
                        detail.buy_executed_at.isoformat(),
                        detail.sell_executed_at.isoformat(),
                        detail.quantity,
                        str(detail.buy_price),
                        str(detail.sell_price),
                        str(detail.buy_amount),
                        str(detail.sell_amount),
                        str(detail.sell_tax),
                        str(detail.sell_fee),
                        str(detail.net_pnl),
                        str(detail.return_rate),
                    ),
                )

    def _upsert_daily_report(self, report: DailyReport) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO daily_reports(
                    trading_date, total_buy_amount, total_sell_amount, total_sell_tax,
                    total_sell_fee, total_net_pnl, total_return_rate, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trading_date) DO UPDATE SET
                  total_buy_amount=excluded.total_buy_amount,
                  total_sell_amount=excluded.total_sell_amount,
                  total_sell_tax=excluded.total_sell_tax,
                  total_sell_fee=excluded.total_sell_fee,
                  total_net_pnl=excluded.total_net_pnl,
                  total_return_rate=excluded.total_return_rate,
                  generated_at=excluded.generated_at
                """,
                (
                    report.trading_date.isoformat(),
                    str(report.total_buy_amount),
                    str(report.total_sell_amount),
                    str(report.total_sell_tax),
                    str(report.total_sell_fee),
                    str(report.total_net_pnl),
                    str(report.total_return_rate),
                    report.generated_at.isoformat(),
                ),
            )

    def generate_daily_report(self, trading_date: date) -> DailyReport:
        executions = self._list_executions_for_date(trading_date)
        details, report = generate_daily_report(executions, trading_date)
        self._upsert_trade_details(trading_date, details)
        self._upsert_daily_report(report)
        return report

    def list_trade_details(self, trading_date: date, symbol: str | None = None) -> list[TradeDetail]:
        if symbol:
            rows = self.conn.execute(
                """
                SELECT id, trading_date, symbol, buy_executed_at, sell_executed_at, quantity,
                       buy_price, sell_price, buy_amount, sell_amount, sell_tax,
                       sell_fee, net_pnl, return_rate
                FROM trade_details
                WHERE trading_date = ? AND symbol = ?
                ORDER BY sell_executed_at ASC, id ASC
                """,
                (trading_date.isoformat(), symbol),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT id, trading_date, symbol, buy_executed_at, sell_executed_at, quantity,
                       buy_price, sell_price, buy_amount, sell_amount, sell_tax,
                       sell_fee, net_pnl, return_rate
                FROM trade_details
                WHERE trading_date = ?
                ORDER BY sell_executed_at ASC, id ASC
                """,
                (trading_date.isoformat(),),
            ).fetchall()

        result: list[TradeDetail] = []
        for row in rows:
            result.append(
                TradeDetail(
                    id=row["id"],
                    trading_date=date.fromisoformat(row["trading_date"]),
                    symbol=row["symbol"],
                    buy_executed_at=datetime.fromisoformat(row["buy_executed_at"]),
                    sell_executed_at=datetime.fromisoformat(row["sell_executed_at"]),
                    quantity=int(row["quantity"]),
                    buy_price=_to_decimal(row["buy_price"]),
                    sell_price=_to_decimal(row["sell_price"]),
                    buy_amount=_to_decimal(row["buy_amount"]),
                    sell_amount=_to_decimal(row["sell_amount"]),
                    sell_tax=_to_decimal(row["sell_tax"]),
                    sell_fee=_to_decimal(row["sell_fee"]),
                    net_pnl=_to_decimal(row["net_pnl"]),
                    return_rate=_to_decimal(row["return_rate"]),
                )
            )
        return result
