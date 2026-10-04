"""Rule-based reasons for the flow score. Owned by agent B (task B4)."""

from __future__ import annotations


def build(entry: dict, top: int = 3) -> list[dict]:
    """Reasons ``{code, params, text_en}`` for one ``flow.compute`` entry."""
    raise NotImplementedError("agent B: see docs/plan.md §6, task B4")
