import json

import pytest

from radar import config, db
from radar.ingest import parsers

SAMPLES = config.FIXTURES_DIR / "raw_samples"


def sample(name):
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))["body"]


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    db.init_schema(connection)
    yield connection
    connection.close()


CASES = [
    ("companies_fundamentals", parsers.parse_companies, "companies"),
    ("brokers", parsers.parse_brokers, "brokers"),
    ("daily", parsers.parse_prices, "prices"),
    ("foreign_flow", parsers.parse_foreign_flow, "foreign_flow"),
    ("foreign_flow_universe", parsers.parse_foreign_flow_universe, "foreign_flow"),
    ("broker_summary", parsers.parse_broker_summary, "broker_summary"),
    ("holder_mix", parsers.parse_holder_mix, "holder_mix"),
    ("filings", parsers.parse_filings, "filings"),
    ("corporate_actions", parsers.parse_corporate_actions, "corporate_actions"),
    ("suspensions", parsers.parse_suspensions, "suspensions"),
]


@pytest.mark.parametrize("name, parse, table", CASES)
def test_real_sample_loads_into_its_table(conn, name, parse, table):
    rows = parse(sample(name))
    assert rows

    parsers.upsert(conn, table, rows)
    parsers.upsert(conn, table, rows)  # idempotent on primary key

    stored = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    assert 0 < stored <= len(rows)
    assert all(not str(row.get("symbol", "")).endswith(".JK") for row in rows)


def test_companies_fundamentals_are_mapped():
    rows = parsers.parse_companies(sample("companies_fundamentals"))
    assert len(rows) == 45
    first = rows[0]
    assert first["symbol"] == "AADI"
    assert first["last_close"] > 0 and first["market_cap"] > 0
    assert first["net_profit_margin"] is not None and first["pe_peer_avg"] is not None


def test_broker_summary_keeps_null_foreign_split():
    rows = parsers.parse_broker_summary(sample("broker_summary"))
    assert any(row["f_bval"] is None for row in rows)
    assert {row["symbol"] for row in rows} == {"BBCA"}
    assert len({row["date"] for row in rows}) >= 5


def test_filing_ids_are_stable_and_unique():
    first = parsers.parse_filings(sample("filings"))
    second = parsers.parse_filings(sample("filings"))
    assert [r["id"] for r in first] == [r["id"] for r in second]
    assert {r["transaction_type"] for r in first} <= {"buy", "sell", "others"}


def test_clean_symbol():
    assert parsers.clean_symbol("bbca.jk") == "BBCA"
    assert parsers.clean_symbol("BBCA") == "BBCA"
