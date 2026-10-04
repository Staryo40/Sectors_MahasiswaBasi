"""Weekly/monthly investor ranking, computed exclusively from SQLite rows.

Percentiles use average positions for ties; a singleton has rank 0.5.
Historical company fundamentals are unavailable in the database contract.
"""
from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from radar.signals import common, flow, investor_reasons, investor_config as cfg

QUALITY = ("roe_ttm", "net_profit_margin", "yoy_quarter_earnings_growth",
           "yoy_quarter_revenue_growth", "der_mrq")
VALUATION = ("pe_relative", "pb_relative", "yield_ttm")
SLOW_FLOW = ("foreign_20d", "foreign_90d", "holder_shift", "insider")
INPUTS = {"quality": QUALITY, "valuation": VALUATION, "slow_flow": SLOW_FLOW}
LOWER_IS_BETTER = {"der_mrq", "pe_relative", "pb_relative"}


def _number(value):
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _ratio(value, denominator):
    value, denominator = _number(value), _number(denominator)
    return value / denominator if value is not None and denominator is not None and denominator > 0 else None


def _percentile_rank(values, higher_is_better=True):
    """Temporary fallback permitted by C's brief while common is a stub."""
    try:
        return common.percentile_rank(values, higher_is_better=higher_is_better)
    except NotImplementedError:
        present = sorted(v for v in values.values() if v is not None)
        positions = defaultdict(list)
        for index, value in enumerate(present):
            positions[value].append(index)
        ranks = {v: (sum(indices) / len(indices) / (len(present) - 1)
                     if len(present) > 1 else 0.5) for v, indices in positions.items()}
        return {key: None if value is None else (ranks[value] if higher_is_better else 1 - ranks[value])
                for key, value in values.items()}


def _holder_snapshots(db, symbol, as_of):
    # Retain the latest observation in each distinct calendar month.
    months = {}
    for row in db.execute("SELECT * FROM holder_mix WHERE symbol=? AND date<=? ORDER BY date DESC", (symbol, as_of)):
        months.setdefault(row["date"][:7], row)
        if len(months) == cfg.HOLDER_SHIFT_SNAPSHOTS:
            break
    return list(months.values())


def _institutional_share(row):
    local, foreign = _number(row["individual_l"]), _number(row["individual_f"])
    if local is None or foreign is None:
        return None
    individual = _ratio(local + foreign, row["shares_number"])
    return None if individual is None else 1 - individual


def _holder_shift(db, symbol, as_of):
    rows = _holder_snapshots(db, symbol, as_of)
    if len(rows) < cfg.HOLDER_SHIFT_SNAPSHOTS:
        return None
    shares = [_institutional_share(row) for row in rows]
    return None if any(v is None for v in shares) else shares[0] - shares[-1]


def _foreign_ratio(db, symbol, as_of, days, market_cap):
    dates = [row[0] for row in db.execute(
        "SELECT DISTINCT date FROM prices WHERE date<=? ORDER BY date DESC LIMIT ?", (as_of, days))]
    if not dates:
        return None
    values = [_number(row[0]) for row in db.execute(
        "SELECT net_foreign_inflow FROM foreign_flow WHERE symbol=? AND date BETWEEN ? AND ?",
        (symbol, dates[-1], as_of))]
    present = [v for v in values if v is not None]
    return _ratio(sum(present), market_cap) if present else None


def compute(db: sqlite3.Connection, as_of: str) -> list[dict]:
    """One investor.json entry per company, excluding rank_prev."""
    companies = [dict(row) for row in db.execute("SELECT * FROM companies ORDER BY symbol")]
    raw = {}
    skipped = {}
    for company in companies:
        symbol = company["symbol"]
        skipped[symbol] = {"der_mrq"} if (company["sector"] or "").casefold() == cfg.FINANCIALS_SECTOR.casefold() else set()
        values = {key: _number(company[key]) for key in QUALITY}
        for key in skipped[symbol]:
            values[key] = None
        values.update(pe_relative=_ratio(company["pe_ttm"], company["pe_peer_avg"]),
                      pb_relative=_ratio(company["pb_mrq"], company["pb_peer_avg"]),
                      yield_ttm=_number(company["yield_ttm"]))
        price = db.execute("SELECT market_cap FROM prices WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT 1", (symbol, as_of)).fetchone()
        cap = price[0] if price and _number(price[0]) is not None else company["market_cap"]
        for days in cfg.FOREIGN_LONG_DAYS:
            values[f"foreign_{days}d"] = _foreign_ratio(db, symbol, as_of, days, cap)
        values["holder_shift"] = _holder_shift(db, symbol, as_of)
        values["insider"] = _number(flow.insider_ratio(db, symbol, as_of, days=cfg.INSIDER_DAYS))
        raw[symbol] = values

    percentiles = {}
    for keys in INPUTS.values():
        for key in keys:
            values = {symbol: values[key] for symbol, values in raw.items()}
            if key == "pe_relative":
                positives = [v for v in values.values() if v is not None and v >= 0]
                last = max(positives, default=0) + 1
                values = {s: last if v is not None and v < 0 else v for s, v in values.items()}
            percentiles[key] = _percentile_rank(values, higher_is_better=key not in LOWER_IS_BETTER)
            if key == "pe_relative":
                for symbol in raw:
                    if raw[symbol][key] is not None and raw[symbol][key] < 0:
                        percentiles[key][symbol] = 0.0

    entries = []
    for company in companies:
        symbol = company["symbol"]
        components, pillars = [], {}
        for pillar, keys in INPUTS.items():
            present = []
            for key in keys:
                if key in skipped[symbol]:
                    continue
                percentile = percentiles[key][symbol]
                components.append({"key": key, "pillar": pillar, "raw": raw[symbol][key], "percentile": percentile})
                if percentile is not None:
                    present.append(percentile)
            pillars[pillar] = 100 * sum(present) / len(present) if present else None
        weights = sum(cfg.PILLAR_WEIGHTS[p] for p in pillars if pillars[p] is not None)
        score = sum(cfg.PILLAR_WEIGHTS[p] * v for p, v in pillars.items() if v is not None) / weights if weights else 0.0
        entries.append({"symbol": symbol, "name": company["name"] or symbol, "sector": company["sector"] or "Unknown",
                        "rank": 0, "investor_score": score, "pillars": pillars, "components": components,
                        "coverage": sum(c["percentile"] is not None for c in components) / len(components), "reasons": []})
    entries.sort(key=lambda entry: (-entry["investor_score"], entry["symbol"]))
    for rank, entry in enumerate(entries, 1):
        entry["rank"] = rank
        entry["reasons"] = investor_reasons.build(entry)
    return entries
