import { PageHead } from "../components/common";
import { COMPONENTS, PILLARS, INPUTS } from "../lib/labels";

export function Methodology() {
  return (
    <>
      <PageHead
        kicker="TRANSPARENT BY DESIGN"
        title="Understand every signal."
        description="Rules-based scores computed from Sectors data. The frontend displays the pipeline’s results; it does not generate scores."
      />
      <div className="grid cols-2">
        <section className="card method-card">
          <span className="method-number">01</span>
          <h2>Daily flow</h2>
          <p>
            Scores range from −100 to +100. Six normalized components contribute
            according to their weights. Missing observations contribute zero;
            the stock research view shows every contribution.
          </p>
          <div className="scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Label</th>
                  <th scope="col">Score threshold</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Strong accumulation</td>
                  <td>≥ +40</td>
                </tr>
                <tr>
                  <td>Accumulation</td>
                  <td>+15 to below +40</td>
                </tr>
                <tr>
                  <td>Neutral</td>
                  <td>−15 to below +15</td>
                </tr>
                <tr>
                  <td>Distribution</td>
                  <td>−40 to below −15</td>
                </tr>
                <tr>
                  <td>Strong distribution</td>
                  <td>Below −40</td>
                </tr>
              </tbody>
            </table>
          </div>
          {Object.entries(COMPONENTS).map(([key, [title, note]]) => (
            <div key={key}>
              <h4>{title}</h4>
              <p>{note}</p>
            </div>
          ))}
        </section>
        <section className="card method-card">
          <span className="method-number">02</span>
          <h2>Investor lens</h2>
          <p>
            Scores range from 0 to 100. Quality contributes 40%, valuation 25%,
            and slow flow 35%. Inputs use relative ranks within the available
            universe. Coverage reports the share of usable inputs.
          </p>
          {Object.entries(PILLARS).map(([key, [title, note]]) => (
            <div key={key}>
              <h4>{title}</h4>
              <p>{note}</p>
            </div>
          ))}
          <h4>What coverage means</h4>
          <p>
            A high score with incomplete data deserves closer inspection.
            Missing values appear as a dash, rather than a measured zero.
            Ownership observations update monthly, while the investor ranking
            updates weekly.
          </p>
          <h4>Reading peer context</h4>
          <p>
            Percentiles describe relative position within the dataset. Valuation
            comparisons use exported peer averages where available. A rank is an
            observation to investigate.
          </p>
        </section>
      </div>
      <div className="section-head">
        <h2>Reading the inputs</h2>
      </div>
      <section className="card">
        <div className="scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Input</th>
                <th scope="col">Display unit</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(INPUTS).map(([key, [title, unit]]) => (
                <tr key={key}>
                  <td>{title}</td>
                  <td>
                    {unit === "pct" || unit === "pct3"
                      ? "Percent"
                      : unit === "pp"
                        ? "Percentage points"
                        : unit === "x"
                          ? "Multiple"
                          : "Ratio"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="section-head">
        <h2>Limits of the evidence</h2>
      </div>
      <section className="card method-card">
        <p>
          End-of-day observations may lag current market conditions. Broker
          classifications are proxies for institutional activity, and foreign
          ownership overlaps holder categories. Flow can reflect many motives;
          historical signals do not establish future outcomes.
        </p>
        <p>
          All displayed figures come from the exported JSON. Information and
          analysis only. Not investment advice.
        </p>
      </section>
    </>
  );
}
