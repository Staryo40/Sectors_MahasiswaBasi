import { useEffect, useState } from "react";
import type {
  DailyEntry,
  InvestorEntry,
  Snapshot,
  Stock,
} from "../types/contracts";
import { loadStock } from "../lib/api";
import { format } from "../lib/format";
import { LABELS, LABEL_ORDER, LABEL_COLOR } from "../lib/labels";
import { SignalRow } from "../components/SignalRow";
import { Sparkline } from "../components/Chart";
import { Icon } from "../components/Icon";

function Board({
  title,
  kicker,
  entries,
  href,
  distribution = false,
}: {
  title: string;
  kicker: string;
  entries: (DailyEntry | InvestorEntry)[];
  href: string;
  distribution?: boolean;
}) {
  return (
    <section className={"board" + (distribution ? " distribution-board" : "")}>
      <div className="board-head">
        <div>
          <div className="eyebrow">{kicker}</div>
          <h3>{title}</h3>
        </div>
        <span className="board-icon">
          <Icon name={distribution ? "activity" : "layers"} />
        </span>
      </div>
      <div className="board-body">
        {entries.length ? (
          entries.map((entry) => (
            <SignalRow key={entry.symbol} entry={entry} compact />
          ))
        ) : (
          <p className="board-empty">No matching signals in this snapshot.</p>
        )}
      </div>
      <div className="board-foot">
        <a className="text-link" href={href}>
          Explore the full ranking <Icon name="arrow" />
        </a>
      </div>
    </section>
  );
}

