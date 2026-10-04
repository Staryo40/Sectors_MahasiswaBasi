import pytest
from radar.db import connect, init_schema
from radar.signals import flow

@pytest.fixture
def db():
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # Every network operation in weekly tests must be explicitly mocked.
    import urllib.request
    import smtplib
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network operation")
    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    monkeypatch.setattr(smtplib, "SMTP", blocked)
    monkeypatch.delenv("SECTORS_LIVE", raising=False)

@pytest.fixture
def insider(monkeypatch):
    monkeypatch.setattr(flow, "insider_ratio", lambda *args, **kwargs: 0.0)

@pytest.fixture
def trading_days(monkeypatch):
    from radar.signals import common
    def dates(db, as_of, n):
        return sorted(row[0] for row in db.execute("SELECT DISTINCT date FROM prices WHERE date<=? ORDER BY date DESC LIMIT ?", (as_of, n)))
    monkeypatch.setattr(common, "trading_days", dates)

@pytest.fixture
def daily_stubs(monkeypatch, trading_days, insider):
    import copy
    import json
    from pathlib import Path
    from radar.signals import changes_daily
    fixture_dir = Path(__file__).resolve().parents[2] / "fixtures" / "out"
    samples = json.loads((fixture_dir / "daily.json").read_text())
    stock = json.loads((fixture_dir / "stocks" / "BBCA.json").read_text())
    calls = []
    def compute(db, as_of):
        calls.append(as_of)
        companies = list(db.execute("SELECT symbol,name,sector FROM companies ORDER BY symbol"))
        result = []
        for rank, company in enumerate(companies, 1):
            entry = copy.deepcopy(samples[(rank - 1) % len(samples)])
            entry.update(symbol=company["symbol"], name=company["name"] or company["symbol"], sector=company["sector"] or "Unknown", rank=rank)
            entry.pop("rank_prev", None)
            entry.pop("flow_score_prev", None)
            result.append(entry)
        return result
    monkeypatch.setattr(flow, "compute", compute)
    monkeypatch.setattr(flow, "top_brokers", lambda *args, **kwargs: copy.deepcopy(stock["top_brokers"]))
    monkeypatch.setattr(changes_daily, "diff", lambda today, prev, db, as_of: {"as_of": as_of, "items": [], "upcoming": []})
    return calls
