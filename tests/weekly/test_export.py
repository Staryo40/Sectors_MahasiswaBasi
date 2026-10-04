import json
from pathlib import Path
import pytest
from radar.export import build_out
from radar.export.validation import validate
from radar.db import connect
from tests.weekly.test_investor import company, complete_history

AS_OF = "2026-10-02"
ROOT = Path(__file__).resolve().parents[2]


def seed(db):
    company(db, "BBCA")
    complete_history(db, "BBCA")
    for date in ("2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"):
        db.execute("INSERT INTO prices(symbol,date,close,volume) VALUES ('BBCA',?,100,10)", (date,))
    db.execute("INSERT INTO filings(id,symbol,timestamp,transaction_type,holder_type) VALUES ('1','BBCA','2026-10-02T12:00:00','buy','insider')")
    db.execute("INSERT INTO filings(id,symbol,timestamp,transaction_type,holder_type) VALUES ('2','BBCA','2026-10-03T12:00:00','sell','insider')")
    db.execute("INSERT INTO api_calls(ts,url,credits,from_cache) VALUES ('2026-10-04','fixture',7,0)")
    db.execute("INSERT INTO api_calls(ts,url,credits,from_cache) VALUES ('2026-10-04','fixture',99,1)")


def assert_export(directory, expected):
    for name in ("meta", "daily", "investor", "brief_daily", "brief_weekly"):
        data = json.loads((directory / f"{name}.json").read_text())
        validate(name, data)
    meta = json.loads((directory / "meta.json").read_text())
    assert meta["n_stocks"] == expected
    symbols = {r["symbol"] for r in json.loads((directory / "daily.json").read_text())}
    assert len(symbols) == expected
    for symbol in symbols:
        data = json.loads((directory / "stocks" / f"{symbol}.json").read_text())
        validate("stock", data)
        assert data["symbol"] == symbol


def test_complete_export_history_and_comparison_dates(db, daily_stubs, tmp_path):
    seed(db)
    build_out.build(db, AS_OF, tmp_path)
    assert_export(tmp_path, 1)
    assert_export(tmp_path / "history" / AS_OF, 1)
    assert "2026-10-01" in daily_stubs
    assert json.loads((tmp_path / "daily.json").read_text())[0]["rank_prev"] == 1
    investor = json.loads((tmp_path / "investor.json").read_text())[0]
    assert investor["rank_prev"] == 1
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["credits_used"] == 7
    assert meta["generated_at"].endswith("+07:00")
    stock = json.loads((tmp_path / "stocks/BBCA.json").read_text())
    assert stock["filings"] == [{"date": AS_OF, "transaction_type": "accumulation", "holder_type": "insider"}]
    assert len(stock["series"]["flow_score"]) == 6
    assert stock["series"]["holder_mix"][-1]["institutional_pct"] == pytest.approx(60)
    assert stock["series"]["foreign_flow"][-1]["cum"] == 10
    assert not list(tmp_path.rglob("*.tmp"))


def test_validation_failure_preserves_all_published_files(db, daily_stubs, tmp_path, monkeypatch):
    seed(db)
    build_out.build(db, AS_OF, tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*.json")}
    original = build_out.flow.compute
    def invalid(*args):
        rows = original(*args)
        rows[0]["flow_score"] = 101
        return rows
    monkeypatch.setattr(build_out.flow, "compute", invalid)
    with pytest.raises(Exception, match="101"):
        build_out.build(db, AS_OF, tmp_path)
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert before == after


def test_comparison_uses_published_snapshot(db, daily_stubs, tmp_path):
    seed(db)
    build_out.build(db, AS_OF, tmp_path)
    daily = json.loads((tmp_path / "daily.json").read_text())
    daily[0].update(rank=9, flow_score=13)
    weekly = json.loads((tmp_path / "investor.json").read_text())
    weekly[0]["rank"] = 8
    for name, date, rows in [("daily", "2026-10-01", daily), ("investor", "2026-09-25", weekly)]:
        folder = tmp_path / "history" / date
        folder.mkdir(parents=True)
        (folder / f"{name}.json").write_text(json.dumps(rows))
    build_out.build(db, AS_OF, tmp_path)
    row = json.loads((tmp_path / "daily.json").read_text())[0]
    assert (row["rank_prev"], row["flow_score_prev"]) == (9, 13)
    assert json.loads((tmp_path / "investor.json").read_text())[0]["rank_prev"] == 8


def test_atomic_failure_cleans_up_temporary_file(tmp_path, monkeypatch):
    target = tmp_path / "daily.json"
    target.write_text("old")
    def fail(source, destination):
        assert Path(source).read_text() == "new"
        raise OSError("replace failed")
    monkeypatch.setattr(build_out.os, "replace", fail)
    with pytest.raises(OSError):
        build_out._atomic_write(target, "new")
    assert target.read_text() == "old"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("relative", ["data/sectors.db", "fixtures/synthetic/synthetic.db"])
def test_database_export_with_agent_b_fixture_stubs(relative, daily_stubs, tmp_path):
    source = ROOT / relative
    if not source.exists():
        pytest.skip(f"Agent database not present: {relative}")
    db = connect(source)
    try:
        db.execute("PRAGMA query_only=ON")
        as_of = db.execute("SELECT MAX(date) FROM prices").fetchone()[0]
        n_stocks = db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        ledger_before = db.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0]
        build_out.build(db, as_of, tmp_path)
        assert_export(tmp_path, n_stocks)
        assert_export(tmp_path / "history" / as_of, n_stocks)
        assert db.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == ledger_before
    finally:
        db.close()
