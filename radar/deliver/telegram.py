"""Telegram brief sender. Owned by agent C (task C5)."""

from __future__ import annotations


def format_brief(brief: dict) -> str:
    """Minimal default message text; the real wording is the team's decision."""
    raise NotImplementedError("agent C: see docs/plan.md §6, task C5")


def send(text: str, dry_run: bool = True) -> None:
    raise NotImplementedError("agent C: see docs/plan.md §6, task C5")
