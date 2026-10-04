import pytest
from radar.signals import investor, common

def company(db, symbol, **values):
    row = dict(symbol=symbol, name=symbol, sector="Industrials", market_cap=1000,
               roe_ttm=0.2, net_profit_margin=0.1, der_mrq=1,
               yoy_quarter_earnings_growth=0.1, yoy_quarter_revenue_growth=0.1,
               pe_ttm=10, pe_peer_avg=20, pb_mrq=1, pb_peer_avg=2, yield_ttm=0.03)
    row.update(values)
    db.execute(f"INSERT INTO companies ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))

def complete_history(db, symbol):
    db.execute("INSERT INTO prices(symbol,date,close,market_cap) VALUES (?, '2026-10-02', 100, 1000)", (symbol,))
    db.execute("INSERT INTO foreign_flow(symbol,date,net_foreign_inflow) VALUES (?, '2026-10-02', 10)", (symbol,))
    for date, individual in [("2026-07-31", 50), ("2026-08-31", 45), ("2026-09-30", 40)]:
        db.execute("INSERT INTO holder_mix(symbol,date,shares_number,individual_l,individual_f) VALUES (?, ?, 100, ?, 0)", (symbol, date, individual))

def test_complete_score_and_financials_coverage(db, insider):
    company(db, "A")
    company(db, "F", sector="Financials", der_mrq=None)
    for symbol in ("A", "F"):
        complete_history(db, symbol)
    rows = investor.compute(db, "2026-10-02")
    assert all(r["coverage"] == 1 for r in rows)
    assert all(r["investor_score"] == pytest.approx(50) for r in rows)
    financial = next(r for r in rows if r["symbol"] == "F")
    assert "der_mrq" not in [c["key"] for c in financial["components"]]
    assert financial["rank"] == 2  # deterministic symbol tie-break

def test_missing_input_and_pillar_renormalisation(db, insider):
    company(db, "A", pe_ttm=None, pb_mrq=None, yield_ttm=None, roe_ttm=None)
    row = investor.compute(db, "2026-10-02")[0]
    assert row["coverage"] == pytest.approx(5 / 12)
    assert row["pillars"] == {"quality": 50, "valuation": None, "slow_flow": 50}
    assert row["investor_score"] == pytest.approx(50)

def test_negative_pe_ranks_last(db, insider):
    company(db, "A", pe_ttm=-2)
    company(db, "B", pe_ttm=10)
    company(db, "C", pe_ttm=30)
    rows = {r["symbol"]: r for r in investor.compute(db, "2026-10-02")}
    pe = {s: next(c for c in r["components"] if c["key"] == "pe_relative") for s, r in rows.items()}
    assert pe["A"]["raw"] == -0.1
    assert pe["A"]["percentile"] == 0
    assert pe["B"]["percentile"] > pe["C"]["percentile"] > pe["A"]["percentile"]
    assert all(0 <= r["investor_score"] <= 100 for r in rows.values())

def test_future_rows_excluded_and_available_history_used(db, insider):
    company(db, "A")
    complete_history(db, "A")
    db.execute("INSERT INTO foreign_flow(symbol,date,net_foreign_inflow) VALUES ('A','2026-10-03',99999)")
    db.execute("INSERT INTO prices(symbol,date,close,market_cap) VALUES ('A','2026-10-03',100,1)")
    db.execute("INSERT INTO holder_mix(symbol,date,shares_number,individual_l,individual_f) VALUES ('A','2026-10-03',100,90,0)")
    row = investor.compute(db, "2026-10-02")[0]
    raw = {c["key"]: c["raw"] for c in row["components"]}
    assert raw["foreign_90d"] == pytest.approx(0.01)
    assert raw["holder_shift"] == pytest.approx(0.1)

def test_holder_requires_three_distinct_months(db, insider):
    company(db, "A")
    for date in ("2026-09-01", "2026-09-15", "2026-09-30"):
        db.execute("INSERT INTO holder_mix(symbol,date,shares_number,individual_l,individual_f) VALUES ('A',?,100,40,0)", (date,))
    assert investor._holder_shift(db, "A", "2026-10-02") is None

def test_uses_agent_b_interfaces(db, monkeypatch):
    company(db, "A")
    calls = []
    monkeypatch.setattr(common, "percentile_rank", lambda values, higher_is_better=True: {s: None if v is None else 0.75 for s, v in values.items()})
    monkeypatch.setattr(investor.flow, "insider_ratio", lambda *args, **kwargs: calls.append((args, kwargs)) or -1)
    row = investor.compute(db, "2026-10-02")[0]
    assert row["investor_score"] == pytest.approx(75)
    assert calls[0][0][1:] == ("A", "2026-10-02")
    assert calls[0][1] == {"days": 30}
