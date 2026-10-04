import type { DailyEntry, InvestorEntry } from "../types/contracts";
import { format } from "../lib/format";
import { FLAGS } from "../lib/labels";
import {
  Avatar,
  Badge,
  FlowParts,
  InvestorInputs,
  PillarBars,
  RankChange,
  Reasons,
  ScoreBar,
  WatchButton,
} from "./common";

export function isDaily(
  entry: DailyEntry | InvestorEntry,
): entry is DailyEntry {
  return "flow_score" in entry;
}

export function SignalRow({
  entry,
  compact = false,
}: {
  entry: DailyEntry | InvestorEntry;
  compact?: boolean;
}) {
  const daily = isDaily(entry);
  const score = daily ? entry.flow_score : entry.investor_score;
  if (compact)
    return (
      <div className="signal-row">
        <span className="rank">{entry.rank.toString().padStart(2, "0")}</span>
        <Avatar symbol={entry.symbol} />
        <div className="signal-identity">
          <a className="sym" href={"#stock/" + entry.symbol}>
            {entry.symbol}
          </a>
          <span className="name">{entry.name}</span>
          <p className="why">
            {entry.reasons[0]?.text_en ||
              "Inspect the underlying score inputs."}
          </p>
        </div>
        <div className="signal-number num">
          {daily ? format.signed(score) : format.number(score)}
          <small>{daily ? "FLOW SCORE" : "INVESTOR SCORE"}</small>
        </div>
        <WatchButton symbol={entry.symbol} />
      </div>
    );
  return (
    <article className={"row" + (daily ? "" : " inv")}>
      <div className="rank">
        {entry.rank}
        <RankChange entry={entry} />
      </div>
      <div className="identity">
        <Avatar symbol={entry.symbol} />
        <div>
          <a className="sym" href={"#stock/" + entry.symbol}>
            {entry.symbol}
          </a>
          <div className="name">{entry.name}</div>
          <div className="sector">{entry.sector}</div>
          {daily && (
            <div className="price">
              Rp {format.integer(entry.close)}{" "}
              <span
                className={
                  entry.change_1d != null && entry.change_1d < 0
                    ? "negative"
                    : "positive"
                }
              >
                {format.signedPercent(entry.change_1d)}
              </span>
            </div>
          )}
        </div>
      </div>
      <div>
        <div className="scoreline">
          <b className="num">
            {daily ? format.signed(score) : format.number(score)}
          </b>
          {daily ? (
            <Badge label={entry.label} />
          ) : (
            <span className="small muted">/ 100</span>
          )}
        </div>
        <ScoreBar value={score} signed={daily} />
        {daily ? (
          <div>
            {entry.flags.map((flag) => (
              <span className="flag" key={flag}>
                {FLAGS[flag] || flag}
              </span>
            ))}
          </div>
        ) : (
          <PillarBars entry={entry} />
        )}
      </div>
      <div className="why">
        <p>
          {entry.reasons[0]?.text_en || "No reason available in this snapshot."}
        </p>
        {!daily && (
          <p className="small muted">
            Input coverage {format.percent(entry.coverage, 0)}
          </p>
        )}
        <details>
          <summary>
            {daily ? "Explain this score" : "Inspect score inputs"}
          </summary>
          {daily ? (
            <FlowParts entry={entry} />
          ) : (
            <InvestorInputs entry={entry} />
          )}
          <Reasons entry={entry} />
        </details>
      </div>
      <WatchButton symbol={entry.symbol} />
    </article>
  );
}
