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

Open **http://127.0.0.1:5173/?src=out** for the existing exported market data or **http://127.0.0.1:5173/?src=fixtures** for the clearly labelled five-stock demo. Without a source parameter, the UI tries market output, fixtures, then optional demo data. Vite forwards `/api` requests to FastAPI; no CORS setup is needed for this development flow.

API documentation: **http://127.0.0.1:8000/docs**. Health check: `GET /api/health`. The API reads local exports only; it does not refresh data, call Sectors, or send messages.

To regenerate local output without ingestion or delivery:

```powershell
& .\.venv\Scripts\python.exe -m radar export --db data/sectors.db --as-of 2026-10-02
```

Reload the browser after an export to load the new snapshot. Keep live API access disabled. Delivery commands remain dry-run by default.

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