export function Overview({ snapshot }: { snapshot: Snapshot }) {
  const { daily, investor, meta, dailyBrief } = snapshot;
  const [leaderStock, setLeaderStock] = useState<Stock | null>(null);
  const leader = daily[0];
  useEffect(() => {
    if (!leader) return;
    const controller = new AbortController();
    loadStock(snapshot.source, leader.symbol, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setLeaderStock(data);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [snapshot.source, leader?.symbol]);
  const accumulated = daily.filter((entry) =>
    entry.label.includes("accumulation"),
  ).length;
  const distributed = daily.filter((entry) =>
    entry.label.includes("distribution"),
  ).length;
  const metrics = [
    {
      caption: "Under accumulation",
      value: accumulated,
      sub: "Flow scores of +15 or higher",
      icon: "trend",
      tag: daily.length
        ? format.percent(accumulated / daily.length, 0) + " of universe"
        : "No observations",
    },
    {
      caption: "Under distribution",
      value: distributed,
      sub: "Flow scores below −15",
      icon: "activity",
      tag: daily.length
        ? format.percent(distributed / daily.length, 0) + " of universe"
        : "No observations",
    },
    {
      caption: "Leading daily signal",
      value: leader?.symbol || "—",
      sub: leader
        ? "Flow score " + format.signed(leader.flow_score)
        : "No daily observations",
      icon: "globe",
      tag: "DAILY",
    },
    {
      caption: "Leading investor signal",
      value: investor[0]?.symbol || "—",
      sub: investor[0]
        ? "Investor score " +
          format.number(investor[0].investor_score) +
          " / 100"
        : "No investor observations",
      icon: "layers",
      tag: "WEEKLY",
    },
  ];
  const history = leaderStock?.series.flow_score || [];
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">INDONESIA EQUITIES / {meta.universe}</div>
          <h1>
            Follow the flow.
            <br />
            <span>See the whole picture.</span>
          </h1>
          <p>
            Track where large investors are accumulating, understand what drives
            each signal, and connect today’s flow with the longer view.
          </p>
          <div className="hero-actions">
            <a className="btn primary" href="#daily">
              Explore daily flow <Icon name="arrow" />
            </a>
            <a className="btn" href="#investor">
              <Icon name="layers" />
              Investor lens
            </a>
          </div>
        </div>
        {leader && (
          <div className="spotlight">
            <div className="spotlight-heading">
              <span className="eyebrow">HIGHEST DAILY FLOW SCORE</span>
              <Icon name="activity" />
            </div>
            <div className="spotlight-title">
              <div>
                <a
                  className="spotlight-symbol"
                  href={"#stock/" + leader.symbol}
                >
                  {leader.symbol}
                </a>
                <div className="spotlight-name">{leader.name}</div>
              </div>
              <div className="spotlight-score num">
                {format.signed(leader.flow_score)}
                <small>FLOW SCORE · −100 TO +100</small>
              </div>
            </div>
            <Sparkline
              points={history.map((point) => ({
                date: point.date,
                value: point.score,
              }))}
            />
            <div className="sparkline-note">
              <span>{history[0]?.date}</span>
              <span>{history.at(-1)?.date}</span>
            </div>
            <p className="spotlight-reason">
              {leader.reasons[0]?.text_en ||
                "Inspect the component scores behind this rank."}
            </p>
            <a className="text-link" href={"#stock/" + leader.symbol}>
              Explore the evidence <Icon name="arrow" />
            </a>
          </div>
        )}
      </section>
      <div className="grid tiles">
        {metrics.map((metric, index) => (
          <div className="card tile" key={metric.caption}>
            <div className="tile-top">
              <span className="cap">{metric.caption}</span>
              <Icon name={metric.icon} />
            </div>
            <div className="metric-value">
              <div className="big num">{metric.value}</div>
              <span className={"pill" + (index === 1 ? " neg" : "")}>
                {metric.tag}
              </span>
            </div>
            <div className="sub">{metric.sub}</div>
          </div>
        ))}
      </div>
      <section className="card breadth">
        <div>
          <h3>The balance of flow</h3>
          <p>{daily.length} stocks · Daily signal distribution</p>
        </div>
        <div className="breadth-chart">
          <div
            className="mix"
            role="img"
            aria-label={LABEL_ORDER.map(
              (label) =>
                LABELS[label].text +
                ": " +
                daily.filter((entry) => entry.label === label).length,
            ).join(", ")}
          >
            {LABEL_ORDER.map((label) => (
              <i
                key={label}
                style={{
                  width:
                    (daily.length
                      ? (daily.filter((entry) => entry.label === label).length /
                          daily.length) *
                        100
                      : 0) + "%",
                  background: LABEL_COLOR[label],
                  opacity: label.startsWith("strong") ? 1 : 0.55,
                }}
              />
            ))}
          </div>
          <div className="legend">
            {LABEL_ORDER.map((label) => (
              <span className="key" key={label}>
                <i className="sw" style={{ background: LABEL_COLOR[label] }} />
                {LABELS[label].text}{" "}
                <b>{daily.filter((entry) => entry.label === label).length}</b>
              </span>
            ))}
          </div>
        </div>
      </section>
      <div className="section-head">
        <div>
          <h2>One market. Two horizons.</h2>
          <p>Every rank comes with its reasons. Choose your view.</p>
        </div>
        <a className="text-link" href="#help">
          How scores work <Icon name="arrow" />
        </a>
      </div>
      <div className="grid cols-2">
        <Board
          title="Daily flow leaders"
          kicker="01 / SHORTER HORIZON"
          entries={daily.slice(0, 5)}
          href="#daily"
        />
        <Board
          title="The investor shortlist"
          kicker="02 / LONGER HORIZON"
          entries={investor.slice(0, 5)}
          href="#investor"
        />
      </div>
      <div className="section-head">
        <div>
          <h2>Beyond the headline</h2>
          <p>Distribution signals and the changes worth investigating.</p>
        </div>
        <a className="text-link" href="#changes">
          Read market brief <Icon name="arrow" />
        </a>
      </div>
      <div className="grid cols-2">
        <Board
          title="Strongest distribution"
          kicker="THE OTHER SIDE OF FLOW"
          entries={[...daily]
            .sort((a, b) => a.flow_score - b.flow_score)
            .filter((entry) => entry.flow_score < 0)
            .slice(0, 3)}
          href="#daily"
          distribution
        />
        <section className="board">
          <div className="board-head">
            <div>
              <div className="eyebrow">LATEST / DAILY BRIEF</div>
              <h3>What changed</h3>
            </div>
            <span className="board-icon">
              <Icon name="brief" />
            </span>
          </div>
          <div className="board-body">
            {dailyBrief.items.length ? (
              <ul className="changes">
                {dailyBrief.items.slice(0, 5).map((item, index) => (
                  <li key={index}>
                    <a className="sym" href={"#stock/" + item.symbol}>
                      {item.symbol}
                    </a>
                    <span>{item.text_en}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="board-empty">
                No material changes in this snapshot.
              </p>
            )}
          </div>
          <div className="board-foot">
            <a className="text-link" href="#changes">
              Read the full brief <Icon name="arrow" />
            </a>
          </div>
        </section>
      </div>
    </>
  );
}
