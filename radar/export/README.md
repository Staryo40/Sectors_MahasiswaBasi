# Radar exports and scheduled runs

No command changes git. All output is deterministic SQLite-derived data, apart from the generation timestamp. No runtime dependencies beyond the declared jsonschema dependency were added.

## Export an existing database

`python -m radar export --as-of 2026-10-02 --db data/sectors.db`

Omit --as-of to use the latest date present in prices. Use --out PATH to select an output directory. Every contract file is validated before any file is published, then written through a temporary file and atomic rename. The final file replaced is meta.json. This is atomic per file, not a transaction across files; readers should reload after meta changes.

Each export also writes history/YYYY-MM-DD/ under the output directory. Comparison scores use an existing dated snapshot when available; otherwise daily is recomputed one trading day earlier and investor five trading days earlier. Company fundamentals have no historical observation dates, so recomputed comparisons use current fundamentals. Three monthly snapshots means the latest minus the oldest of the last three distinct months. Missing observations remain null; a wholly missing score has score zero and coverage zero. Financials coverage excludes the inapplicable debt input.

Holder series use percentages on 0–100; holder-shift components use fractions, with reason parameters in percentage points. Foreign-flow share preserves its stored database units. Filing transaction types are accumulation/distribution/others. Fixed buyers/sellers keys are retained as the contract requires. Brief items retain kind and include uppercase code.

## One-command brief

`python -m radar run-daily --dry-run`

`python -m radar run-weekly --dry-run`

Daily calls Agent A's refresh_daily(), then exports, then formats and prints the daily brief for Telegram and email. Weekly calls refresh_daily() followed by refresh_weekly(), exports, and uses the weekly brief. Jobs control their own cache and live-call gate; the runner never sets that gate. --dry-run controls delivery only. For a completely offline run, use --skip-refresh:

`python -m radar run-weekly --skip-refresh --dry-run --db data/sectors.db --as-of 2026-10-02`

Delivery is dry-run by default, including when --dry-run is omitted. Actual delivery requires --send. A channel without settings is skipped with a notice. Channel settings are read from .env without loading the ingestion live flag. Email uses STARTTLS; recipients are comma-separated EMAIL_TO addresses. No real send was performed during implementation.

## Cron (Linux host, Asia/Jakarta)

Use the host's cron timezone support or configure its timezone to Asia/Jakarta. Replace /path/to/project and /home/USER with the actual paths. These lines preview delivery; enable real delivery only when the team elects to use --send. Refresh jobs must be available, and uncached refresh requests remain subject to ingest's existing gate and credit cap.

```cron
CRON_TZ=Asia/Jakarta
30 18 * * 1-4 cd /path/to/project && /home/USER/.venvs/sectors-radar/bin/python -m radar run-daily --dry-run >> /path/to/project/radar.log 2>&1
30 18 * * 5 cd /path/to/project && /home/USER/.venvs/sectors-radar/bin/python -m radar run-weekly --dry-run >> /path/to/project/radar.log 2>&1
```

Run only `pytest tests/weekly` for Agent C checks. Real-database integration tests open the source read-only and substitute Agent B fixture outputs while its functions are stubs. They do not establish that B's daily score computation works. Synthetic integration is skipped when B's database is absent. Unpatched production runs need B's implemented functions and, for refresh commands, A's refresh jobs.
