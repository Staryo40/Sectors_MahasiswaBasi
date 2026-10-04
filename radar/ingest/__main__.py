"""``python -m radar.ingest <command>``: probe, backfill, ledger."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from radar import config, db
from radar.ingest import jobs, ledger
from radar.ingest.client import SectorsClient, SectorsError

RAW_SAMPLES_DIR = config.FIXTURES_DIR / "raw_samples"
PROBE_SYMBOL = "BBCA"


def probe_calls(today: date) -> list[tuple[str, str, dict, int]]:
    """(sample name, path, params, cost): one call per endpoint the pipeline uses."""
    end = today.isoformat()
    d14 = (today - timedelta(days=14)).isoformat()
    d30 = (today - timedelta(days=30)).isoformat()
    d90 = (today - timedelta(days=90)).isoformat()
    ahead = (today + timedelta(days=30)).isoformat()
    universe = f"indices in ['{config.UNIVERSE_INDEX}']"
    return [
        ("companies", "companies", {"where": universe, "limit": 200, "include_query_values": "true"}, 1),
        ("brokers", "brokers", {}, 1),
        ("daily", f"daily/{PROBE_SYMBOL}", {"start": d90, "end": end}, 1),
        ("foreign_flow", f"foreign-flow/{PROBE_SYMBOL}", {"start": d90, "end": end}, 1),
        ("broker_summary", f"broker-summary/{PROBE_SYMBOL}", {"start": d14, "end": end}, 1),
        ("holder_mix", f"company/shareholders-composition/{PROBE_SYMBOL}", {"year": today.year}, 1),
        ("filings", "filings", {"start": d30, "end": end, "limit": 30}, 1),
        ("corporate_actions", "corporate-actions", {"start": d30, "end": ahead, "type": "dividend"}, 1),
        ("suspensions", "suspensions", {"start": d30, "end": end, "limit": 30}, 1),
        ("foreign_flow_universe", "foreign-flow", {"limit": 30}, 1),
    ]


def cmd_probe(args: argparse.Namespace) -> int:
    calls = probe_calls(date.today())
    conn = db.connect()
    db.init_schema(conn)
    client = SectorsClient(conn)

    uncached = [c for c in calls if client.cache.get(c[1], c[2]) is None]
    estimate = sum(cost for *_, cost in uncached)
    print(f"{len(calls)} probe calls, {len(uncached)} not cached, about {estimate} credits.")
    print(f"Spent so far: {ledger.credits_spent(conn)} of cap {client.credit_cap}.")
    if uncached and not client.live:
        print("SECTORS_LIVE is not 1, so uncached calls will be refused. Nothing done.")
        return 1
    if uncached and not args.yes:
        print("Re-run with --yes to spend the credits.")
        return 0

    RAW_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, path, params, cost in calls:
        try:
            body = client.get(path, params, cost)
        except SectorsError as err:
            failed += 1
            print(f"  FAILED  {name}: HTTP {err.status} {json.dumps(err.body)[:200]}")
            continue
        (RAW_SAMPLES_DIR / f"{name}.json").write_text(
            json.dumps({"path": path, "params": params, "body": body}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  saved   {name}")
    print(f"Spent so far: {ledger.credits_spent(conn)} of cap {client.credit_cap}.")
    return 1 if failed else 0


def cmd_backfill(args: argparse.Namespace) -> int:
    conn = db.connect()
    db.init_schema(conn)
    client = SectorsClient(conn)

    # The universe call (1 credit) is needed before the rest can be planned.
    universe_cached = client.cache.get("companies", jobs.universe_query()) is not None
    if not universe_cached and not (client.live and args.yes):
        print("Universe not cached. About 200 credits in total; re-run with --yes and SECTORS_LIVE=1.")
        return 0
    symbols = jobs.fetch_universe(client, conn)
    calls = jobs.backfill_calls(symbols, date.today())
    estimate = jobs.estimate(client, calls)
    print(f"{len(symbols)} symbols, {len(calls)} calls, about {estimate} credits (plus extra pages of filings).")
    print(f"Spent so far: {ledger.credits_spent(conn)} of cap {client.credit_cap}.")
    if estimate and not args.yes:
        print("Re-run with --yes to spend the credits.")
        return 0

    report = jobs.run(client, conn, calls)
    for table, count in sorted(report.rows.items()):
        print(f"  {table:<18} {count:>6} rows")
    for failure in report.failures:
        print(f"  FAILED  {failure}")
    print(f"Spent so far: {ledger.credits_spent(conn)} of cap {client.credit_cap}.")
    return 1 if report.failures else 0


def cmd_ledger(args: argparse.Namespace) -> int:
    conn = db.connect()
    db.init_schema(conn)
    print(f"Credits spent: {ledger.credits_spent(conn)} of cap {config.credit_cap()}")
    print(f"Live calls:    {ledger.live_calls(conn)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m radar.ingest")
    commands = parser.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", help="one call per endpoint, saved to fixtures/raw_samples/")
    probe.add_argument("--yes", action="store_true", help="actually spend the credits")
    probe.set_defaults(func=cmd_probe)

    backfill = commands.add_parser("backfill", help="fetch everything the scores need for the universe")
    backfill.add_argument("--yes", action="store_true", help="actually spend the credits")
    backfill.set_defaults(func=cmd_backfill)

    commands.add_parser("ledger", help="show credits spent").set_defaults(func=cmd_ledger)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
