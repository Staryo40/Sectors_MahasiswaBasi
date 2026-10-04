"""Weekly/monthly horizon: investor score per stock. Owned by agent C (task C1)."""

from __future__ import annotations

import sqlite3


def compute(db: sqlite3.Connection, as_of: str) -> list[dict]:
    """One dict per stock, shaped like an ``investor.json`` entry
    (docs/plan.md §5) without ``rank_prev``, sorted by ``rank``."""
    raise NotImplementedError("agent C: see docs/plan.md §6, task C1")
