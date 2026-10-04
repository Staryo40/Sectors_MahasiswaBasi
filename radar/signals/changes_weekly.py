"""Weekly change detection for the weekly brief. Owned by agent C (task C3)."""

from __future__ import annotations

import sqlite3


def diff(now: list[dict], prev: list[dict], db: sqlite3.Connection, as_of: str) -> dict:
    """``brief_weekly.json`` (docs/plan.md §5) without the ``disclaimer`` key."""
    raise NotImplementedError("agent C: see docs/plan.md §6, task C3")
