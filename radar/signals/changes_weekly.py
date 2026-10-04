"""Weekly changes relative to five trading days earlier."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from radar.signals import common, investor, investor_config as cfg


def _comparison_date(db, as_of):
    dates = common.trading_days(db, as_of, cfg.WEEKLY_COMPARE_TRADING_DAYS + 1)
    return dates[0] if len(dates) > cfg.WEEKLY_COMPARE_TRADING_DAYS else None


def _upcoming(db, as_of, symbols):
    end = (date.fromisoformat(as_of) + timedelta(days=cfg.UPCOMING_DAYS)).isoformat()
    return [{"date": row["key_date"], "symbol": row["symbol"],
             "type": "dividend_ex_date" if row["type"] in ("dividend", "upcoming_dividend") else row["type"]}
            for row in db.execute("SELECT symbol,type,key_date FROM corporate_actions WHERE key_date>? AND key_date<=? ORDER BY key_date,symbol,type", (as_of, end))
            if row["symbol"] in symbols]


def diff(now: list[dict], prev: list[dict], db: sqlite3.Connection, as_of: str) -> dict:
    """brief_weekly.json without disclaimer; no mutation of score entries."""
    previous = {entry["symbol"]: entry for entry in prev}
    comparison = _comparison_date(db, as_of)
    items = []
    def add(kind, symbol, params, text):
        items.append({"kind": kind, "code": kind.upper(), "symbol": symbol, "params": params, "text_en": text})
    for entry in sorted(now, key=lambda row: row["rank"]):
        symbol, rank = entry["symbol"], entry["rank"]
        old = previous.get(symbol)
        if rank <= 5 and (old is None or old["rank"] > 5):
            add("new_top5", symbol, {"rank": rank, "rank_prev": old["rank"] if old else None},
                f"{symbol} entered the investor top five at rank {rank}.")
        if old is not None:
            change = old["rank"] - rank
            if abs(change) >= cfg.RANK_MOVER_THRESHOLD:
                add("rank_mover", symbol, {"from": old["rank"], "to": rank, "change": change},
                    f"{symbol} moved from investor rank {old['rank']} to {rank}.")
        if comparison is not None:
            latest = investor._holder_snapshots(db, symbol, as_of)
            baseline = investor._holder_snapshots(db, symbol, comparison)
            if latest and baseline and latest[0]["date"] > comparison:
                new_share = investor._institutional_share(latest[0])
                old_share = investor._institutional_share(baseline[0])
                if new_share is not None and old_share is not None:
                    pp = 100 * (new_share - old_share)
                    if abs(pp) >= cfg.HOLDER_SHIFT_MIN_PP:
                        add("holder_shift", symbol, {"pp": pp, "from_date": baseline[0]["date"], "to_date": latest[0]["date"]},
                            f"{symbol} institutional share {'rose' if pp > 0 else 'fell'} by {abs(pp):.2f} percentage points in the new holder snapshot.")
    return {"as_of": as_of, "items": items, "upcoming": _upcoming(db, as_of, {e["symbol"] for e in now})}
