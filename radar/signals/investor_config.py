"""Weights for the investor score. Owned by agent C.

Starting values from docs/plan.md §6.
"""

PILLAR_WEIGHTS = {"quality": 0.40, "valuation": 0.25, "slow_flow": 0.35}

# Sector whose leverage is its business model: der_mrq is skipped for it.
FINANCIALS_SECTOR = "Financials"

FOREIGN_LONG_DAYS = (20, 90)
HOLDER_SHIFT_SNAPSHOTS = 3
INSIDER_DAYS = 30
WEEKLY_COMPARE_TRADING_DAYS = 5
