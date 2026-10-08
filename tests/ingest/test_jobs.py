import json
from datetime import date

from radar import db
from radar.ingest import jobs, ledger, parsers
from radar.ingest.cache import Cache
from radar.ingest.client import SectorsClient


def page(symbols, next_offset):
    return {
        "results": [{"symbol": f"{s}.JK", "suspension_date": "2026-10-01", "reason": "r", "pdf_url": "u"} for s in symbols],
        "pagination": {"has_next": next_offset is not None, "next_offset": next_offset},
    }


def test_run_follows_pagination_and_bills_each_page(tmp_path):
    conn = db.connect(":memory:")
    db.init_schema(conn)
    responses = [page(["AAAA", "BBBB"], 30), page(["CCCC"], None)]
    urls = []

    def transport(url, headers, timeout):
        urls.append(url)
        return 200, json.dumps(responses.pop(0)).encode()

    client = SectorsClient(conn, cache=Cache(tmp_path), api_key="k", live=True, credit_cap=10, transport=transport)
    call = jobs.Call("suspensions", {"limit": 30}, 1, "suspensions", parsers.parse_suspensions, paginated=True)

    report = jobs.run(client, conn, [call])

    assert report.rows == {"suspensions": 3} and report.failures == []
    assert "offset=30" in urls[1] and "offset" not in urls[0]
    assert ledger.credits_spent(conn) == 2


def test_backfill_plan_is_four_calls_per_symbol_plus_shared():
    calls = jobs.backfill_calls(["BBCA", "BBRI"], date(2026, 10, 4))
    assert len(calls) == 1 + 2 * 4 + 3
    assert sum(c.cost for c in calls) == 1 + 8 + 1 + 3 + 1
    broker = next(c for c in calls if c.path == "broker-summary/BBCA")
    assert broker.params == {"start": "2026-09-20", "end": "2026-10-04"}


def test_universe_query_names_every_company_field():
    where = jobs.universe_query()["where"]
    assert "indices in ['LQ45']" in where
    assert all(field in where for field in parsers.COMPANY_FIELDS.values())


def seeded(tmp_path, transport=None, live=True):
    conn = db.connect(":memory:")
    db.init_schema(conn)
    parsers.upsert(conn, "companies", [{"symbol": s, "name": s} for s in ("BBCA", "BBRI")])
    for table in ("prices", "foreign_flow"):
        parsers.upsert(conn, table, [{"symbol": s, "date": "2026-10-02"} for s in ("BBCA", "BBRI")])
    parsers.upsert(conn, "broker_summary", [
        {"symbol": symbol, "date": "2026-10-02", "broker_code": "AK"}
        for symbol in ("BBCA", "BBRI")
    ])
    parsers.upsert(conn, "filings", [{"id": "x", "symbol": "BBCA", "timestamp": "2026-10-03T20:38:19"}])
    client = SectorsClient(conn, cache=Cache(tmp_path), api_key="k", live=live, credit_cap=500, transport=transport)
    return client, conn


def test_daily_refresh_starts_the_day_after_the_latest_stored_row(tmp_path):
    client, conn = seeded(tmp_path)

    calls = jobs.daily_calls(conn, date(2026, 10, 6))

    per_symbol = [c for c in calls if c.table in ("prices", "foreign_flow", "broker_summary")]
    assert len(per_symbol) == 2 * 3
    assert all(c.params == {"start": "2026-10-03", "end": "2026-10-06"} for c in per_symbol)
    filings = next(c for c in calls if c.table == "filings")
    assert filings.params["start"] == "2026-10-03" and filings.force
    assert jobs.refresh_daily(client, conn, date(2026, 10, 6), dry_run=True).estimate == 6 + 1 + 3 + 1


def test_daily_refresh_skips_tables_that_are_already_current(tmp_path):
    client, conn = seeded(tmp_path)

    calls = jobs.daily_calls(conn, date(2026, 10, 2))

    assert {c.table for c in calls} == {"filings", "corporate_actions", "suspensions"}
    filings = next(call for call in calls if call.table == "filings")
    assert filings.params["start"] == "2026-10-02"
    assert filings.params["end"] == "2026-10-02"


def test_daily_refresh_retries_only_the_symbol_with_a_gap(tmp_path, monkeypatch):
    client, conn = seeded(tmp_path)
    for table in ("prices", "foreign_flow", "broker_summary"):
        row = {"symbol": "BBCA", "date": "2026-10-06"}
        if table == "broker_summary":
            row["broker_code"] = "AK"
        parsers.upsert(conn, table, [row])

    market = [
        call
        for call in jobs.daily_calls(conn, date(2026, 10, 6))
        if call.table in ("prices", "foreign_flow", "broker_summary")
    ]
    assert {call.path for call in market} == {
        "daily/BBRI",
        "foreign-flow/BBRI",
        "broker-summary/BBRI",
    }
    assert all(
        call.params == {"start": "2026-10-03", "end": "2026-10-06"}
        for call in market
    )

    batches = []
    monkeypatch.setattr(
        jobs,
        "run",
        lambda client, conn, calls: batches.append([call.table for call in calls])
        or jobs.Report(),
    )
    jobs.refresh_daily(client, conn, date(2026, 10, 6))
    assert batches[0] == ["prices", "foreign_flow", "broker_summary"]


def test_weekly_refresh_bypasses_the_cache(tmp_path):
    bodies = {
        "companies": {"results": [{"symbol": "BBCA.JK", "company_name": "Bank", "query_values": {"sector": "Financials"}}]},
        "composition": {"symbol": "BBCA.JK", "year": 2026, "data": [{"date": "2026-10-30", "shares_number": 5}]},
    }
    urls = []

    def transport(url, headers, timeout):
        urls.append(url)
        key = "composition" if "composition" in url else "companies"
        return 200, json.dumps(bodies[key]).encode()

    client, conn = seeded(tmp_path, transport)
    jobs.refresh_weekly(client, conn, date(2026, 11, 1))
    report = jobs.refresh_weekly(client, conn, date(2026, 11, 1))

    assert len(urls) == 2 * (1 + 2)  # nothing served from cache on the second run
    assert report.credits == 3
    assert conn.execute("SELECT sector FROM companies WHERE symbol = 'BBCA'").fetchone()[0] == "Financials"


def test_check_reports_gaps_and_unknown_brokers(tmp_path):
    client, conn = seeded(tmp_path)
    parsers.upsert(conn, "prices", [{"symbol": "BBCA", "date": "2026-10-01", "close": 1}])

    text = "\n".join(jobs.check(conn))

    assert "symbols with gaps: BBRI (1)" in text
    assert "broker codes not in registry: AK" in text


def test_daily_refresh_stops_after_one_call_when_there_is_no_new_trading_day(tmp_path):
    urls = []

    def transport(url, headers, timeout):
        urls.append(url)
        if "/daily/" in url:
            return 200, b"[]"
        if "corporate-actions" in url:
            return 200, b"{}"
        return 200, json.dumps({"results": [], "pagination": {"has_next": False}}).encode()

    client, conn = seeded(tmp_path, transport)

    report = jobs.refresh_daily(client, conn, date(2026, 10, 4))

    assert sum("/daily/" in u for u in urls) == 1
    assert not any("broker-summary" in u or "foreign-flow" in u for u in urls)
    assert report.credits == 1 + 1 + 3 + 1
