import { useContext, useMemo, useState } from "react";
import type { DailyEntry, Horizon, InvestorEntry } from "../types/contracts";
import { EmptyState, PageHead, WatchlistContext } from "../components/common";
import { isDaily, SignalRow } from "../components/SignalRow";

type Entry = DailyEntry | InvestorEntry;
export function Rankings({
  entries,
  horizon,
}: {
  entries: Entry[];
  horizon: Horizon;
}) {
  const { symbols } = useContext(WatchlistContext);
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [filter, setFilter] = useState("all");
  const [order, setOrder] = useState("rank");
  const daily = horizon === "daily";
  const filters: {
    key: string;
    title: string;
    test: (entry: Entry) => boolean;
  }[] = daily
    ? [
        { key: "all", title: "All", test: () => true },
        {
          key: "acc",
          title: "Accumulation",
          test: (entry) =>
            isDaily(entry) && entry.label.includes("accumulation"),
        },
        {
          key: "neu",
          title: "Neutral",
          test: (entry) => isDaily(entry) && entry.label === "neutral",
        },
        {
          key: "dist",
          title: "Distribution",
          test: (entry) =>
            isDaily(entry) && entry.label.includes("distribution"),
        },
        {
          key: "flag",
          title: "Flagged",
          test: (entry) => isDaily(entry) && entry.flags.length > 0,
        },
      ]
    : [
        { key: "all", title: "All", test: () => true },
        { key: "top", title: "Top 10", test: (entry) => entry.rank <= 10 },
        {
          key: "quality",
          title: "High quality",
          test: (entry) =>
            !isDaily(entry) && (entry.pillars.quality ?? 0) >= 60,
        },
        {
          key: "valuation",
          title: "High valuation score",
          test: (entry) =>
            !isDaily(entry) && (entry.pillars.valuation ?? 0) >= 60,
        },
        {
          key: "coverage",
          title: "High coverage",
          test: (entry) => !isDaily(entry) && entry.coverage >= 0.8,
        },
      ];
  filters.push({
    key: "saved",
    title: "Saved",
    test: (entry) => symbols.has(entry.symbol),
  });
  const sectors = useMemo(
    () =>
      [...new Set(entries.map((entry) => entry.sector).filter(Boolean))].sort(),
    [entries],
  );
  const query = search.trim().toLowerCase();
  const selectedFilter = filters.find((item) => item.key === filter)!;
  const shown = entries
    .filter(
      (entry) =>
        (!query ||
          (entry.symbol + " " + entry.name).toLowerCase().includes(query)) &&
        (!sector || entry.sector === sector) &&
        selectedFilter.test(entry),
    )
    .sort((a, b) => (order === "reverse" ? b.rank - a.rank : a.rank - b.rank));
  const reset = () => {
    setSearch("");
    setSector("");
    setFilter("all");
    setOrder("rank");
  };
  return (
    <>
      <PageHead
        kicker={
          daily
            ? "SHORTER HORIZON / DAILY"
            : "LONGER HORIZON / WEEKLY & MONTHLY"
        }
        title={daily ? "Where capital is moving." : "The longer view."}
        description={
          daily
            ? "Daily institutional, foreign, and broker flow. Scores run from −100 (distribution) to +100 (accumulation). Expand a row to see every contribution."
            : "Quality, valuation, and slow flow, scored 0 to 100. Updated weekly; ownership observations update monthly."
        }
      />
      <div className="tools">
        <input
          type="search"
          aria-label="Search stocks"
          placeholder="Search symbol or company"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="chips">
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              data-filter={item.key}
              className={"chip" + (filter === item.key ? " on" : "")}
              aria-pressed={filter === item.key}
              onClick={() => setFilter(item.key)}
            >
              {item.title}
            </button>
          ))}
        </div>
        <select
          aria-label="Sector"
          value={sector}
          onChange={(event) => setSector(event.target.value)}
        >
          <option value="">All sectors</option>
          {sectors.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <select
          aria-label="Order"
          value={order}
          onChange={(event) => setOrder(event.target.value)}
        >
          <option value="rank">Highest score first</option>
          <option value="reverse">Lowest score first</option>
        </select>
        <span className="count" aria-live="polite">
          {shown.length} of {entries.length} stocks
        </span>
      </div>
      <div className="list-meta">
        <span>Select a symbol to inspect its evidence.</span>
        <span>★ Save to your watchlist</span>
      </div>
      <div className="rows">
        {shown.length ? (
          shown.map((entry) => <SignalRow key={entry.symbol} entry={entry} />)
        ) : (
          <EmptyState
            title="No signals match just yet."
            note="Try another symbol, sector, or signal filter."
          >
            <button className="btn" onClick={reset}>
              Reset filters
            </button>
          </EmptyState>
        )}
      </div>
    </>
  );
}
