"""Fetch jobs: plan the calls, estimate their cost, run them, fill the database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from radar import config, db
from radar.ingest import ledger, parsers
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
    force: bool = False


@dataclass
class Report:
    rows: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    credits: int = 0
    estimate: int = 0

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


def fetch_universe(client: SectorsClient, conn: sqlite3.Connection, force: bool = False) -> list[str]:
    body = client.get("companies", universe_query(), cost=1, force=force)
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
    return sum(call.cost for call in calls if call.force or client.cache.get(call.path, call.params) is None)


def run(client: SectorsClient, conn: sqlite3.Connection, calls: list[Call]) -> Report:
    report = Report()
    spent_before = ledger.credits_spent(conn)
    for call in calls:
        offset = 0
        while True:
            params = dict(call.params, offset=offset) if offset else call.params
            try:
                body = client.get(call.path, params, call.cost, force=call.force)
            except SectorsError as err:
                report.failures.append(f"{call.path} {params}: HTTP {err.status}")
                break
            report.add(call.table, parsers.upsert(conn, call.table, call.parse(body)))
            pagination = body.get("pagination") if isinstance(body, dict) else None
            if not (call.paginated and pagination and pagination.get("has_next")):
                break
            offset = pagination["next_offset"]
    report.credits = ledger.credits_spent(conn) - spent_before
    return report


def _open(client: SectorsClient | None, conn: sqlite3.Connection | None) -> tuple[SectorsClient, sqlite3.Connection]:
    if conn is None:
        conn = db.connect()
        db.init_schema(conn)
    return client or SectorsClient(conn), conn


def _symbols(conn: sqlite3.Connection) -> list[str]:
    return [row["symbol"] for row in conn.execute("SELECT symbol FROM companies ORDER BY symbol")]


def _day_after_latest(
    conn: sqlite3.Connection,
    table: str,
    column: str = "date",
    symbol: str | None = None,
) -> date | None:
    where = " WHERE symbol=?" if symbol is not None else ""
    params = (symbol,) if symbol is not None else ()
    latest = conn.execute(
        f"SELECT MAX(substr({column}, 1, 10)) FROM {table}{where}", params
    ).fetchone()[0]
    return date.fromisoformat(latest) + timedelta(days=1) if latest else None


def daily_calls(conn: sqlite3.Connection, today: date) -> list[Call]:
    """Calls that bring prices, flow, broker data, filings and events up to ``today``.

    Each window starts the day after the latest stored row, so a refresh after
    several missed days costs the same as a refresh after one.
    """
    end = today.isoformat()
    calls: list[Call] = []
    windows = [
        ("prices", "daily/{}", parsers.parse_prices, PRICE_WINDOW_DAYS),
        ("foreign_flow", "foreign-flow/{}", parsers.parse_foreign_flow, PRICE_WINDOW_DAYS),
        ("broker_summary", "broker-summary/{}", parsers.parse_broker_summary, BROKER_WINDOW_DAYS),
    ]
    for table, path, parse, max_days in windows:
        for symbol in _symbols(conn):
            start = _day_after_latest(conn, table, symbol=symbol) or today - timedelta(days=max_days)
            start = max(start, today - timedelta(days=max_days))
            if start > today:
                continue
            params = {"start": start.isoformat(), "end": end}
            calls.append(Call(path.format(symbol), params, 1, table, parse))

    # Filings arrive during the day, so the latest stored day is fetched again.
    filings_start = min(
        (_day_after_latest(conn, "filings", "timestamp") or today)
        - timedelta(days=1),
        today,
    )
    events_start = (today - timedelta(days=EVENTS_WINDOW_DAYS)).isoformat()
    events_end = (today + timedelta(days=EVENTS_WINDOW_DAYS)).isoformat()
    calls += [
        Call("filings", {"start": filings_start.isoformat(), "end": end, "limit": PAGE_LIMIT}, 1, "filings", parsers.parse_filings, paginated=True, force=True),
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


def weekly_calls(conn: sqlite3.Connection, today: date) -> list[Call]:
    """Holder mix for every symbol. Fundamentals are refreshed separately by ``fetch_universe``."""
    return [
        Call(f"company/shareholders-composition/{symbol}", {"year": today.year}, 1, "holder_mix", parsers.parse_holder_mix, force=True)
        for symbol in _symbols(conn)
    ]


def refresh_daily(
    client: SectorsClient | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> Report:
    """Append everything new since the last stored trading day.

    With ``dry_run`` nothing is fetched and ``Report.estimate`` holds the cost.
    """
    client, conn = _open(client, conn)
    calls = daily_calls(conn, today or date.today())
    if dry_run:
        return Report(estimate=estimate(client, calls))

    # Empty answers are still billed, so one price call checks for a new
    # trading day before the rest of the per-symbol calls are spent.
    market = [c for c in calls if c.table in ("prices", "foreign_flow", "broker_summary")]
    others = [c for c in calls if c not in market]
    report = Report()
    if market:
        price_calls = [call for call in market if call.table == "prices"]
        latest_price = conn.execute(
            "SELECT MAX(date) FROM prices"
        ).fetchone()[0]
        if not price_calls or latest_price == (today or date.today()).isoformat():
            report = run(client, conn, market)
        else:
            probe = price_calls[0]
            report = run(client, conn, [probe])
            if report.rows.get("prices"):
                rest = run(client, conn, [call for call in market if call is not probe])
                _merge(report, rest)
    _merge(report, run(client, conn, others))
    return report


def _merge(report: Report, other: Report) -> None:
    for table, count in other.rows.items():
        report.add(table, count)
    report.failures += other.failures
    report.credits += other.credits


def refresh_weekly(
    client: SectorsClient | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> Report:
    """Re-fetch fundamentals and holder mix, which change quarterly and monthly."""
    client, conn = _open(client, conn)
    calls = weekly_calls(conn, today or date.today())
    if dry_run:
        return Report(estimate=1 + estimate(client, calls))
    spent_before = ledger.credits_spent(conn)
    fetch_universe(client, conn, force=True)
    report = run(client, conn, calls)
    report.add("companies", len(_symbols(conn)))
    report.credits = ledger.credits_spent(conn) - spent_before
    return report


CHECKED_TABLES = {
    "prices": ["close", "volume", "market_cap"],
    "foreign_flow": ["net_foreign_inflow", "foreign_share"],
    "broker_summary": ["nval", "f_bval", "f_sval"],
    "holder_mix": ["shares_number", "individual_l", "individual_f", "numbers_of_shareholders"],
}


def check(conn: sqlite3.Connection) -> list[str]:
    """Data-quality report as printable lines: coverage, gaps and null rates."""
    symbols = _symbols(conn)
    lines = [f"universe: {len(symbols)} symbols"]
    for table, columns in CHECKED_TABLES.items():
        total, first, last, days = conn.execute(
            f"SELECT COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT date) FROM {table}"
        ).fetchone()
        lines.append(f"{table}: {total} rows, {first} to {last}, {days} dates")
        per_symbol = dict(conn.execute(f"SELECT symbol, COUNT(DISTINCT date) FROM {table} GROUP BY symbol").fetchall())
        short = sorted(s for s in symbols if per_symbol.get(s, 0) < days)
        if short:
            lines.append(f"  symbols with gaps: {', '.join(f'{s} ({per_symbol.get(s, 0)})' for s in short)}")
        for column in columns:
            nulls = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL").fetchone()[0]
            if nulls:
                lines.append(f"  {column}: {nulls / total:.0%} null")

    company_columns = [c for c in parsers.COMPANY_FIELDS]
    for column in company_columns:
        missing = [r["symbol"] for r in conn.execute(f"SELECT symbol FROM companies WHERE {column} IS NULL ORDER BY symbol")]
        if missing:
            lines.append(f"companies.{column}: null for {', '.join(missing)}")

    unknown = [r[0] for r in conn.execute(
        "SELECT DISTINCT broker_code FROM broker_summary WHERE broker_code NOT IN (SELECT code FROM brokers) ORDER BY 1"
    )]
    if unknown:
        lines.append(f"broker codes not in registry: {', '.join(unknown)}")
    for table, column in (("filings", "timestamp"), ("corporate_actions", "key_date"), ("suspensions", "date")):
        total, in_universe, last = conn.execute(
            f"SELECT COUNT(*), SUM(symbol IN (SELECT symbol FROM companies)), MAX(substr({column}, 1, 10)) FROM {table}"
        ).fetchone()
        lines.append(f"{table}: {total} rows, {in_universe or 0} in universe, latest {last}")
    return lines
