# Backend

Python source lives under `radar/`. Install from the repository root with `python -m pip install -e '.[dev]'`. Existing imports and CLI commands still use `radar`.

Start from the repository root:

```powershell
python -m uvicorn radar.api.app:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

| Route | Data |
| --- | --- |
| `GET /api/health` | Service status and sources with metadata present |
| `GET /api/snapshots/{source}/meta` | Snapshot date, universe and disclaimer |
| `GET /api/snapshots/{source}/daily` | Daily flow ranking |
| `GET /api/snapshots/{source}/investor` | Investor ranking |
| `GET /api/snapshots/{source}/briefs/{horizon}` | Daily or weekly brief |
| `GET /api/snapshots/{source}/stocks/{symbol}` | Stock scores and research series |

Sources: `out` reads `data/out`; `fixtures` reads `fixtures/out`; `sample` reads optional `data/demo`. Horizon values are `daily` and `weekly`. Symbols are normalized to uppercase and exclude the .JK suffix. Missing data returns 404; invalid source, horizon, or symbol returns 422; unreadable or invalid exports return 503. All snapshot responses use `Cache-Control: no-store` and preserve the exported JSON shape.

The service validates exports against `radar/export/schemas` before returning them. It provides no refresh, delivery, or trading endpoints. Pipeline and delivery remain explicit CLI tasks. Built React assets are served from `frontend/dist` when present at startup.

The optional placeholder demo generator moved to `backend/scripts/generate_demo.py`; its output is clearly labelled and ignored by Git. Prefer real pipeline output or contract fixtures for demonstrations.

## Read-only production deployment

The production container serves the committed `data/out` snapshot. It does not
need `SECTORS_API_KEY`, does not contain `data/sectors.db`, and never refreshes
data through an HTTP request. Railway supplies `PORT`; the included Dockerfile
sets `RADAR_ROOT=/app` so the installed package resolves `/app/data/out`.

When the React frontend is hosted on another origin, set an exact comma-
separated allowlist, for example:

```text
FRONTEND_ORIGINS=https://flow-radar.vercel.app
```

If it is empty, CORS headers are not enabled. Do not use `*`; the frontend has
no need to send credentials and only configured origins should be allowed.

## Interactive Telegram bot

The bot uses long polling, accepts read-only commands from any Telegram chat,
and answers from an already exported snapshot. It never refreshes Sectors data
or places trades in response to a message.

```powershell
python -m radar bot --out data/out
```

Available commands: `/daily`, `/weekly`, `/brief daily`, `/brief weekly`,
`/stock PGEO`, `/top daily`, `/top investor`, and `/help`. A bare ticker such
as `PGEO` also opens the stock summary. Only `TELEGRAM_BOT_TOKEN` is required
for interactive replies; `TELEGRAM_CHAT_ID` remains the destination for
outbound briefs. On Railway, run the bot as a separate worker service with the
same image and override its start command to the command above. Stop a local
polling process with Ctrl+C.
