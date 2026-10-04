"""Helpers shared by the signal modules. Owned by agent B (task B1)."""

from __future__ import annotations

import math
import sqlite3


def trading_days(db: sqlite3.Connection, as_of: str, n: int) -> list[str]:
    """Last ``n`` trading dates on or before ``as_of``, oldest first.

    A trading date is any date present in the ``prices`` table.
    """
    if n <= 0:
        return []
    rows = db.execute(
        "SELECT DISTINCT date FROM prices WHERE date <= ? ORDER BY date DESC LIMIT ?",
        (as_of, n),
    ).fetchall()
    return [r[0] for r in reversed(rows)]


def _is_missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def percentile_rank(
    values: dict[str, float | None], higher_is_better: bool = True
) -> dict[str, float | None]:
    """Percentile rank (0 to 1, higher is better) per key; None stays None.

    The best value gets 1.0 and the worst 0.0: ``(rank - 1) / (n - 1)`` with
    ranks starting at 1 for the worst value. Ties share the average of their
    ranks. A single present value gets 0.5. NaN is treated like None.
    """
    present = {k: float(v) for k, v in values.items() if not _is_missing(v)}
    result: dict[str, float | None] = {k: None for k in values}
    n = len(present)
    if n == 0:
        return result
    if n == 1:
        result[next(iter(present))] = 0.5
        return result

    # Ascending order of "goodness": worst first.
    sign = 1.0 if higher_is_better else -1.0
    ordered = sorted(present.items(), key=lambda kv: sign * kv[1])
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-based average rank of the tie group
        pct = (avg_rank - 1) / (n - 1)
        for k in range(i, j + 1):
            result[ordered[k][0]] = pct
        i = j + 1
    return result


def safe_div(numerator: float | None, denominator: float | None, default: float = 0.0) -> float:
    """``numerator / denominator``, or ``default`` if either is missing or the denominator is 0."""
    if _is_missing(numerator) or _is_missing(denominator) or denominator == 0:
        return default
    return numerator / denominator


def clip(value: float, lo: float, hi: float) -> float:
    """Clamp ``value`` into ``[lo, hi]``."""
    return max(lo, min(hi, value))


def sign(value: float | None) -> int:
    """-1, 0 or 1; missing values count as 0."""
    if _is_missing(value) or value == 0:
        return 0
    return 1 if value > 0 else -1


def median(values: list[float]) -> float | None:
    """Median of the non-missing values, or None if there are none."""
    clean = sorted(float(v) for v in values if not _is_missing(v))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2


def stdev(values: list[float]) -> float | None:
    """Sample standard deviation of the non-missing values; None with fewer than 2."""
    clean = [float(v) for v in values if not _is_missing(v)]
    if len(clean) < 2:
        return None
    mean = sum(clean) / len(clean)
    return math.sqrt(sum((v - mean) ** 2 for v in clean) / (len(clean) - 1))
