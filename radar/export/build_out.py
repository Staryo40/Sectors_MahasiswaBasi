"""Writes the output files in data/out/. Owned by agent C (task C4)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def build(db: sqlite3.Connection, as_of: str, out_dir: Path | None = None) -> None:
    """Write every file in the output contract (docs/plan.md §5) for ``as_of``."""
    raise NotImplementedError("agent C: see docs/plan.md §6, task C4")
