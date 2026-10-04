"""Export and scheduled radar runs; delivery defaults to dry-run."""
from __future__ import annotations

import argparse
import json
from contextlib import closing
from datetime import date
from pathlib import Path
from jsonschema.exceptions import ValidationError
from radar import config
from radar.db import connect
from radar.export.build_out import build
from radar.deliver import telegram, mailer
from radar.ingest import jobs


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m radar", description="SQLite radar pipeline")
    parser.add_argument("command", choices=("export", "run-daily", "run-weekly"))
    parser.add_argument("--as-of", help="YYYY-MM-DD; defaults to latest trading date in the database")
    parser.add_argument("--db", type=Path, default=config.DB_PATH)
    parser.add_argument("--out", type=Path, default=config.OUT_DIR)
    parser.add_argument("--skip-refresh", action="store_true", help="compute and deliver from existing SQLite rows")
    delivery = parser.add_mutually_exclusive_group()
    delivery.add_argument("--dry-run", dest="dry_run", action="store_true", default=True, help="print both channel messages (default)")
    delivery.add_argument("--send", dest="dry_run", action="store_false", help="opt in to actual Telegram and email delivery")
    args = parser.parse_args(argv)
    if args.as_of is not None:
        try:
            if date.fromisoformat(args.as_of).isoformat() != args.as_of:
                raise ValueError("Non-canonical date")
        except ValueError:
            parser.error("--as-of must be YYYY-MM-DD")
    if not args.db.is_file():
        parser.error(f"Database not found: {args.db}")
    try:
        if args.command != "export" and not args.skip_refresh:
            if args.db.resolve() != config.DB_PATH.resolve():
                raise RuntimeError("Refresh jobs target the default database; use --skip-refresh with a custom --db.")
            refreshes = ("refresh_daily", "refresh_weekly") if args.command == "run-weekly" else ("refresh_daily",)
            # Preflight both weekly jobs before allowing a partial refresh.
            if any(not callable(getattr(jobs, name, None)) for name in refreshes):
                raise RuntimeError("Agent A refresh jobs are not available; use --skip-refresh to run from SQLite.")
            for name in refreshes:
                spent = getattr(jobs, name)()
                print(f"{name}: {spent} credits spent")
        with closing(connect(args.db)) as db:
            as_of = args.as_of or db.execute("SELECT MAX(date) FROM prices").fetchone()[0]
            if as_of is None:
                raise RuntimeError("Database has no trading dates; specify --as-of.")
            build(db, as_of, args.out)
        print(f"Exported {as_of} to {args.out}")
        if args.command != "export":
            horizon = "weekly" if args.command == "run-weekly" else "daily"
            brief = json.loads((args.out / f"brief_{horizon}.json").read_text(encoding="utf-8"))
            text = telegram.format_brief(brief)
            errors = []
            for channel, sender in (("Telegram", lambda: telegram.send(text, dry_run=args.dry_run)),
                                    ("Email", lambda: mailer.send(f"Sectors Radar {horizon} — {as_of}", text, dry_run=args.dry_run))):
                try:
                    sender()
                except RuntimeError:
                    errors.append(channel)
            if errors:
                raise RuntimeError("Brief delivery failed on: " + ", ".join(errors))
        return 0
    except ValidationError:
        print("Pipeline failed: output did not validate against the UI schemas; no new export was published.")
        return 1
    except NotImplementedError:
        print("Pipeline blocked: an Agent B signal function is still a stub. See docs/agents/requests.md.")
        return 1
    except (RuntimeError, ValueError) as error:
        print(f"Pipeline failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
