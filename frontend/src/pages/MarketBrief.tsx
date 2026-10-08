import type { Brief, Snapshot } from "../types/contracts";
import { downloadBrief, uniqueEvents } from "../lib/brief";
import { KINDS, words } from "../lib/labels";
import { format } from "../lib/format";
import { PageHead } from "../components/common";
import { Icon } from "../components/Icon";

function BriefPanel({
  brief,
  horizon,
}: {
  brief: Brief;
  horizon: "daily" | "weekly";
}) {
  const groups = [...new Set(brief.items.map((item) => item.kind))];
  return (
    <section className="card">
      <div className="brief-label">
        <Icon name={horizon === "daily" ? "activity" : "layers"} />
        <h3>{words(horizon)} changes</h3>
        <span className="badge">{brief.items.length} signals</span>
      </div>
      <p className="brief-date">{format.date(brief.as_of)}</p>
      {groups.length ? (
        groups.map((kind) => (
          <div key={kind}>
            <h4>{KINDS[kind] || words(kind)}</h4>
            <ul className="changes">
              {brief.items
                .filter((item) => item.kind === kind)
                .map((item, index) => (
                  <li key={index}>
                    <a className="sym" href={"#stock/" + item.symbol}>
                      {item.symbol}
                    </a>
                    <span>{item.text_en}</span>
                  </li>
                ))}
            </ul>
          </div>
        ))
      ) : (
        <p className="chart-unavailable">
          No material changes in this snapshot.
        </p>
      )}
    </section>
  );
}

export function MarketBrief({ snapshot }: { snapshot: Snapshot }) {
  const upcoming = uniqueEvents([snapshot.dailyBrief, snapshot.weeklyBrief]);
  return (
    <>
      <PageHead
        kicker="THE MARKET, EXPLAINED"
        title="What changed. What’s next."
        description="Computed changes across both horizons, with upcoming events in one place. Downloads stay local."
      >
        <button
          className="btn"
          onClick={() => downloadBrief(snapshot.dailyBrief, "daily")}
        >
          <Icon name="down" />
          Daily brief
        </button>
        <button
          className="btn"
          onClick={() => downloadBrief(snapshot.weeklyBrief, "weekly")}
        >
          <Icon name="down" />
          Weekly brief
        </button>
      </PageHead>
      <div className="grid cols-2">
        <BriefPanel brief={snapshot.dailyBrief} horizon="daily" />
        <BriefPanel brief={snapshot.weeklyBrief} horizon="weekly" />
      </div>
      <div className="section-head">
        <div>
          <h2>On the calendar</h2>
          <p>Unique events from both briefs.</p>
        </div>
      </div>
      <section className="card">
        {upcoming.length ? (
          <div className="scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Symbol</th>
                  <th scope="col">Event</th>
                </tr>
              </thead>
              <tbody>
                {upcoming.map((event) => (
                  <tr key={[event.date, event.symbol, event.type].join("|")}>
                    <td>{event.date}</td>
                    <td>
                      <a className="sym" href={"#stock/" + event.symbol}>
                        {event.symbol}
                      </a>
                    </td>
                    <td>{words(event.type)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="chart-unavailable">
            No upcoming events in this snapshot.
          </p>
        )}
      </section>
    </>
  );
}
