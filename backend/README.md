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
