"""Daily change detection for the daily brief. Owned by agent B (task B5)."""

from __future__ import annotations

import sqlite3


def diff(today: list[dict], prev: list[dict], db: sqlite3.Connection, as_of: str) -> dict:
    """``brief_daily.json`` (docs/plan.md §5) without the ``disclaimer`` key."""
    raise NotImplementedError("agent B: see docs/plan.md §6, task B5")
