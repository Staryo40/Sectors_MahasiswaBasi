import { useEffect, useRef, useState } from "react";
import type { Snapshot } from "./types/contracts";
import { loadSnapshot, productionSnapshotSource } from "./lib/api";
import { format } from "./lib/format";
import { useRoute } from "./hooks/useRoute";
import { useWatchlist } from "./hooks/useWatchlist";
import { WatchlistContext, EmptyState } from "./components/common";
import { Icon } from "./components/Icon";
import { Overview } from "./pages/Overview";
import { Rankings } from "./pages/Rankings";
import { Watchlist } from "./pages/Watchlist";
import { StockDetail } from "./pages/StockDetail";
import { MarketBrief } from "./pages/MarketBrief";
import { Methodology } from "./pages/Methodology";

const navigation = [
  { view: "overview", title: "Overview", icon: "grid" },
  { view: "daily", title: "Daily flow", icon: "activity" },
  { view: "investor", title: "Investor lens", icon: "layers" },
  { view: "watchlist", title: "Watchlist", icon: "star" },
  { view: "changes", title: "Market brief", icon: "brief" },
  { view: "help", title: "Methodology", icon: "book" },
];

export function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    const requestedSource =
      new URLSearchParams(location.search).get("src") ||
      productionSnapshotSource;
    loadSnapshot(requestedSource, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setSnapshot(data);
      })
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to load the market snapshot.",
          );
      });
    return () => controller.abort();
  }, [attempt]);
  if (error)
    return (
      <main className="startup-state">
        <EmptyState title="Snapshot unavailable" note={error}>
          <button
            className="btn"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Retry
          </button>
          {import.meta.env.DEV && (
            <a className="btn" href="?src=fixtures">
              Open fixture demo
            </a>
          )}
        </EmptyState>
      </main>
    );
  if (!snapshot)
    return (
      <main className="startup-state" aria-busy="true">
        <div className="skeleton-hero">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
        <p role="status">Loading market snapshot…</p>
      </main>
    );
  return <Workspace key={snapshot.source} snapshot={snapshot} />;
}

