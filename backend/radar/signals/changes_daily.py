"""Daily change detection for the daily brief. Owned by agent B (task B5)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from radar.signals import common
from radar.signals import flow_config as cfg

_SIDE = {
    "strong_accumulation": "accumulation",
    "accumulation": "accumulation",
    "neutral": "neutral",
    "distribution": "distribution",
    "strong_distribution": "distribution",
}
_FILING_WORD = {"buy": "acquisition", "sell": "disposal"}
_UPCOMING_TYPE = {"dividend": "dividend_ex_date"}


def _streak(entry: dict) -> int:
    """Signed foreign streak length recovered from the component (capped at STREAK_CAP_DAYS)."""
    for c in entry.get("components", []):
        if c["key"] == "foreign_streak":
            return round(c["value"] * cfg.STREAK_CAP_DAYS)
    return 0


def _divergence_flag(entry: dict) -> str | None:
    for flag in entry.get("flags", []):
        if flag.startswith("divergence_"):
            return flag
    return None


def _previous_trading_day(db: sqlite3.Connection, as_of: str) -> str:
    days = common.trading_days(db, as_of, 2)
    if len(days) == 2 and days[-1] == as_of:
        return days[0]
    if days and days[-1] < as_of:
        return days[-1]
    return (date.fromisoformat(as_of) - timedelta(days=1)).isoformat()


def diff(today: list[dict], prev: list[dict], db: sqlite3.Connection, as_of: str) -> dict:
    """``brief_daily.json`` (docs/plan.md §5) without the ``disclaimer`` key.

    ``today`` and ``prev`` are ``flow.compute`` outputs for ``as_of`` and the
    previous trading day. With an empty ``prev`` the comparison items are
    skipped; filings, suspensions and upcoming events are still reported.
    """
    items: list[dict] = []
    prev_by_symbol = {e["symbol"]: e for e in prev}
    universe = {e["symbol"] for e in today}

    if prev:
        # new_top5
        prev_top = {e["symbol"] for e in prev if e["rank"] <= cfg.BRIEF_TOP_N}
        for e in sorted(today, key=lambda x: x["rank"]):
            if e["rank"] <= cfg.BRIEF_TOP_N and e["symbol"] not in prev_top:
                items.append({
                    "kind": "new_top5", "symbol": e["symbol"],
                    "params": {"rank": e["rank"], "flow_score": e["flow_score"]},
                    "text_en": f"{e['symbol']} entered the top {cfg.BRIEF_TOP_N} of the daily flow list at rank {e['rank']}",
                })

        for e in sorted(today, key=lambda x: x["rank"]):
            p = prev_by_symbol.get(e["symbol"])
            if p is None:
                continue
            sym = e["symbol"]

            # score_flip
            was, now = _SIDE[p["label"]], _SIDE[e["label"]]
            if was != now:
                items.append({
                    "kind": "score_flip", "symbol": sym,
                    "params": {"from": was, "to": now, "flow_score": e["flow_score"],
                               "flow_score_prev": p["flow_score"]},
                    "text_en": f"{sym} flow turned from {was} to {now} (score {p['flow_score']:g} to {e['flow_score']:g})",
                })

            # streak_started / streak_ended
            s_now, s_prev = _streak(e), _streak(p)
            min_days = cfg.STREAK_BRIEF_MIN_DAYS
            if abs(s_now) >= min_days and not (abs(s_prev) >= min_days and common.sign(s_prev) == common.sign(s_now)):
                direction = "in" if s_now > 0 else "out"
                word = "inflow" if s_now > 0 else "outflow"
                items.append({
                    "kind": "streak_started", "symbol": sym,
                    "params": {"days": abs(s_now), "direction": direction},
                    "text_en": f"{sym} has {abs(s_now)} straight days of net foreign {word}",
                })
            elif abs(s_prev) >= min_days and common.sign(s_now) != common.sign(s_prev):
                direction = "in" if s_prev > 0 else "out"
                word = "inflow" if s_prev > 0 else "outflow"
                items.append({
                    "kind": "streak_ended", "symbol": sym,
                    "params": {"days": abs(s_prev), "direction": direction},
                    "text_en": f"{sym} ended a {abs(s_prev)}-day net foreign {word} streak",
                })

            # divergence (newly flagged)
            flag = _divergence_flag(e)
            if flag and flag != _divergence_flag(p):
                side = flag.removeprefix("divergence_")
                move = "falling or flat" if side == "accumulation" else "rising or flat"
                items.append({
                    "kind": "divergence", "symbol": sym,
                    "params": {"direction": side, "return_10d": e.get("return_10d")},
                    "text_en": f"{sym} shows smart-money {side} while the price is {move}",
                })

    since = _previous_trading_day(db, as_of)

    # insider_filing: insider filings dated after the previous trading day, up to as_of.
    filings = db.execute(
        """
        SELECT symbol, substr(timestamp, 1, 10) AS day, transaction_type, holder_type
        FROM filings
        WHERE holder_type = 'insider' AND substr(timestamp, 1, 10) > ? AND substr(timestamp, 1, 10) <= ?
        ORDER BY timestamp, symbol
        """,
        (since, as_of),
    ).fetchall()
    for f in filings:
        if f["symbol"] not in universe:
            continue
        kind = _FILING_WORD.get(f["transaction_type"], "other")
        items.append({
            "kind": "insider_filing", "symbol": f["symbol"],
            "params": {"date": f["day"], "transaction": kind, "holder_type": f["holder_type"]},
            "text_en": f"New insider filing for {f['symbol']}: {kind} reported on {f['day']}",
        })

    # suspension
    suspensions = db.execute(
        "SELECT symbol, date, reason FROM suspensions WHERE date > ? AND date <= ? ORDER BY date, symbol",
        (since, as_of),
    ).fetchall()
    for s in suspensions:
        if s["symbol"] not in universe:
            continue
        items.append({
            "kind": "suspension", "symbol": s["symbol"],
            "params": {"date": s["date"], "reason": s["reason"]},
            "text_en": f"{s['symbol']} trading was suspended on {s['date']}",
        })

    # upcoming corporate actions
    horizon = (date.fromisoformat(as_of) + timedelta(days=cfg.UPCOMING_DAYS)).isoformat()
    actions = db.execute(
        "SELECT symbol, type, key_date FROM corporate_actions WHERE key_date > ? AND key_date <= ? ORDER BY key_date, symbol",
        (as_of, horizon),
    ).fetchall()
    upcoming = [
        {"date": a["key_date"], "symbol": a["symbol"], "type": _UPCOMING_TYPE.get(a["type"], a["type"])}
        for a in actions if a["symbol"] in universe
    ]

    return {"as_of": as_of, "items": items, "upcoming": upcoming}
