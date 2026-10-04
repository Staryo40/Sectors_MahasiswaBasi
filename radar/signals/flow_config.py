"""Weights and thresholds for the flow score. Owned by agent B.

Starting values from docs/plan.md §6; tune in task B6.
"""

WEIGHTS = {
    "foreign_5d": 0.30,
    "foreign_streak": 0.15,
    "broker_concentration": 0.25,
    "institutional_net": 0.15,
    "divergence": 0.10,
    "insider": 0.05,
}

# Lower bound of each label, checked from the top.
LABELS = [
    (40, "strong_accumulation"),
    (15, "accumulation"),
    (-15, "neutral"),
    (-40, "distribution"),
    (float("-inf"), "strong_distribution"),
]

FOREIGN_SHORT_DAYS = 5
FOREIGN_NORM_DAYS = 90
STREAK_CAP_DAYS = 10
BROKER_WINDOW_DAYS = 14
TOP_BROKERS = 3
RETURN_DAYS = 10
INSIDER_DAYS = 30
DIVERGENCE_FLAG_THRESHOLD = 0.3
UNUSUAL_VOLUME_RATIO = 2.0
VOLUME_MEDIAN_DAYS = 20
