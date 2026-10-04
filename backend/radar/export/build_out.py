"""Validated, atomic JSON exports and dated snapshots for every UI."""
from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
import tempfile
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from radar import config
from radar.export.validation import validate
from radar.signals import common, flow, investor, changes_daily, changes_weekly


def _atomic_write(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _past(out_dir, name, as_of, compute, db):
    if as_of is None:
        return []
    snapshot = out_dir / "history" / as_of / f"{name}.json"
    if snapshot.exists():
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        validate(name, data)
        return data
    return compute(db, as_of)


def _brief(data, as_of):
    data = copy.deepcopy(data)
    data["as_of"] = as_of
    data["disclaimer"] = config.DISCLAIMER
    for item in data["items"]:
        item.setdefault("code", item["kind"].upper())
    return data


def _holder_series(db, symbol, as_of):
    series = []
    for row in db.execute("SELECT * FROM holder_mix WHERE symbol=? AND date<=? ORDER BY date", (symbol, as_of)):
        institutional = investor._institutional_share(row)
        foreign = investor._ratio(row["total_f"], row["shares_number"])
        series.append({"date": row["date"], "institutional_pct": None if institutional is None else institutional * 100,
                       "individual_pct": None if institutional is None else (1 - institutional) * 100,
                       "foreign_pct": None if foreign is None else foreign * 100})
    return series


def _stock(db, symbol, as_of, daily, weekly, score_history):
    price = [{"date": r["date"], "close": r["close"], "volume": r["volume"]}
             for r in db.execute("SELECT date,close,volume FROM prices WHERE symbol=? AND date<=? ORDER BY date", (symbol, as_of))]
    cumulative, foreign = 0.0, []
    for row in db.execute("SELECT * FROM foreign_flow WHERE symbol=? AND date<=? ORDER BY date", (symbol, as_of)):
        net = investor._number(row["net_foreign_inflow"])
        cumulative += net or 0
        foreign.append({"date": row["date"], "net": net, "cum": cumulative, "share": row["foreign_share"]})
    filings = [{"date": r["timestamp"][:10], "transaction_type": {"buy": "accumulation", "sell": "distribution"}.get(r["transaction_type"], "others"),
                "holder_type": r["holder_type"] or "unknown"}
               for r in db.execute("SELECT timestamp,transaction_type,holder_type FROM filings WHERE symbol=? AND substr(timestamp,1,10)<=? ORDER BY timestamp,id", (symbol, as_of))]
    events = [{"date": r["key_date"], "type": "dividend_ex_date" if r["type"] in ("dividend", "upcoming_dividend") else r["type"],
               "detail": r["type"].replace("_", " ")}
              for r in db.execute("SELECT type,key_date FROM corporate_actions WHERE symbol=? ORDER BY key_date,type", (symbol,))]
    for row in db.execute("SELECT date,reason FROM suspensions WHERE symbol=? AND date<=? ORDER BY date", (symbol, as_of)):
        detail = re.sub(r"\bbuy\b", "accumulation", row["reason"] or "Trading suspended", flags=re.IGNORECASE)
        detail = re.sub(r"\bsell\b", "distribution", detail, flags=re.IGNORECASE)
        events.append({"date": row["date"], "type": "suspension", "detail": detail})
    events.sort(key=lambda event: (event["date"], event["type"]))
    company = db.execute("SELECT * FROM companies WHERE symbol=?", (symbol,)).fetchone()
    percentiles = {c["key"]: c["percentile"] for c in weekly["components"]}
    fundamentals = []
    for key in (*investor.QUALITY, "pe_ttm", "pb_mrq", "yield_ttm"):
        component_key = {"pe_ttm": "pe_relative", "pb_mrq": "pb_relative"}.get(key, key)
        peer_key = {"pe_ttm": "pe_peer_avg", "pb_mrq": "pb_peer_avg"}.get(key)
        fundamentals.append({"key": key, "value": company[key], "peer_avg": company[peer_key] if peer_key else None,
                             "percentile": percentiles.get(component_key)})
    return {"symbol": symbol, "daily": daily, "investor": weekly,
            "series": {"price": price, "foreign_flow": foreign, "flow_score": score_history, "holder_mix": _holder_series(db, symbol, as_of)},
            "top_brokers": flow.top_brokers(db, symbol, as_of), "filings": filings, "events": events, "fundamentals": fundamentals}


def build(db: sqlite3.Connection, as_of: str, out_dir: Path | None = None) -> None:
    """Write all §5 files only after the complete export validates.

    Per-file atomic replacement prevents truncated JSON. A generation spans
    multiple files, so clients should reload after observing new meta.json.
    """
    if date.fromisoformat(as_of).isoformat() != as_of:
        raise ValueError("as_of must be YYYY-MM-DD")
    out_dir = Path(out_dir) if out_dir is not None else config.OUT_DIR
    dates = common.trading_days(db, as_of, 21)
    prev_day = dates[-2] if len(dates) >= 2 else None
    prev_week = dates[-6] if len(dates) >= 6 else None
    daily = copy.deepcopy(flow.compute(db, as_of))
    weekly = copy.deepcopy(investor.compute(db, as_of))
    daily.sort(key=lambda row: row["rank"])
    weekly.sort(key=lambda row: row["rank"])
    symbols = {row[0] for row in db.execute("SELECT symbol FROM companies")}
    for name, rows in (("daily", daily), ("investor", weekly)):
        if {r["symbol"] for r in rows} != symbols or len(rows) != len(symbols):
            raise ValueError(f"{name} does not contain exactly one entry per company")
        if [r["rank"] for r in rows] != list(range(1, len(rows) + 1)):
            raise ValueError(f"{name} ranks must be consecutive")
    daily_prev = _past(out_dir, "daily", prev_day, flow.compute, db)
    weekly_prev = _past(out_dir, "investor", prev_week, investor.compute, db)
    daily_old = {r["symbol"]: r for r in daily_prev}
    weekly_old = {r["symbol"]: r for r in weekly_prev}
    for entry in daily:
        old = daily_old.get(entry["symbol"], {})
        entry.update(rank_prev=old.get("rank"), flow_score_prev=old.get("flow_score"))
    for entry in weekly:
        entry["rank_prev"] = weekly_old.get(entry["symbol"], {}).get("rank")
    history = {symbol: [] for symbol in symbols}
    for trading_date in dates[-20:]:
        rows = daily if trading_date == as_of else flow.compute(db, trading_date)
        for entry in rows:
            if entry["symbol"] in history:
                history[entry["symbol"]].append({"date": trading_date, "score": entry["flow_score"]})
    daily_map = {r["symbol"]: r for r in daily}
    weekly_map = {r["symbol"]: r for r in weekly}
    output = {"daily.json": ("daily", daily), "investor.json": ("investor", weekly),
              "brief_daily.json": ("brief_daily", _brief(changes_daily.diff(daily, daily_prev, db, as_of), as_of)),
              "brief_weekly.json": ("brief_weekly", _brief(changes_weekly.diff(weekly, weekly_prev, db, as_of), as_of))}
    for symbol in sorted(symbols):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", symbol):
            raise ValueError(f"Unsafe symbol filename: {symbol!r}")
        output[f"stocks/{symbol}.json"] = ("stock", _stock(db, symbol, as_of, daily_map[symbol], weekly_map[symbol], history[symbol]))
    credits = db.execute("SELECT COALESCE(SUM(credits),0) FROM api_calls WHERE from_cache=0").fetchone()[0]
    output["meta.json"] = ("meta", {"as_of": as_of, "generated_at": datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds"),
                                  "universe": config.UNIVERSE_INDEX, "n_stocks": len(symbols), "credits_used": credits, "disclaimer": config.DISCLAIMER})
    # Validate and serialise everything before touching any published file.
    texts = {}
    for name, (schema, data) in output.items():
        validate(schema, data)
        texts[name] = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    for name, text in texts.items():
        _atomic_write(out_dir / "history" / as_of / name, text)
    # meta.json is deliberately the final file installed in each generation.
    for name, text in texts.items():
        _atomic_write(out_dir / name, text)
