"""Daily horizon: flow score per stock. Owned by agent B (tasks B2, B3)."""

from __future__ import annotations

import math
import sqlite3
from datetime import date, timedelta

from radar.signals import common
from radar.signals import flow_config as cfg


def _days_before(as_of: str, days: int) -> str:
    """The date ``days`` calendar days before ``as_of`` (exclusive lower bound of a window)."""
    return (date.fromisoformat(as_of) - timedelta(days=days)).isoformat()


def _label(score: float) -> str:
    for lower, name in cfg.LABELS:
        if score >= lower:
            return name
    return cfg.LABELS[-1][1]


def _universe(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("SELECT symbol, name, sector FROM companies ORDER BY symbol").fetchall()
    if rows:
        return [dict(r) for r in rows]
    rows = db.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol").fetchall()
    return [{"symbol": r[0], "name": None, "sector": None} for r in rows]


# --- components ---------------------------------------------------------------------------


def _foreign_components(net_by_date: dict[str, float], dates: list[str]) -> tuple[float, float, int]:
    """(foreign_5d, foreign_streak, signed streak length) over the trading ``dates`` (oldest first)."""
    if not dates or not net_by_date:
        return 0.0, 0.0, 0

    short = dates[-cfg.FOREIGN_SHORT_DAYS:]
    sum_short = sum(net_by_date.get(d, 0.0) or 0.0 for d in short)
    sd = common.stdev([net_by_date[d] for d in dates if net_by_date.get(d) is not None])
    if sd:
        z = sum_short / (sd * math.sqrt(cfg.FOREIGN_SHORT_DAYS))
        foreign_5d = common.clip(z, -3.0, 3.0) / 3.0
    else:
        foreign_5d = 0.0

    # Streak: consecutive trading days of same-sign net inflow ending at the last date.
    # A missing day or a zero day ends the streak.
    direction = common.sign(net_by_date.get(dates[-1]))
    streak = 0
    if direction:
        for d in reversed(dates):
            if common.sign(net_by_date.get(d)) == direction:
                streak += 1
            else:
                break
    signed = direction * streak
    foreign_streak = direction * min(streak, cfg.STREAK_CAP_DAYS) / cfg.STREAK_CAP_DAYS
    return foreign_5d, foreign_streak, signed


def _broker_nets(db: sqlite3.Connection, symbol: str, as_of: str) -> list[sqlite3.Row]:
    """Per-broker totals over the broker window, joined with the registry."""
    return db.execute(
        """
        SELECT b.broker_code AS code,
               SUM(b.nval) AS net,
               SUM(b.bval) AS bval, SUM(b.sval) AS sval,
               SUM(b.bavg_per_share * b.blot) AS bavg_w, SUM(CASE WHEN b.bavg_per_share IS NOT NULL THEN b.blot END) AS blot,
               SUM(b.savg_per_share * b.slot) AS savg_w, SUM(CASE WHEN b.savg_per_share IS NOT NULL THEN b.slot END) AS slot,
               r.name AS name, r.is_foreign AS is_foreign, COALESCE(r.cohort, 'unknown') AS cohort
        FROM broker_summary b
        LEFT JOIN brokers r ON r.code = b.broker_code
        WHERE b.symbol = ? AND b.date > ? AND b.date <= ?
        GROUP BY b.broker_code
        """,
        (symbol, _days_before(as_of, cfg.BROKER_WINDOW_DAYS), as_of),
    ).fetchall()


def _broker_components(rows: list[sqlite3.Row]) -> tuple[float, float]:
    """(broker_concentration, institutional_net)."""
    nets = [(r["net"] or 0.0) for r in rows]
    buyers = sorted((n for n in nets if n > 0), reverse=True)[: cfg.TOP_BROKERS]
    sellers = sorted(n for n in nets if n < 0)[: cfg.TOP_BROKERS]
    bt, st = sum(buyers), abs(sum(sellers))
    concentration = common.safe_div(bt - st, bt + st)

    inst = sum((r["net"] or 0.0) for r in rows if r["cohort"] == "institutional")
    half_gross = sum(abs(n) for n in nets) / 2
    institutional = common.clip(common.safe_div(inst, half_gross), -1.0, 1.0)
    return concentration, institutional


def _price_fields(closes: dict[str, float], volumes: dict[str, float], dates: list[str]) -> dict:
    """close, change_1d, return_10d, volume_ratio at the last of ``dates`` (None when not computable)."""
    out = {"close": None, "change_1d": None, "return_10d": None, "volume_ratio": None}
    if not dates:
        return out
    today = dates[-1]
    close = closes.get(today)
    out["close"] = close
    if close is None:
        return out

    def ret(n: int) -> float | None:
        if len(dates) <= n:
            return None
        base = closes.get(dates[-1 - n])
        return close / base - 1 if base else None

    out["change_1d"] = ret(1)
    out["return_10d"] = ret(cfg.RETURN_DAYS)

    vol = volumes.get(today)
    prior = [volumes.get(d) for d in dates[-1 - cfg.VOLUME_MEDIAN_DAYS: -1]]
    med = common.median([v for v in prior if v is not None])
    if vol is not None and med:
        out["volume_ratio"] = vol / med
    return out


def _round(x: float | None, nd: int) -> float | None:
    return None if x is None else round(x, nd)


# --- public interface -----------------------------------------------------------------------


def compute(db: sqlite3.Connection, as_of: str) -> list[dict]:
    """One dict per stock, shaped like a ``daily.json`` entry (docs/plan.md §5)
    without ``rank_prev`` and ``flow_score_prev``, sorted by ``rank``."""
    from radar.signals import flow_reasons  # local import: flow_reasons may import flow helpers

    dates = common.trading_days(db, as_of, cfg.FOREIGN_NORM_DAYS)
    entries: list[dict] = []

    for company in _universe(db):
        symbol = company["symbol"]

        ff = db.execute(
            "SELECT date, net_foreign_inflow FROM foreign_flow WHERE symbol = ? AND date <= ? AND date >= ?",
            (symbol, as_of, dates[0] if dates else as_of),
        ).fetchall()
        net_by_date = {r["date"]: r["net_foreign_inflow"] for r in ff}
        foreign_5d, foreign_streak, _ = _foreign_components(net_by_date, dates)

        concentration, institutional = _broker_components(_broker_nets(db, symbol, as_of))

        px = db.execute(
            "SELECT date, close, volume FROM prices WHERE symbol = ? AND date <= ? AND date >= ?",
            (symbol, as_of, dates[0] if dates else as_of),
        ).fetchall()
        closes = {r["date"]: r["close"] for r in px}
        volumes = {r["date"]: r["volume"] for r in px}
        prices = _price_fields(closes, volumes, dates)

        f = (foreign_5d + concentration) / 2
        r = prices["return_10d"]
        divergence = f if common.sign(f) != common.sign(r) else 0.0
        insider = insider_ratio(db, symbol, as_of, cfg.INSIDER_DAYS)

        values = {
            "foreign_5d": foreign_5d,
            "foreign_streak": foreign_streak,
            "broker_concentration": concentration,
            "institutional_net": institutional,
            "divergence": divergence,
            "insider": insider,
        }
        components = []
        score = 0.0
        for key, weight in cfg.WEIGHTS.items():
            value = common.clip(values[key], -1.0, 1.0)
            contribution = 100 * weight * value
            score += contribution
            components.append(
                {"key": key, "value": round(value, 4), "weight": weight, "contribution": round(contribution, 2)}
            )
        score = round(common.clip(score, -100.0, 100.0), 1)

        flags = []
        r0 = r if r is not None else 0.0
        if f > cfg.DIVERGENCE_FLAG_THRESHOLD and r0 <= 0:
            flags.append("divergence_accumulation")
        if f < -cfg.DIVERGENCE_FLAG_THRESHOLD and r0 >= 0:
            flags.append("divergence_distribution")
        if prices["volume_ratio"] is not None and prices["volume_ratio"] > cfg.UNUSUAL_VOLUME_RATIO:
            flags.append("unusual_volume")

        entry = {
            "symbol": symbol,
            "name": company["name"],
            "sector": company["sector"],
            "rank": 0,
            "flow_score": score,
            "label": _label(score),
            "components": components,
            "flags": flags,
            "reasons": [],
            "close": prices["close"],
            "change_1d": _round(prices["change_1d"], 4),
            "return_10d": _round(prices["return_10d"], 4),
            "volume_ratio": _round(prices["volume_ratio"], 2),
        }
        entry["reasons"] = flow_reasons.build(entry)
        entries.append(entry)

    entries.sort(key=lambda e: (-e["flow_score"], e["symbol"]))
    for i, e in enumerate(entries, start=1):
        e["rank"] = i
    return entries


def top_brokers(db: sqlite3.Connection, symbol: str, as_of: str, n: int = 5) -> dict:
    """``{"buyers": [...], "sellers": [...]}`` as in ``stocks/{SYMBOL}.json``.

    Net value is summed over the broker window. Buyers are sorted by net value
    descending, sellers ascending (largest distribution first). ``avg_price`` is
    the lot-weighted average buy price for buyers and sell price for sellers.
    Brokers missing from the registry get cohort ``unknown``.
    """
    rows = _broker_nets(db, symbol, as_of)

    def item(r: sqlite3.Row, side: str) -> dict:
        if side == "buy":
            avg = common.safe_div(r["bavg_w"], r["blot"], default=None)
        else:
            avg = common.safe_div(r["savg_w"], r["slot"], default=None)
        return {
            "code": r["code"],
            "name": r["name"] if r["name"] is not None else r["code"],
            "cohort": r["cohort"],
            "is_foreign": bool(r["is_foreign"]),
            "net_value": r["net"] or 0.0,
            "avg_price": _round(avg, 2),
        }

    buyers = sorted((r for r in rows if (r["net"] or 0) > 0), key=lambda r: (-r["net"], r["code"]))[:n]
    sellers = sorted((r for r in rows if (r["net"] or 0) < 0), key=lambda r: (r["net"], r["code"]))[:n]
    return {"buyers": [item(r, "buy") for r in buyers], "sellers": [item(r, "sell") for r in sellers]}


def insider_ratio(db: sqlite3.Connection, symbol: str, as_of: str, days: int = 30) -> float:
    """(buys - sells) / (buys + sells) over ``days``; 0.0 if there are none.

    Counts insider filings (``holder_type = 'insider'``) dated in the last
    ``days`` calendar days up to ``as_of``. ``others`` transactions are ignored.
    """
    row = db.execute(
        """
        SELECT SUM(transaction_type = 'buy') AS buys, SUM(transaction_type = 'sell') AS sells
        FROM filings
        WHERE symbol = ? AND holder_type = 'insider'
          AND substr(timestamp, 1, 10) > ? AND substr(timestamp, 1, 10) <= ?
        """,
        (symbol, _days_before(as_of, days), as_of),
    ).fetchone()
    buys, sells = (row["buys"] or 0), (row["sells"] or 0)
    return common.safe_div(buys - sells, buys + sells)