function Workspace({ snapshot }: { snapshot: Snapshot }) {
  const { view, symbol } = useRoute();
  const watchlist = useWatchlist(
    snapshot.source,
    snapshot.daily.map((entry) => entry.symbol),
  );
  const [search, setSearch] = useState("");
  const searchInput = useRef<HTMLInputElement>(null);
  const previousView = useRef("daily");
  const title =
    view === "stock"
      ? symbol + " research"
      : navigation.find((item) => item.view === view)?.title || "Overview";
  useEffect(() => {
    document.title = title + " · Flow Radar";
    if (["daily", "investor", "watchlist"].includes(view))
      previousView.current = view;
  }, [view, title]);
  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        event.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName || "") &&
        !target?.isContentEditable
      ) {
        event.preventDefault();
        searchInput.current?.focus();
      }
    };
    window.addEventListener("keydown", onShortcut);
    return () => window.removeEventListener("keydown", onShortcut);
  }, []);
  const openStock = () => {
    const entered = search.trim().toUpperCase().replace(/\.JK$/, "");
    const found = snapshot.daily.find((entry) => entry.symbol === entered);
    if (found) {
      location.hash = "stock/" + found.symbol;
      setSearch("");
    }
  };
  let page;
  switch (view) {
    case "daily":
      page = <Rankings entries={snapshot.daily} horizon="daily" />;
      break;
    case "investor":
      page = <Rankings entries={snapshot.investor} horizon="investor" />;
      break;
    case "watchlist":
      page = <Watchlist snapshot={snapshot} />;
      break;
    case "stock":
      page = (
        <StockDetail
          key={snapshot.source + symbol}
          source={snapshot.source}
          symbol={symbol}
          backView={previousView.current}
        />
      );
      break;
    case "changes":
      page = <MarketBrief snapshot={snapshot} />;
      break;
    case "help":
      page = <Methodology />;
      break;
    default:
      page = <Overview snapshot={snapshot} />;
  }
  return (
    <WatchlistContext.Provider value={watchlist}>
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="Flow Radar overview">
          <img src="/mark.svg" width="36" height="36" alt="" />
          <span>
            flow<span className="brand-light">radar</span>
            <small>MARKET INTELLIGENCE</small>
          </span>
        </a>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav id="nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <a
              key={item.view}
              href={"#" + item.view}
              className={view === item.view ? "on" : ""}
              aria-current={view === item.view ? "page" : undefined}
            >
              <Icon name={item.icon} />
              {item.title}
              {item.view === "watchlist" && (
                <span className="nav-count">{watchlist.symbols.size}</span>
              )}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="universe-card">
            <span className="status-dot" />
            <b>{snapshot.meta.universe} universe</b>
            <p>{snapshot.meta.n_stocks} stocks · Two horizons</p>
            <span className="universe-tag">END-OF-DAY DATA</span>
          </div>
          <div className="powered">
            Built with <b>Sectors</b>
            <span>Financial API</span>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="top">
          <div className="top-row">
            <div className="workspace-title">
              <span>{title}</span>
              <span className="workspace-divider">/</span>
              <span className="muted">Indonesia equities</span>
            </div>
            <form
              className="jump"
              autoComplete="off"
              onSubmit={(event) => {
                event.preventDefault();
                openStock();
              }}
            >
              <Icon name="search" />
              <input
                ref={searchInput}
                list="symbols"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Find a stock…"
                aria-label="Find a stock by symbol"
              />
              <datalist id="symbols">
                {snapshot.daily.map((entry) => (
                  <option key={entry.symbol} value={entry.symbol}>
                    {entry.name}
                  </option>
                ))}
              </datalist>
              <kbd aria-hidden="true">/</kbd>
            </form>
          </div>
          <div className="freshness">
            <span className="status-dot" />
            <b>As of {format.date(snapshot.meta.as_of)}</b>
            <span>End-of-day snapshot</span>
            <span className="source-tag">
              {snapshot.source === "out"
                ? "EXPORTED MARKET DATA"
                : snapshot.source === "fixtures"
                  ? "ILLUSTRATIVE FIXTURES"
                  : "DEMO · PLACEHOLDER SCORES"}
            </span>
            <span className="analysis-note">
              Information and analysis only.
            </span>
          </div>
        </header>
        <div className="ticker" aria-label="Leading stocks">
          <span className="ticker-label">ON THE RADAR</span>
          {snapshot.daily.slice(0, 6).map((entry) => (
            <a key={entry.symbol} href={"#stock/" + entry.symbol}>
              <b>{entry.symbol}</b>
              <span>Rp {format.integer(entry.close)}</span>
              <span
                className={
                  "ticker-change " +
                  (entry.change_1d != null && entry.change_1d < 0
                    ? "negative"
                    : "positive")
                }
              >
                {format.signedPercent(entry.change_1d)}
              </span>
            </a>
          ))}
        </div>
        {snapshot.source !== "out" && (
          <div className="wrap banner">
            {snapshot.source === "fixtures"
              ? "Illustrative five-stock dataset for demonstration. These are sample scores."
              : "Demo data includes placeholder scores and ranks."}
          </div>
        )}
        {watchlist.storageNotice && (
          <p className="wrap banner" role="status">
            {watchlist.storageNotice}
          </p>
        )}
        <main className="wrap" id="main-content" tabIndex={-1}>
          {page}
        </main>
        <footer className="wrap foot">
          <div>
            <span className="footer-mark">◈</span>
            <b>Flow Radar</b>
            <span>Clarity behind the capital.</span>
          </div>
          <p>{snapshot.meta.disclaimer}</p>
          <p className="small muted">
            Sectors Financial API · End-of-day observations · Transparent,
            rules-based scores
          </p>
        </footer>
      </div>
    </WatchlistContext.Provider>
  );
}
