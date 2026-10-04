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
