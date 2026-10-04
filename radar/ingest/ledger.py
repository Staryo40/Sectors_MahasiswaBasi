"""Credit ledger: every request is recorded in the ``api_calls`` table."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def record(conn: sqlite3.Connection, url: str, status: int, credits: int, from_cache: bool) -> None:
    conn.execute(
        "INSERT INTO api_calls (ts, url, status, credits, from_cache) VALUES (?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), url, status, credits, int(from_cache)),
    )
    conn.commit()


def credits_spent(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(SUM(credits), 0) FROM api_calls").fetchone()
    return int(row[0])


def live_calls(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM api_calls WHERE from_cache = 0").fetchone()
    return int(row[0])
