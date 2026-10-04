import { useContext } from "react";
import type { Snapshot } from "../types/contracts";
import { EmptyState, PageHead, WatchlistContext } from "../components/common";
import { SignalRow } from "../components/SignalRow";

export function Watchlist({ snapshot }: { snapshot: Snapshot }) {
  const { symbols } = useContext(WatchlistContext);
  return (
    <>
      <PageHead
        kicker="YOUR SAVED RESEARCH"
        title="Keep your signals in sight."
        description="Saved in this browser, separately for each data source. Track the same stocks across both horizons."
      />
      {!symbols.size ? (
        <EmptyState
          title="Your watchlist starts here."
          note="Save a stock with the star beside its symbol."
        >
          <a className="btn primary" href="#daily">
            Explore daily flow
          </a>
        </EmptyState>
      ) : (
        <>
          <div className="section-head">
            <h2>Daily flow</h2>
            <span className="count">{symbols.size} saved stocks</span>
          </div>
          <div className="rows">
            {snapshot.daily
              .filter((entry) => symbols.has(entry.symbol))
              .map((entry) => (
                <SignalRow key={entry.symbol} entry={entry} />
              ))}
          </div>
          <div className="section-head">
            <h2>Investor lens</h2>
          </div>
          <div className="rows">
            {snapshot.investor
              .filter((entry) => symbols.has(entry.symbol))
              .map((entry) => (
                <SignalRow key={entry.symbol} entry={entry} />
              ))}
          </div>
        </>
      )}
    </>
  );
}
