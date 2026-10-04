"""SQLite access shared by every module. Owned by agent A."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from radar import config

SCHEMA_PATH = Path(__file__).resolve().parent / "ingest" / "schema.sql"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a database with ``row_factory = sqlite3.Row``.

    ``path`` defaults to ``data/sectors.db``. Pass ``":memory:"`` in tests.
    """
    target = str(path) if path is not None else str(config.DB_PATH)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create every table in the database contract. Safe to call repeatedly."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
