"""Write contract-shaped sample output into data/demo/ for the demo UI.

Series, brokers, filings and fundamentals are real rows from data/sectors.db.
SCORES, RANKS AND REASONS ARE RANDOM PLACEHOLDERS: the real ones come from the
signal modules via ``python -m radar export``. This exists only so the demo UI
can be looked at before those modules are finished.

Run from the repo root: ``python backend/scripts/generate_demo.py``
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from radar import config, db  # noqa: E402

OUT = ROOT / "data" / "demo"
FLOW_KEYS = [
    ("foreign_5d", 0.30),
    ("foreign_streak", 0.15),
    ("broker_concentration", 0.25),
    ("institutional_net", 0.15),
    ("divergence", 0.10),
    ("insider", 0.05),
]
FUNDAMENTALS = ["roe_ttm", "net_profit_margin", "der_mrq", "yoy_quarter_earnings_growth", "yoy_quarter_revenue_growth", "pe_ttm", "pb_mrq", "yield_ttm"]
PEER = {"pe_ttm": "pe_peer_avg", "pb_mrq": "pb_peer_avg"}


def label(score: float) -> str:
    for bound, name in ((40, "strong_accumulation"), (15, "accumulation"), (-15, "neutral"), (-40, "distribution")):
        if score >= bound:
            return name
    return "strong_distribution"


def write(name: str, payload) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    rng = random.Random(7)
    conn = db.connect()
    as_of = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    companies = conn.execute("SELECT * FROM companies ORDER BY symbol").fetchall()
    note = "SAMPLE DATA: scores, ranks and reasons are random placeholders. "

    daily, investor = [], []
    for c in companies:
        prices = conn.execute("SELECT date, close, volume FROM prices WHERE symbol = ? ORDER BY date", (c["symbol"],)).fetchall()
        closes = [p["close"] for p in prices]
        volumes = sorted(p["volume"] for p in prices[-20:])
        components = []
        for key, weight in FLOW_KEYS:
            value = round(rng.uniform(-1, 1), 2)
            components.append({"key": key, "value": value, "weight": weight, "contribution": round(100 * weight * value, 1)})
        score = round(sum(x["contribution"] for x in components), 1)
        ret10 = closes[-1] / closes[-11] - 1
        flags = []
        if score > 15 and ret10 <= 0:
            flags.append("divergence_accumulation")
        if score < -15 and ret10 >= 0:
            flags.append("divergence_distribution")
        ratio = round(prices[-1]["volume"] / volumes[len(volumes) // 2], 2)
        if ratio > 2:
            flags.append("unusual_volume")
        days = rng.randint(2, 8)
        daily.append({
            "symbol": c["symbol"], "name": c["name"], "sector": c["sector"],
            "flow_score": score, "flow_score_prev": round(score + rng.uniform(-15, 15), 1), "label": label(score),
            "components": components, "flags": flags,
            "reasons": [{"code": "FOREIGN_STREAK", "params": {"days": days, "direction": "in" if score > 0 else "out"},
                         "text_en": f"Foreign investors net {'bought' if score > 0 else 'sold'} for {days} days in a row (placeholder)"}],
            "close": closes[-1], "change_1d": round(closes[-1] / closes[-2] - 1, 4),
            "return_10d": round(ret10, 4), "volume_ratio": ratio,
        })
        pillars = {k: round(rng.uniform(15, 95), 1) for k in ("quality", "valuation", "slow_flow")}
        inputs = [k for k in FUNDAMENTALS if c[k] is not None]
        investor.append({
            "symbol": c["symbol"], "name": c["name"], "sector": c["sector"],
            "investor_score": round(0.40 * pillars["quality"] + 0.25 * pillars["valuation"] + 0.35 * pillars["slow_flow"], 1),
            "pillars": pillars,
            "components": [{"key": k, "pillar": "valuation" if k in ("pe_ttm", "pb_mrq", "yield_ttm") else "quality",
                            "raw": c[k], "percentile": round(rng.random(), 2)} for k in inputs],
            "coverage": round(len(inputs) / len(FUNDAMENTALS), 2),
            "reasons": [{"code": "QUALITY_HIGH", "params": {}, "text_en": "Return on equity in the top third of the universe (placeholder)"}],
        })

    daily.sort(key=lambda e: -e["flow_score"])
    investor.sort(key=lambda e: -e["investor_score"])
    for entries in (daily, investor):
        for i, entry in enumerate(entries, 1):
            entry["rank"] = i
            entry["rank_prev"] = max(1, min(len(entries), i + rng.randint(-4, 4)))
    by_symbol = {"daily": {e["symbol"]: e for e in daily}, "investor": {e["symbol"]: e for e in investor}}

    for c in companies:
        s = c["symbol"]
        prices = conn.execute("SELECT date, close, volume FROM prices WHERE symbol = ? ORDER BY date", (s,)).fetchall()
        flow, cum = [], 0
        for r in conn.execute("SELECT date, net_foreign_inflow, foreign_share FROM foreign_flow WHERE symbol = ? ORDER BY date", (s,)):
            cum += r["net_foreign_inflow"] or 0
            flow.append({"date": r["date"], "net": r["net_foreign_inflow"], "cum": cum, "share": r["foreign_share"]})
        mix = []
        for r in conn.execute("SELECT * FROM holder_mix WHERE symbol = ? ORDER BY date", (s,)):
            shares = r["shares_number"]
            individual = (r["individual_l"] + r["individual_f"]) / shares
            mix.append({"date": r["date"], "institutional_pct": round(1 - individual, 4), "individual_pct": round(individual, 4),
                        "foreign_pct": round(r["total_f"] / shares, 4)})
        walk, history = by_symbol["daily"][s]["flow_score"], []
        for p in reversed(prices[-20:]):
            history.append({"date": p["date"], "score": round(max(-100, min(100, walk)), 1)})
            walk += rng.uniform(-10, 10)
        net = conn.execute(
            """SELECT b.broker_code code, COALESCE(r.name, b.broker_code) name, COALESCE(r.cohort, 'unknown') cohort,
                      COALESCE(r.is_foreign, 0) is_foreign, SUM(b.nval) net_value, SUM(b.bval) bval, SUM(b.sval) sval,
                      SUM(b.blot) blot, SUM(b.slot) slot
               FROM broker_summary b LEFT JOIN brokers r ON r.code = b.broker_code
               WHERE b.symbol = ? GROUP BY b.broker_code ORDER BY net_value DESC""", (s,)).fetchall()

        def broker(row, side):
            lots, value = (row["blot"], row["bval"]) if side == "b" else (row["slot"], row["sval"])
            return {"code": row["code"], "name": row["name"], "cohort": row["cohort"], "is_foreign": bool(row["is_foreign"]),
                    "net_value": row["net_value"], "avg_price": round(value / (lots * 100)) if lots else None}

        filings = []
        for r in conn.execute("SELECT * FROM filings WHERE symbol = ? ORDER BY timestamp DESC", (s,)):
            raw = json.loads(r["raw_json"])
            filings.append({"date": r["timestamp"][:10], "transaction_type": r["transaction_type"], "holder_type": r["holder_type"],
                            "holder_name": raw.get("holder_name"), "transaction_value": raw.get("transaction_value")})
        events = [{"date": r["key_date"], "type": r["type"], "detail": r["raw_json"]}
                  for r in conn.execute("SELECT * FROM corporate_actions WHERE symbol = ? ORDER BY key_date", (s,))]
        write(f"stocks/{s}.json", {
            "symbol": s, "daily": by_symbol["daily"][s], "investor": by_symbol["investor"][s],
            "series": {"price": [dict(p) for p in prices], "foreign_flow": flow, "flow_score": history[::-1], "holder_mix": mix},
            "top_brokers": {"buyers": [broker(r, "b") for r in net[:5]], "sellers": [broker(r, "s") for r in net[::-1][:5]]},
            "filings": filings, "events": events,
            "fundamentals": [{"key": k, "value": c[k], "peer_avg": c[PEER[k]] if k in PEER else None, "percentile": round(rng.random(), 2)}
                             for k in FUNDAMENTALS],
        })

    top = daily[0]
    upcoming = [{"date": r["key_date"], "symbol": r["symbol"], "type": r["type"]} for r in conn.execute(
        "SELECT * FROM corporate_actions WHERE key_date >= ? AND symbol IN (SELECT symbol FROM companies) ORDER BY key_date", (as_of,))]
    write("meta.json", {"as_of": as_of, "generated_at": as_of + "T18:00:00+07:00", "universe": config.UNIVERSE_INDEX,
                        "n_stocks": len(companies), "credits_used": 201, "disclaimer": note + config.DISCLAIMER})
    write("daily.json", daily)
    write("investor.json", investor)
    write("brief_daily.json", {"as_of": as_of, "disclaimer": note + config.DISCLAIMER, "upcoming": upcoming, "items": [
        {"kind": "new_top5", "symbol": top["symbol"], "params": {"rank": 1}, "text_en": f"{top['symbol']} entered the top 5 by flow score (placeholder)"},
        {"kind": "score_flip", "symbol": daily[-1]["symbol"], "params": {"from": "neutral", "to": "distribution"},
         "text_en": f"{daily[-1]['symbol']} moved from neutral to distribution (placeholder)"}]})
    write("brief_weekly.json", {"as_of": as_of, "disclaimer": note + config.DISCLAIMER, "upcoming": [], "items": [
        {"kind": "rank_mover", "symbol": investor[0]["symbol"], "params": {"from": 6, "to": 1},
         "text_en": f"{investor[0]['symbol']} rose from rank 6 to 1 on the investor list (placeholder)"}]})
    print(f"Wrote sample for {len(companies)} stocks, as of {as_of}, to {OUT}")


if __name__ == "__main__":
    main()
