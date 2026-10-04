import { useEffect, useState } from "react";
import type { Source, Stock } from "../types/contracts";
import { loadStock } from "../lib/api";
import { format } from "../lib/format";
import { INPUTS, words } from "../lib/labels";
import {
  Avatar,
  Badge,
  EmptyState,
  FlowParts,
  InvestorInputs,
  PillarBars,
  Reasons,
  WatchButton,
} from "../components/common";
import { Chart, type ChartSeries } from "../components/Chart";

type Range = 20 | 60 | "all";

function Brokers({
  title,
  rows,
}: {
  title: string;
  rows: Stock["top_brokers"]["buyers"];
}) {
  return (
    <section className="card">
      <h3>{title}</h3>
      {!rows.length ? (
        <p className="chart-unavailable">No broker observations available.</p>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Broker</th>
                <th>Cohort</th>
                <th>Net value (IDR)</th>
                <th>Average price</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.code}>
                  <td>
                    <b>{row.code}</b>
                    <div className="small muted">
                      {row.name}
                      {row.is_foreign ? " · Foreign" : ""}
                    </div>
                  </td>
                  <td>{words(row.cohort)}</td>
                  <td
                    className={
                      "num " + (row.net_value < 0 ? "negative" : "positive")
                    }
                  >
                    {format.rupiah(row.net_value)}
                  </td>
                  <td className="num">{format.number(row.avg_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Research({ stock, backView }: { stock: Stock; backView: string }) {
  const [range, setRange] = useState<Range>(60);
  const { daily, investor, series } = stock;
  const windowed = <T,>(rows: T[]): T[] =>
    range === "all" ? rows : rows.slice(-range);
  const price = windowed(series.price);
  const foreign = windowed(series.foreign_flow);
  const score = windowed(series.flow_score);
  const ownership: ChartSeries[] = [
    {
      name: "Institutional",
      points: series.holder_mix.map((point) => ({
        date: point.date,
        value: point.institutional_pct,
      })),
    },
    {
      name: "Individual",
      points: series.holder_mix.map((point) => ({
        date: point.date,
        value: point.individual_pct,
      })),
    },
    {
      name: "Foreign",
      points: series.holder_mix.map((point) => ({
        date: point.date,
        value: point.foreign_pct,
      })),
    },
  ];
  return (
    <>
      <div className="section-head research-back">
        <a className="text-link" href={"#" + backView}>
          ← Back to{" "}
          {backView === "investor"
            ? "investor lens"
            : backView === "watchlist"
              ? "your watchlist"
              : "daily flow"}
        </a>
        <span className="watch-action">
          <WatchButton symbol={stock.symbol} />
          <span className="small muted">Watchlist</span>
        </span>
      </div>
      <div className="page-head">
        <div className="stock-heading">
          <Avatar symbol={stock.symbol} large />
          <div>
            <div className="eyebrow">{daily.sector}</div>
            <h1>{stock.symbol}</h1>
            <p className="muted">{daily.name}</p>
          </div>
        </div>
        <div className="stock-price num">
          <strong>Rp {format.integer(daily.close)}</strong>
          <span
            className={
              daily.change_1d != null && daily.change_1d < 0
                ? "negative"
                : "positive"
            }
          >
            {format.signedPercent(daily.change_1d)} on the day
          </span>
        </div>
      </div>
      <div className="stock-context">
        <span>
          10-day return <b>{format.signedPercent(daily.return_10d)}</b>
        </span>
        <span>
          Relative volume{" "}
          <b>
            {daily.volume_ratio == null
              ? "–"
              : format.number(daily.volume_ratio) + "×"}
          </b>
        </span>
        <span>
          Daily rank <b>#{daily.rank}</b>
        </span>
        <span>
          Investor rank <b>#{investor.rank}</b>
        </span>
      </div>
      <div className="grid cols-2">
        <section className="card horizon-card">
          <div className="eyebrow">SHORTER HORIZON / DAILY</div>
          <div className="score-head">
            <h3>Flow score</h3>
            <Badge label={daily.label} />
          </div>
          <div className="big num">
            {format.signed(daily.flow_score)}
            <small> / 100</small>
          </div>
          <FlowParts entry={daily} />
          <Reasons entry={daily} />
        </section>
        <section className="card horizon-card">
          <div className="eyebrow">LONGER HORIZON / WEEKLY & MONTHLY</div>
          <div className="score-head">
            <h3>Investor score</h3>
            <span className="badge">
              Coverage {format.percent(investor.coverage, 0)}
            </span>
          </div>
          <div className="big num">
            {format.number(investor.investor_score)}
            <small> / 100</small>
          </div>
          <PillarBars entry={investor} />
          <Reasons entry={investor} />
          <details>
            <summary>Inspect every input</summary>
            <InvestorInputs entry={investor} />
          </details>
        </section>
      </div>
      <div className="section-head">
        <div>
          <h2>Evidence behind the signal</h2>
          <p>
            Trading charts use the selected window; ownership shows all monthly
            observations.
          </p>
        </div>
        <div className="chart-controls" aria-label="Chart window">
          {([20, 60, "all"] as const).map((option) => (
            <button
              key={option}
              type="button"
              className={range === option ? "on" : ""}
              aria-pressed={range === option}
              onClick={() => setRange(option)}
            >
              {option === "all" ? "All" : option + " sessions"}
            </button>
          ))}
        </div>
      </div>
      <div className="grid cols-2 chart-grid">
        <Chart
          title="Price"
          note="Closing price in IDR."
          formatValue={format.integer}
          series={[
            {
              name: "Close",
              points: price.map((point) => ({
                date: point.date,
                value: point.close,
              })),
            },
          ]}
        />
        <Chart
          title="Daily foreign flow"
          note="Net foreign flow in IDR; negative values show distribution."
          bars
          formatValue={format.rupiah}
          series={[
            {
              name: "Net flow",
              points: foreign.map((point) => ({
                date: point.date,
                value: point.net,
              })),
            },
          ]}
        />
        <Chart
          title="Cumulative foreign flow"
          note="Cumulative exported flow in IDR, starting at the export history boundary."
          formatValue={format.rupiah}
          series={[
            {
              name: "Cumulative flow",
              points: foreign.map((point) => ({
                date: point.date,
                value: point.cum,
              })),
            },
          ]}
        />
        <Chart
          title="Flow score history"
          note="Daily score on the same −100 to +100 scale."
          bounds={[-100, 100]}
          formatValue={format.signed}
          series={[
            {
              name: "Flow score",
              points: score.map((point) => ({
                date: point.date,
                value: point.score,
              })),
            },
          ]}
        />
        <Chart
          title="Ownership mix"
          note="Monthly ownership, in percentage points. Foreign ownership overlaps the other categories."
          bounds={[0, 100]}
          formatValue={(value) =>
            value == null ? "–" : format.number(value) + "%"
          }
          series={ownership}
        />
        <Chart
          title="Trading volume"
          note="Daily volume in shares."
          bars
          series={[
            {
              name: "Volume",
              points: price.map((point) => ({
                date: point.date,
                value: point.volume,
              })),
            },
          ]}
        />
      </div>
      <div className="section-head">
        <div>
          <h2>Broker activity</h2>
          <p>Net positions over the exported broker window.</p>
        </div>
      </div>
      <div className="grid cols-2">
        <Brokers title="Net accumulators" rows={stock.top_brokers.buyers} />
        <Brokers title="Net distributors" rows={stock.top_brokers.sellers} />
      </div>
      <div className="section-head">
        <h2>Company context</h2>
      </div>
      <div className="grid cols-2">
        <section className="card">
          <h3>Insider filings</h3>
          {stock.filings.length ? (
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Transaction</th>
                    <th>Holder</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.filings.map((filing, index) => (
                    <tr key={index}>
                      <td>{filing.date}</td>
                      <td>{words(filing.transaction_type)}</td>
                      <td>{words(filing.holder_type)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="chart-unavailable">No filings in this snapshot.</p>
          )}
        </section>
        <section className="card">
          <h3>Upcoming events</h3>
          {stock.events.length ? (
            <ul className="changes">
              {stock.events.map((event, index) => (
                <li key={index}>
                  <span>{event.date}</span>
                  <span>
                    <b>{words(event.type)}</b>
                    <br />
                    {event.detail}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="chart-unavailable">
              No upcoming events in this snapshot.
            </p>
          )}
        </section>
      </div>
      <div className="section-head">
        <h2>Fundamentals & peer context</h2>
      </div>
      <section className="card">
        {stock.fundamentals.length ? (
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Company</th>
                  <th>Peer average</th>
                  <th>Peer percentile</th>
                </tr>
              </thead>
              <tbody>
                {stock.fundamentals.map((input) => (
                  <tr key={input.key}>
                    <td>{INPUTS[input.key]?.[0] || words(input.key)}</td>
                    <td className="num">
                      {format.raw(input.value, INPUTS[input.key]?.[1] || "")}
                    </td>
                    <td className="num">
                      {format.raw(input.peer_avg, INPUTS[input.key]?.[1] || "")}
                    </td>
                    <td className="num">
                      {format.percent(input.percentile, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="chart-unavailable">No fundamentals available.</p>
        )}
      </section>
    </>
  );
}

export function StockDetail({
  source,
  symbol,
  backView,
}: {
  source: Source;
  symbol: string;
  backView: string;
}) {
  const [stock, setStock] = useState<Stock | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    loadStock(source, symbol, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setStock(data);
      })
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to load stock research.",
          );
      });
    return () => controller.abort();
  }, [source, symbol]);
  if (error)
    return (
      <EmptyState title={symbol + " research unavailable"} note={error}>
        <a className="btn" href={"#" + backView}>
          Back to rankings
        </a>
      </EmptyState>
    );
  if (!stock)
    return (
      <p role="status" className="card" aria-busy="true">
        Loading stock research…
      </p>
    );
  return <Research stock={stock} backView={backView} />;
}
