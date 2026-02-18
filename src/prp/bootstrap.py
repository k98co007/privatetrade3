from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import SCHEMA_SQL, SCHEMA_VERSION

DEFAULT_DB_PATH = Path("runtime/state/prp.db")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(SCHEMA_SQL)
        row = conn.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
        current = row["version"] if row and row["version"] is not None else 0
        if current < SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, _utc_now_iso()),
            )


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    run_migrations(conn)
    return conn
