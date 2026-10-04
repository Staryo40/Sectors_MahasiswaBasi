"""Turn raw API responses into rows for the tables in schema.sql.

Each ``parse_*`` returns a list of dicts keyed by column name; ``upsert``
writes them. Symbols are stored without the ``.JK`` suffix.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Iterable

# Fiscal year used for the yearly screener fields (net margin, peer averages).
FUNDAMENTALS_YEAR = 2025

# companies column -> screener field
COMPANY_FIELDS = {
    "sector": "sector",
    "sub_sector": "sub_sector",
    "market_cap": "market_cap",
    "last_close": "last_close_price",
    "roe_ttm": "roe_ttm",
    "net_profit_margin": f"net_profit_margin[{FUNDAMENTALS_YEAR}]",
    "der_mrq": "der_mrq",
    "yoy_quarter_earnings_growth": "yoy_quarter_earnings_growth",
    "yoy_quarter_revenue_growth": "yoy_quarter_revenue_growth",
    "pe_ttm": "pe_ttm",
    "pb_mrq": "pb_mrq",
    "pe_peer_avg": f"pe_peer_avg[{FUNDAMENTALS_YEAR}]",
    "pb_peer_avg": f"pb_peer_avg[{FUNDAMENTALS_YEAR}]",
    "yield_ttm": "yield_ttm",
}

# corporate action type -> the date field the calendar filters on
CORPORATE_ACTION_DATE = {
    "dividend": "ex_date",
    "upcoming_dividend": "ex_date",
    "bonus": "ex_date",
    "right_issue": "ex_date",
    "stock_split": "date",
    "warrant": "trading_period_start",
    "agm": "agm_date",
}


def clean_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    return symbol[:-3] if symbol.endswith(".JK") else symbol


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_companies(body: dict) -> list[dict]:
    rows = []
    for item in body["results"]:
        values = item.get("query_values") or {}
        row = {"symbol": clean_symbol(item["symbol"]), "name": item.get("company_name")}
        row.update({column: values.get(field) for column, field in COMPANY_FIELDS.items()})
        row["raw_json"] = _dump(item)
        rows.append(row)
    return rows


def parse_brokers(body: list) -> list[dict]:
    return [
        {"code": b["code"], "name": b.get("name"), "is_foreign": int(bool(b.get("is_foreign"))), "cohort": b.get("cohort")}
        for b in body
    ]


def parse_prices(body: list) -> list[dict]:
    return [
        {
            "symbol": clean_symbol(r["symbol"]),
            "date": r["date"],
            "close": r.get("close"),
            "volume": r.get("volume"),
            "market_cap": r.get("market_cap"),
        }
        for r in body
    ]


def parse_foreign_flow(body: dict) -> list[dict]:
    symbol = clean_symbol(body["symbol"])
    return [
        {
            "symbol": symbol,
            "date": r["date"],
            "net_foreign_inflow": r.get("net_foreign_inflow"),
            "foreign_buy_idr": r.get("foreign_buy_idr"),
            "foreign_sell_idr": r.get("foreign_sell_idr"),
            "foreign_share": r.get("foreign_share"),
        }
        for r in body["data"]
    ]


def parse_foreign_flow_universe(body: dict) -> list[dict]:
    """Rows from the one-day full-universe feed, which has no ``foreign_share``."""
    return [
        {
            "symbol": clean_symbol(r["symbol"]),
            "date": r["date"],
            "net_foreign_inflow": r.get("net_foreign_inflow"),
            "foreign_buy_idr": r.get("foreign_buy_idr"),
            "foreign_sell_idr": r.get("foreign_sell_idr"),
            "foreign_share": r.get("foreign_share"),
        }
        for r in body["results"]
    ]


def parse_broker_summary(body: dict) -> list[dict]:
    symbol = clean_symbol(body["symbol"])
    columns = ("bval", "sval", "nval", "blot", "slot", "nlot", "bavg_per_share", "savg_per_share", "f_bval", "f_sval")
    rows = []
    for day in body["data"]:
        for entry in day["summary"]:
            row = {"symbol": symbol, "date": day["date"], "broker_code": entry["broker_code"]}
            row.update({column: entry.get(column) for column in columns})
            rows.append(row)
    return rows


def parse_holder_mix(body: dict) -> list[dict]:
    symbol = clean_symbol(body["symbol"])
    columns = ("shares_number", "individual_l", "individual_f", "total_l", "total_f", "numbers_of_shareholders")
    rows = []
    for snapshot in body["data"]:
        row = {"symbol": symbol, "date": snapshot["date"]}
        row.update({column: snapshot.get(column) for column in columns})
        row["raw_json"] = _dump(snapshot)
        rows.append(row)
    return rows


def parse_filings(body: dict) -> list[dict]:
    rows = []
    for item in body["results"]:
        if not item.get("symbol"):
            continue
        symbol = clean_symbol(item["symbol"])
        # The API gives no id; this one is stable across re-fetches.
        identity = [symbol, item.get("timestamp"), item.get("holder_name"), item.get("transaction_type"), item.get("amount_transaction")]
        rows.append(
            {
                "id": hashlib.sha1(_dump(identity).encode("utf-8")).hexdigest(),
                "symbol": symbol,
                "timestamp": item.get("timestamp"),
                "transaction_type": item.get("transaction_type"),
                "holder_type": item.get("holder_type"),
                "raw_json": _dump(item),
            }
        )
    return rows


def parse_corporate_actions(body: dict) -> list[dict]:
    rows = []
    for action_type, date_field in CORPORATE_ACTION_DATE.items():
        for item in body.get(action_type) or []:
            if not item.get(date_field):
                continue
            rows.append(
                {
                    "symbol": clean_symbol(item["symbol"]),
                    "type": action_type,
                    "key_date": item[date_field],
                    "raw_json": _dump(item),
                }
            )
    return rows


def parse_suspensions(body: dict) -> list[dict]:
    return [
        {
            "symbol": clean_symbol(r["symbol"]),
            "date": r["suspension_date"],
            "reason": r.get("reason"),
            "pdf_url": r.get("pdf_url"),
        }
        for r in body["results"]
    ]


def upsert(conn: sqlite3.Connection, table: str, rows: Iterable[dict]) -> int:
    """Insert or replace ``rows`` by primary key. Returns the number written."""
    rows = list(rows)
    if not rows:
        return 0
    columns = list(rows[0])
    sql = f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
    conn.executemany(sql, [[row[c] for c in columns] for row in rows])
    conn.commit()
    return len(rows)
