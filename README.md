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

### Railway backend

`Dockerfile` and `railway.json` deploy only the read-only FastAPI service and
the committed `data/out` snapshot. No Sectors credential is required in the
hosted backend. Set this Railway variable after the Vercel domain is known:

```text
FRONTEND_ORIGINS=https://your-project.vercel.app
```

Multiple exact origins can be comma-separated. The image sets
`RADAR_ROOT=/app`, listens on Railway's `PORT`, runs as a non-root user, and
uses `/api/health` for its health check.

To keep the interactive Telegram bot online, create an optional second Railway
service from the same repository, override its start command to
`python -m radar bot --out data/out`, and set `TELEGRAM_BOT_TOKEN`. This worker
also reads only the frozen snapshot.

### Vercel frontend

The root `vercel.json` installs and builds the app from `frontend/`. Configure
these Vercel build variables, then redeploy:

```text
VITE_API_BASE_URL=https://your-service.up.railway.app
VITE_SNAPSHOT_SOURCE=out
```

Do not put `SECTORS_API_KEY`, Telegram credentials, or SMTP credentials in
Vercel. `VITE_*` values are public browser configuration. Once deployed, check
the Railway health endpoint, open the Vercel site without `?src=fixtures`, and
confirm that the displayed **As of** date matches `data/out/meta.json`.

There is deliberately no cron or GitHub Actions refresh workflow. To publish a
new snapshot later, repeat the local refresh/export, commit `data/out`, and
redeploy.

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
