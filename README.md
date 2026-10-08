# Flow Radar

Market intelligence for Indonesia’s LQ45 equities: daily capital flow, weekly investor scores, transparent stock evidence, and local market briefs. Sectors data powers the pipeline. Information and analysis only. Not investment advice.

## Project layout

```text
backend/
  radar/
    api/          FastAPI REST service
    ingest/       Local cache and Sectors ingestion
    signals/      Rules-based daily and investor scores
    export/       JSON generation and contract schemas
    deliver/      Telegram and email, dry-run by default
  scripts/        Explicit demo-data tools
frontend/
  src/
    components/   Shared React UI and SVG charts
    pages/        Overview, rankings, research, watchlist, briefs
    hooks/        Navigation and browser watchlist state
    lib/          Typed API client and display utilities
    types/        Existing JSON contracts in TypeScript
  public/         Local brand assets
fixtures/         Offline sample exports and synthetic inputs
data/            Local SQLite database and exported snapshots
tests/           Python verification; weekly tests also run React checks
```

Python packaging stays in the root `pyproject.toml`, with packages discovered under `backend/`. Tests and shared datasets stay at the root. `.env` stays at the root and is never committed. The database remains `data/sectors.db`; existing exported JSON keys and scoring interfaces are unchanged.

## Run locally

Requires Python 3.11+ and Node.js 22.12+ (or a supported newer version). Run these commands from the repository root in PowerShell.

Create a Python environment and install the backend:

```powershell
& 'C:\Python312\python.exe' -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Terminal 1 — start FastAPI:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn radar.api.app:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — start React:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173/?src=out** for the existing exported market data or **http://127.0.0.1:5173/?src=fixtures** for the clearly labelled five-stock demo. In development, without a source parameter, the UI tries market output, fixtures, then optional demo data. A production build defaults strictly to `out` and does not silently fall back to illustrative data. Vite forwards `/api` requests to FastAPI; no CORS setup is needed for this development flow.

API documentation: **http://127.0.0.1:8000/docs**. Health check: `GET /api/health`. The API reads local exports only; it does not refresh data, call Sectors, or send messages.

To regenerate local output without ingestion or delivery:

```powershell
& .\.venv\Scripts\python.exe -m radar export --db data/sectors.db --as-of 2026-10-02
```

Reload the browser after an export to load the new snapshot. Keep live API access disabled except during an explicit, reviewed refresh. Delivery commands remain dry-run by default.

## Freeze one market snapshot for deployment

The hosted product is intentionally read-only: it serves one final Sectors
snapshot and does not schedule API refreshes. After the market data for the
desired day is available, preview the cost and perform the one-time refresh
locally:

```powershell
& .\.venv\Scripts\python.exe -m radar.ingest refresh-daily
& .\.venv\Scripts\python.exe -m radar.ingest refresh-daily --yes
& .\.venv\Scripts\python.exe -m radar export --db data/sectors.db
```

The second command requires `SECTORS_API_KEY`, `SECTORS_LIVE=1`, and enough
`CREDIT_CAP` in the local `.env`. Review the printed estimate before adding
`--yes`. The export automatically selects the newest trading date stored in
SQLite. Verify `data/out/meta.json`, then commit the changed `data/out` JSON
files. Never commit `.env`, `data/sectors.db`, or `data/cache`.
If the current calendar day's market data is not available yet, pass the latest
known trading date explicitly, for example `refresh-daily --as-of 2026-10-07`.

### Vercel-only deployment

The root `vercel.json` deploys both parts of the public product:

- Vite builds the dashboard and copies the committed `data/out` files it needs
  to `/snapshots/out`. The browser reads them directly from the same Vercel
  domain, so no hosted FastAPI process is required.
- `api/telegram.ts` becomes the serverless Telegram webhook at
  `/api/telegram`. It reads the same frozen ranking and brief files and sends
  replies through the Telegram Bot API.

Import the GitHub repository in Vercel with the repository root as the project
root. The build and output settings are already in `vercel.json`; do not add
`VITE_API_BASE_URL`. Production defaults to the `out` snapshot. In **Settings
→ Environment Variables**, add these server-side secrets for Production:

```text
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_WEBHOOK_SECRET=<random letters/numbers/_/->
```

Generate a valid webhook secret locally if needed:

```powershell
& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Use the same values in the local root `.env`, deploy Vercel, then register the
deployed HTTPS endpoint with Telegram:

```powershell
.\scripts\set-telegram-webhook.ps1 -SiteUrl https://your-project.vercel.app
```

The script also prints Telegram's current webhook status. Opening
`https://your-project.vercel.app/api/telegram` should return a small health JSON.
Then send `/start`, `/daily`, or a ticker such as `PGEO` to the bot. The bot is
public, as currently requested; possession of the bot username is enough to
send it commands. `TELEGRAM_WEBHOOK_SECRET` authenticates Telegram-to-Vercel
requests and is not an end-user access restriction.

Do not use the old long-polling command while the webhook is active; Telegram
supports only one update-delivery method at a time. There is deliberately no
cron or hosted Sectors refresh. To publish a newer snapshot, refresh/export it
locally, commit `data/out`, and let Vercel redeploy. `Dockerfile`, `railway.json`,
and FastAPI remain available for local development or an optional future
backend, but they are not required by the live product.

## Build and serve from one process

```powershell
cd frontend
npm run build
cd ..
& .\.venv\Scripts\python.exe -m uvicorn radar.api.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

FastAPI serves `frontend/dist` when it exists at startup. Open **http://127.0.0.1:8000/?src=out**. Restart the backend if you create the build after starting it. Hash navigation works on reload.

## Verification

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/weekly
cd frontend
npm run build
npm test
```

Weekly tests cover scoring, exports, delivery, CLI, the REST contracts, and React interaction checks. Install frontend dependencies first so those interaction checks run. React checks exercise fixture and available market snapshots with local fetch mocks. See [frontend/README.md](frontend/README.md) and [backend/README.md](backend/README.md) for details.

Framework references: [React](https://react.dev/reference/react-dom/client/createRoot), [Vite](https://vite.dev/guide/), and [FastAPI](https://fastapi.tiangolo.com/tutorial/testing/).
