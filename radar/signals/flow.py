"""Daily horizon: flow score per stock. Owned by agent B (tasks B2, B3)."""

from __future__ import annotations

import sqlite3


def compute(db: sqlite3.Connection, as_of: str) -> list[dict]:
    """One dict per stock, shaped like a ``daily.json`` entry (docs/plan.md §5)
    without ``rank_prev`` and ``flow_score_prev``, sorted by ``rank``."""
    raise NotImplementedError("agent B: see docs/plan.md §6, task B2")


def top_brokers(db: sqlite3.Connection, symbol: str, as_of: str, n: int = 5) -> dict:
    """``{"buyers": [...], "sellers": [...]}`` as in ``stocks/{SYMBOL}.json``."""
    raise NotImplementedError("agent B: see docs/plan.md §6, task B3")


def insider_ratio(db: sqlite3.Connection, symbol: str, as_of: str, days: int = 30) -> float:
    """(buys - sells) / (buys + sells) over ``days``; 0.0 if there are none."""
    raise NotImplementedError("agent B: see docs/plan.md §6, task B3")
