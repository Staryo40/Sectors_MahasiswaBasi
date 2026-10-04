"""Fetch jobs: plan the calls, estimate their cost, run them, fill the database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from radar import config
from radar.ingest import parsers
from radar.ingest.client import SectorsClient, SectorsError

PAGE_LIMIT = 30
PRICE_WINDOW_DAYS = 90
BROKER_WINDOW_DAYS = 14
FILINGS_WINDOW_DAYS = 30
EVENTS_WINDOW_DAYS = 30
CORPORATE_ACTION_TYPES = ("dividend", "right_issue", "stock_split")


@dataclass
class Call:
    path: str
    params: dict
    cost: int
    table: str
    parse: Callable
    paginated: bool = False


@dataclass
class Report:
    rows: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def add(self, table: str, count: int) -> None:
        self.rows[table] = self.rows.get(table, 0) + count


def universe_query() -> dict:
    """One screener call that returns every ``companies`` column for the universe.

    The screener only echoes fields named in the query, so each one is
    referenced in a condition that any non-null value satisfies.
    """
    numeric = [f for column, f in parsers.COMPANY_FIELDS.items() if column not in ("sector", "sub_sector")]
    conditions = [f"{f} > -1000000000" for f in numeric] + ["sector != ''", "sub_sector != ''"]
    where = f"indices in ['{config.UNIVERSE_INDEX}'] and ({' or '.join(conditions)})"
    return {"where": where, "limit": 200, "include_query_values": "true"}


def fetch_universe(client: SectorsClient, conn: sqlite3.Connection) -> list[str]:
    body = client.get("companies", universe_query(), cost=1)
    rows = parsers.parse_companies(body)
    parsers.upsert(conn, "companies", rows)
    return sorted(row["symbol"] for row in rows)


def backfill_calls(symbols: list[str], today: date) -> list[Call]:
    end = today.isoformat()
    price_start = (today - timedelta(days=PRICE_WINDOW_DAYS)).isoformat()
    broker_start = (today - timedelta(days=BROKER_WINDOW_DAYS)).isoformat()
    filings_start = (today - timedelta(days=FILINGS_WINDOW_DAYS)).isoformat()
    events_start = (today - timedelta(days=EVENTS_WINDOW_DAYS)).isoformat()
    events_end = (today + timedelta(days=EVENTS_WINDOW_DAYS)).isoformat()

    calls = [Call("brokers", {}, 1, "brokers", parsers.parse_brokers)]
    for symbol in symbols:
        calls += [
            Call(f"daily/{symbol}", {"start": price_start, "end": end}, 1, "prices", parsers.parse_prices),
            Call(f"foreign-flow/{symbol}", {"start": price_start, "end": end}, 1, "foreign_flow", parsers.parse_foreign_flow),
            Call(f"broker-summary/{symbol}", {"start": broker_start, "end": end}, 1, "broker_summary", parsers.parse_broker_summary),
            Call(f"company/shareholders-composition/{symbol}", {"year": today.year}, 1, "holder_mix", parsers.parse_holder_mix),
        ]
    calls += [
        Call("filings", {"start": filings_start, "end": end, "limit": PAGE_LIMIT}, 1, "filings", parsers.parse_filings, paginated=True),
        Call(
            "corporate-actions",
            {"start": events_start, "end": events_end, "type": ",".join(CORPORATE_ACTION_TYPES)},
            len(CORPORATE_ACTION_TYPES),
            "corporate_actions",
            parsers.parse_corporate_actions,
        ),
        Call("suspensions", {"start": events_start, "end": end, "limit": PAGE_LIMIT}, 1, "suspensions", parsers.parse_suspensions, paginated=True),
    ]
    return calls


def estimate(client: SectorsClient, calls: list[Call]) -> int:
    """Credits the uncached calls will cost. Paginated feeds count their first page only."""
    return sum(call.cost for call in calls if client.cache.get(call.path, call.params) is None)


def run(client: SectorsClient, conn: sqlite3.Connection, calls: list[Call]) -> Report:
    report = Report()
    for call in calls:
        offset = 0
        while True:
            params = dict(call.params, offset=offset) if offset else call.params
            try:
                body = client.get(call.path, params, call.cost)
            except SectorsError as err:
                report.failures.append(f"{call.path} {params}: HTTP {err.status}")
                break
            report.add(call.table, parsers.upsert(conn, call.table, call.parse(body)))
            pagination = body.get("pagination") if isinstance(body, dict) else None
            if not (call.paginated and pagination and pagination.get("has_next")):
                break
            offset = pagination["next_offset"]
    return report
