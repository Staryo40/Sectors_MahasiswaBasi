import { createContext, useContext, type ReactNode } from "react";
import type { DailyEntry, InvestorEntry } from "../types/contracts";
import { LABELS, COMPONENTS, PILLARS, INPUTS, words } from "../lib/labels";
import { format } from "../lib/format";
import { Icon } from "./Icon";

export const WatchlistContext = createContext({
  symbols: new Set<string>(),
  toggle: (_symbol: string) => {},
});

export function WatchButton({ symbol }: { symbol: string }) {
  const { symbols, toggle } = useContext(WatchlistContext);
  const saved = symbols.has(symbol);
  return (
    <button
      type="button"
      className={"star-button" + (saved ? " saved" : "")}
      data-watch-symbol={symbol}
      aria-label={
        (saved ? "Remove " : "Save ") +
        symbol +
        (saved ? " from" : " to") +
        " watchlist"
      }
      aria-pressed={saved}
      onClick={() => toggle(symbol)}
    >
      <Icon name="star" />
    </button>
  );
}

export function PageHead({
  kicker,
  title,
  description,
  children,
}: {
  kicker: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">{kicker}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children && <div className="head-actions">{children}</div>}
    </div>
  );
}
export function EmptyState({
  title,
  note,
  children,
}: {
  title: string;
  note: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Icon name="search" />
      <h3>{title}</h3>
      <p>{note}</p>
      {children}
    </div>
  );
}
export function Badge({ label }: { label: string }) {
  const wording = LABELS[label] || { text: words(label), cls: "" };
  return (
    <span className="badge">
      <i className={"dot " + wording.cls} />
      {wording.text}
    </span>
  );
}
export function Avatar({
  symbol,
  large = false,
}: {
  symbol: string;
  large?: boolean;
}) {
  return (
    <span className={"avatar" + (large ? " large" : "")} aria-hidden="true">
      {symbol.slice(0, 2)}
    </span>
  );
}
export function RankChange({ entry }: { entry: DailyEntry | InvestorEntry }) {
  if (entry.rank_prev == null) return <span className="delta">New</span>;
  const change = entry.rank_prev - entry.rank;
  return (
    <span className={"delta " + (change > 0 ? "up" : change < 0 ? "down" : "")}>
      {change > 0 ? "↑ " : change < 0 ? "↓ " : "—"}
      {change ? Math.abs(change) : ""}
    </span>
  );
}
export function ScoreBar({
  value,
  signed = false,
  pillar = "",
}: {
  value: number | null;
  signed?: boolean;
  pillar?: string;
}) {
  return (
    <div
      className={"bar " + (signed ? "div" : "")}
      data-pillar={pillar}
      aria-hidden="true"
    >
      <i
        className={
          signed ? (value != null && value < 0 ? "neg" : "pos") : "mag"
        }
        style={{
          width: Math.min(100, Math.abs(value ?? 0)) / (signed ? 2 : 1) + "%",
          ...(signed
            ? {
                left:
                  value != null && value < 0
                    ? 50 - Math.min(100, Math.abs(value)) / 2 + "%"
                    : "50%",
              }
            : {}),
        }}
      />
    </div>
  );
}
export function Reasons({ entry }: { entry: DailyEntry | InvestorEntry }) {
  return (
    <ul className="reason-list">
      {entry.reasons.map((reason, index) => (
        <li key={reason.code + index}>{reason.text_en}</li>
      ))}
    </ul>
  );
}
export function FlowParts({ entry }: { entry: DailyEntry }) {
  return (
    <div className="parts">
      {entry.components.map((component) => (
        <div className="part" key={component.key}>
          <div>
            <span title={COMPONENTS[component.key]?.[1]}>
              {COMPONENTS[component.key]?.[0] || words(component.key)}
            </span>
            <div className="hint">
              Weight {format.percent(component.weight, 0)} · Normalized{" "}
              {format.signed(component.value, 2)}
            </div>
          </div>
          <b className="num">{format.signed(component.contribution)}</b>
        </div>
      ))}
    </div>
  );
}
export function PillarBars({ entry }: { entry: InvestorEntry }) {
  return (
    <div className="mini">
      {Object.entries(entry.pillars).map(([key, value]) => (
        <div key={key}>
          <div className="scoreline">
            <span title={PILLARS[key]?.[1]}>
              {PILLARS[key]?.[0] || words(key)}
            </span>
            <b className="num">{format.number(value)}</b>
          </div>
          <ScoreBar value={value} pillar={key} />
        </div>
      ))}
    </div>
  );
}
export function InvestorInputs({ entry }: { entry: InvestorEntry }) {
  return (
    <div className="scroll">
      <table className="data-table inputs-table">
        <thead>
          <tr>
            <th scope="col">Input</th>
            <th className="num" scope="col">Raw value</th>
            <th className="num" scope="col">Peer percentile</th>
          </tr>
        </thead>
        <tbody>
          {entry.components.map((component) => (
            <tr key={component.key}>
              <td>{INPUTS[component.key]?.[0] || words(component.key)}</td>
              <td className="num">
                {format.raw(component.raw, INPUTS[component.key]?.[1] || "")}
              </td>
              <td className="num">{format.percent(component.percentile, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
