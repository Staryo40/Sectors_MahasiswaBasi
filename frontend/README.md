# React frontend

React 19, TypeScript in strict mode, and Vite. All views use declarative React components and state; the old imperative DOM application has been replaced.

From this folder:

```powershell
npm ci
npm run dev
```

Start FastAPI on port 8000 as described in the [project README](../README.md). Open `http://127.0.0.1:5173/?src=out` or `?src=fixtures`. The Vite development and preview servers proxy `/api` to FastAPI. Build with `npm run build`, then start or restart FastAPI to serve the build on port 8000.

## Where to read and edit

- `App.tsx` loads a snapshot and renders the shared workspace.
- `pages/` contains overview, daily/investor rankings, watchlist, stock research, market brief, and methodology views.
- `components/` contains shared scores, rows, icons and accessible SVG charts.
- `hooks/` handles hash navigation and browser watchlists, separated by source. The previous storage keys are preserved.
- `lib/api.ts` is the typed REST client. Requests abort when their consuming view unmounts.
- `types/contracts.ts` mirrors the backend JSON schemas; keep their key names unchanged.
- `styles/app.css` preserves the dashboard design and responsive layout.

Filters include symbol/company search, sector, signal, saved stocks, and rank order. Stock charts support 20/60/all windows, keyboard inspection, and observation tables; monthly ownership always shows its complete exported history. Brief downloads are local text files. No API credentials belong in this frontend.

## Verification

```powershell
npm run build
npm test
```

React Testing Library runs the actual React views in jsdom against fixture and existing market exports, mocking only HTTP responses. Weekly Python tests invoke the same checks. These verify interactions and data handling; they do not substitute for visual browser review.

For a judging walkthrough: overview → daily ranking and score explanation → save a stock → stock evidence and chart inspection → investor lens → watchlist → daily/weekly brief download. Date, source, and analysis-only wording stay visible.
