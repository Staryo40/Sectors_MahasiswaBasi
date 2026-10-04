"""Helpers shared by the signal modules. Owned by agent B (task B1)."""

from __future__ import annotations

import sqlite3


def trading_days(db: sqlite3.Connection, as_of: str, n: int) -> list[str]:
    """Last ``n`` trading dates on or before ``as_of``, oldest first.

    A trading date is any date present in the ``prices`` table.
    """
    raise NotImplementedError("agent B: see docs/plan.md §6, task B1")


def percentile_rank(
    values: dict[str, float | None], higher_is_better: bool = True
) -> dict[str, float | None]:
    """Percentile rank (0 to 1, higher is better) per key; None stays None."""
    raise NotImplementedError("agent B: see docs/plan.md §6, task B1")
