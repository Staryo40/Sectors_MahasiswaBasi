"use strict";
// Reads the pipeline's output files. Looked for in this order; ?src=out|fixtures|sample pins one.
const SOURCES = { out: "../../data/out/", fixtures: "../../fixtures/out/", sample: "sample/" };
const pinned = new URLSearchParams(location.search).get("src");
let base = null;
const cache = new Map();
const app = document.getElementById("app");

// ---------- wording ----------
const LABELS = {
  strong_accumulation: { text: "Strong accumulation", cls: "pos strong" },
  accumulation: { text: "Accumulation", cls: "pos" },
  neutral: { text: "Neutral", cls: "" },
  distribution: { text: "Distribution", cls: "neg" },
  strong_distribution: { text: "Strong distribution", cls: "neg strong" },
};
const LABEL_ORDER = ["strong_accumulation", "accumulation", "neutral", "distribution", "strong_distribution"];
const LABEL_COLOR = { strong_accumulation: "var(--pos)", accumulation: "var(--pos)", neutral: "var(--flat)", distribution: "var(--neg)", strong_distribution: "var(--neg)" };
const LABEL_OPACITY = { strong_accumulation: 1, accumulation: 0.55, neutral: 1, distribution: 0.55, strong_distribution: 1 };

const COMPONENTS = {
  foreign_5d: ["Foreign flow, last 5 days", "Net foreign buying or selling over 5 trading days, compared with what is normal for this stock."],
  foreign_streak: ["Foreign flow streak", "How many days in a row foreign investors were net buyers or net sellers."],
  broker_concentration: ["Broker concentration", "Whether the three biggest net buyers outweigh the three biggest net sellers over the last two weeks."],
  institutional_net: ["Institutional brokers", "The net position of brokers classed as institutional over the last two weeks."],
  divergence: ["Flow against price", "Flow pointing one way while the price moved the other way over 10 days."],
  insider: ["Insider filings", "The balance of insider transactions reported in the last 30 days."],
};
const PILLARS = {
  quality: ["Quality", "Profitability and growth compared with the other stocks in the list."],
  valuation: ["Valuation", "Price multiples against peer averages, plus dividend yield."],
  slow_flow: ["Slow flow", "Foreign flow over 20 and 90 days, the monthly change in who holds the shares, and insider filings."],
};
const INPUTS = {
  roe_ttm: ["Return on equity", "pct"], net_profit_margin: ["Net profit margin", "pct"], der_mrq: ["Debt to equity", "x"],
  yoy_quarter_earnings_growth: ["Earnings growth, year on year", "pct"], yoy_quarter_revenue_growth: ["Revenue growth, year on year", "pct"],
  pe_ttm: ["Price to earnings", "x"], pb_mrq: ["Price to book", "x"], pe_relative: ["PE against peers", "x"], pb_relative: ["PB against peers", "x"],
  yield_ttm: ["Dividend yield", "pct"], foreign_20d: ["Foreign flow, 20 days (share of market cap)", "pct3"],
  foreign_90d: ["Foreign flow, 90 days (share of market cap)", "pct3"], holder_shift: ["Change in institutional share", "pp"], insider: ["Insider filings balance", "ratio"],
};
const FLAGS = {
  divergence_accumulation: "Accumulation while price fell", divergence_distribution: "Distribution while price rose", unusual_volume: "Unusual volume",
};
const KINDS = {
  new_top5: "Entered the top 5", score_flip: "Label changed", streak_started: "Streak started", streak_ended: "Streak ended",
  divergence: "Flow against price", insider_filing: "Insider filing", suspension: "Suspension", rank_mover: "Rank movers", holder_shift: "Holder shifts",
};
const words = v => { const t = String(v ?? "").replace(/_/g, " "); return t.charAt(0).toUpperCase() + t.slice(1); };

// ---------- helpers ----------
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v; else if (k.startsWith("on")) el.addEventListener(k.slice(2), v); else el.setAttribute(k, v);
  }
  for (const c of children.flat(4)) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}
function s(tag, attrs, ...children) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  for (const c of children.flat()) if (c != null) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}
const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const fmt = {
  num: (v, d = 1) => v == null ? "–" : Number(v).toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d }),
  int: v => v == null ? "–" : Math.round(v).toLocaleString("en"),
  big: v => v == null ? "–" : compact.format(v),
  idr: v => v == null ? "–" : "Rp " + compact.format(v),
  pct: (v, d = 1) => v == null ? "–" : (v * 100).toFixed(d) + "%",
  spct: (v, d = 2) => v == null ? "–" : (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%",
  signed: (v, d = 1) => v == null ? "–" : (v > 0 ? "+" : "") + Number(v).toFixed(d),
  date: iso => iso ? new Date(iso.slice(0, 10) + "T00:00:00Z").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "",
  shortDate: iso => iso ? new Date(iso.slice(0, 10) + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) : "",
  raw: (v, kind) => v == null ? "–" : kind === "pct" ? fmt.pct(v) : kind === "pct3" ? fmt.spct(v, 3) : kind === "pp" ? fmt.signed(v * 100, 2) + " pp" : kind === "x" ? fmt.num(v, 2) + "×" : fmt.signed(v, 2),
};
async function getJSON(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(base + name, { cache: "no-store" }).then(r => { if (!r.ok) throw new Error(`Could not load ${name}`); return r.json(); }));
  }
  return cache.get(name);
}
async function pickSource() {
  for (const key of pinned ? [pinned] : ["out", "fixtures", "sample"]) {
    if (!SOURCES[key]) continue;
    try { const r = await fetch(SOURCES[key] + "meta.json", { cache: "no-store" }); if (r.ok) { base = SOURCES[key]; return key; } } catch (e) { /* try the next one */ }
  }
  throw new Error("No data found yet. Run `python -m radar export` from the project folder, then reload.");
}

// ---------- small components ----------
function badge(label) {
  const l = LABELS[label] || { text: words(label), cls: "" };
  return h("span", { class: "badge" }, h("i", { class: "dot " + l.cls }), l.text);
}
function delta(e, what) {
  if (e.rank_prev == null) return h("span", { class: "delta", title: "New in the list" }, "new");
  const d = e.rank_prev - e.rank;
  if (d === 0) return h("span", { class: "delta", title: `Same rank as ${what}` }, "no change");
  return h("span", { class: "delta", title: `${d > 0 ? "Up" : "Down"} ${Math.abs(d)} place${Math.abs(d) > 1 ? "s" : ""} since ${what}` }, (d > 0 ? "▲ " : "▼ ") + Math.abs(d));
}
function divBar(value, max = 100) {
  const w = Math.min(Math.abs(value) / max, 1) * 50;
  return h("div", { class: "bar div", role: "img", "aria-label": `${fmt.signed(value)} on a scale of minus ${max} to ${max}` },
    h("i", { class: value >= 0 ? "pos" : "neg", style: `left:${value >= 0 ? 50 : 50 - w}%;width:${w}%` }));
}
function magBar(value, max = 100) {
  return h("div", { class: "bar", role: "img", "aria-label": `${fmt.num(value)} out of ${max}` }, h("i", { class: "mag", style: `left:0;width:${Math.max(0, Math.min(value / max, 1)) * 100}%` }));
}
const flagList = e => (e.flags || []).map(f => h("span", { class: "flag" }, FLAGS[f] || words(f)));
const reasonList = e => (e.reasons || []).length ? h("ul", { class: "reasons" }, e.reasons.map(r => h("li", {}, r.text_en))) : null;
const priceCell = e => h("div", { class: "price num" }, h("div", {}, fmt.int(e.close)), h("div", { class: "delta" }, fmt.spct(e.change_1d) + " today"));

function flowParts(e) {
  return h("div", { class: "parts" }, (e.components || []).map(c => {
    const [name, hint] = COMPONENTS[c.key] || [words(c.key), ""];
    return h("div", { class: "part" }, h("span", {}, name), divBar(c.contribution, 30), h("b", { class: "num" }, fmt.signed(c.contribution)), h("span", { class: "hint" }, hint));
  }));
}
function pillarBars(e) {
  return h("div", { class: "mini" }, Object.keys(PILLARS).map(k =>
    h("div", { class: "scoreline" }, h("span", {}, PILLARS[k][0]), magBar(e.pillars?.[k] ?? 0), h("span", { class: "num" }, fmt.num(e.pillars?.[k], 0)))));
}

function dailyRow(e, opts = {}) {
  const first = (e.reasons || [])[0];
  return h("div", { class: "row" },
    h("div", {}, h("div", { class: "rank num" }, e.rank), opts.compact ? null : delta(e, "the previous trading day")),
    h("div", {}, h("a", { class: "sym", href: "#stock/" + e.symbol }, e.symbol), h("div", { class: "name" }, e.name)),
    h("div", { class: "score" }, badge(e.label), h("div", { class: "scoreline", style: "margin-top:6px" }, h("b", { class: "num" }, fmt.signed(e.flow_score)), divBar(e.flow_score))),
    opts.compact ? null : priceCell(e),
    h("div", { class: "why" }, first ? first.text_en : "", h("div", {}, flagList(e))),
    opts.compact ? null : h("details", {}, h("summary", {}, "Why this score"), flowParts(e), reasonList(e)));
}
function investorRow(e, opts = {}) {
  const first = (e.reasons || [])[0];
  return h("div", { class: opts.compact ? "row" : "row inv" },
    h("div", {}, h("div", { class: "rank num" }, e.rank), opts.compact ? null : delta(e, "a week ago")),
    h("div", {}, h("a", { class: "sym", href: "#stock/" + e.symbol }, e.symbol), h("div", { class: "name" }, e.name)),
    h("div", { class: "score" }, h("div", { class: "scoreline" }, h("b", { class: "num" }, fmt.num(e.investor_score)), magBar(e.investor_score))),
    opts.compact ? null : pillarBars(e),
    h("div", { class: "why" }, first ? first.text_en : "", e.coverage < 1 ? h("div", { class: "delta" }, `Based on ${fmt.pct(e.coverage, 0)} of the usual inputs`) : null),
    opts.compact ? null : h("details", {}, h("summary", {}, "Why this score"), reasonList(e), inputTable(e)));
}
function inputTable(e) {
  return table([
    { title: "Input", cell: c => (INPUTS[c.key] || [words(c.key)])[0] },
    { title: "Part of", cell: c => (PILLARS[c.pillar] || [words(c.pillar)])[0] },
    { title: "Value", cls: "num", cell: c => fmt.raw(c.raw, (INPUTS[c.key] || [])[1]) },
    { title: "Better than", cls: "num", cell: c => c.percentile == null ? "–" : fmt.pct(c.percentile, 0) + " of list" },
  ], e.components || []);
}
function table(columns, rows) {
  return h("div", { class: "scroll" }, h("table", {},
    h("thead", {}, h("tr", {}, columns.map(c => h("th", { class: c.cls }, c.title)))),
    h("tbody", {}, rows.map(r => h("tr", {}, columns.map(c => h("td", { class: c.cls }, c.cell(r))))))));
}

// ---------- charts: one y axis each, crosshair tooltip, table view ----------
function chart(title, note, series, opts = {}) {
  const W = 560, H = 210, m = { t: 10, r: opts.endLabels ? 92 : 12, b: 24, l: 54 };
  const xs = series[0].points.map(p => p.x), n = xs.length, format = opts.format || fmt.big;
  const card = h("div", { class: "card" }, h("h3", {}, title), note ? h("p", { class: "chart-note" }, note) : null);
  if (!n) { card.append(h("p", { class: "muted" }, "No data.")); return card; }

  const values = series.flatMap(q => q.points.map(p => p.y)).filter(v => v != null);
  let lo = Math.min(...values), hi = Math.max(...values);
  if (opts.bars || opts.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  if (opts.domain) [lo, hi] = opts.domain;
  else {
    if (lo === hi) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.06; hi += pad; if (!(opts.bars && lo === 0)) lo -= pad;
  }
  const step = (W - m.l - m.r) / Math.max(n - (opts.bars ? 0 : 1), 1);
  const X = i => m.l + (opts.bars ? (i + 0.5) * step : i * step);
  const Y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);

  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title });
  for (let k = 0; k <= 3; k++) {
    const v = lo + (hi - lo) * k / 3, y = Y(v);
    svg.append(s("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: "var(--grid)" }),
               s("text", { x: m.l - 6, y: y + 4, "text-anchor": "end", "font-size": 11, fill: "var(--text-3)" }, format(v)));
  }
  if (lo < 0 && hi > 0) svg.append(s("line", { x1: m.l, x2: W - m.r, y1: Y(0), y2: Y(0), stroke: "var(--text-3)" }));
  svg.append(s("text", { x: m.l, y: H - 6, "font-size": 11, fill: "var(--text-3)" }, fmt.shortDate(xs[0])),
             s("text", { x: W - m.r, y: H - 6, "text-anchor": "end", "font-size": 11, fill: "var(--text-3)" }, fmt.shortDate(xs[n - 1])));
  if (opts.bars) {
    const w = Math.max(step - 2, 1);
    series[0].points.forEach((p, i) => {
      if (p.y == null) return;
      const y0 = Y(0), y1 = Y(p.y);
      svg.append(s("rect", { x: X(i) - w / 2, y: Math.min(y0, y1), width: w, height: Math.max(Math.abs(y1 - y0), 1), rx: Math.min(2, w / 2),
                             fill: opts.diverging ? (p.y >= 0 ? "var(--pos)" : "var(--neg)") : series[0].color }));
    });
  } else {
    for (const q of series) {
      const d = q.points.map((p, i) => p.y == null ? "" : `${i && q.points[i - 1].y != null ? "L" : "M"}${X(i).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
      svg.append(s("path", { d, fill: "none", stroke: q.color, "stroke-width": 2, "stroke-linejoin": "round" }));
      const last = q.points[n - 1];
      if (opts.endLabels && last.y != null) svg.append(s("text", { x: X(n - 1) + 6, y: Y(last.y) + 4, "font-size": 11, fill: "var(--text-2)" }, q.name));
    }
  }
  const hair = s("line", { y1: m.t, y2: H - m.b, stroke: "var(--text-3)", "stroke-dasharray": "3 3", visibility: "hidden" });
  svg.append(hair);
  const tip = h("div", { class: "tip" }), box = h("div", { class: "chart" }, svg, tip);
  svg.addEventListener("pointermove", ev => {
    const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * W;
    const i = Math.min(Math.max(opts.bars ? Math.floor((x - m.l) / step) : Math.round((x - m.l) / step), 0), n - 1);
    hair.setAttribute("x1", X(i)); hair.setAttribute("x2", X(i)); hair.setAttribute("visibility", "visible");
    tip.replaceChildren(h("div", { class: "muted" }, fmt.date(xs[i])), ...series.map(q => h("div", {},
      h("span", { class: "key", style: `border-color:${opts.diverging ? (q.points[i].y >= 0 ? "var(--pos)" : "var(--neg)") : q.color}` }),
      h("b", { class: "num" }, format(q.points[i].y)), " ", q.name)));
    tip.style.display = "block";
    tip.style.left = Math.min(Math.max(X(i) / W * box.clientWidth + 10, 0), box.clientWidth - tip.offsetWidth - 2) + "px";
    tip.style.top = "6px";
  });
  svg.addEventListener("pointerleave", () => { hair.setAttribute("visibility", "hidden"); tip.style.display = "none"; });

  if (series.length > 1) card.append(h("div", { class: "legend" }, series.map(q => h("span", {}, h("span", { class: "key", style: `border-color:${q.color}` }), q.name))));
  if (opts.diverging) card.append(h("div", { class: "legend" },
    h("span", {}, h("span", { class: "sw", style: "background:var(--pos)" }), "Net buying"), h("span", {}, h("span", { class: "sw", style: "background:var(--neg)" }), "Net selling")));
  card.append(box, h("details", { class: "more" }, h("summary", {}, "Show as table"),
    table([{ title: "Date", cell: i => fmt.date(xs[i]) }, ...series.map(q => ({ title: words(q.name), cls: "num", cell: i => format(q.points[i].y) }))], xs.map((_, i) => i).reverse())));
  return card;
}
const pts = (rows, key) => rows.map(r => ({ x: r.date, y: r[key] }));

// ---------- views ----------
function labelMix(daily) {
  const counts = Object.fromEntries(LABEL_ORDER.map(k => [k, daily.filter(e => e.label === k).length]));
  return h("div", { class: "card" }, h("h3", {}, "Where the list stands today"),
    h("div", { class: "mix", role: "img", "aria-label": LABEL_ORDER.map(k => `${counts[k]} ${LABELS[k].text}`).join(", ") },
      LABEL_ORDER.filter(k => counts[k]).map(k => h("i", { style: `flex:${counts[k]};background:${LABEL_COLOR[k]};opacity:${LABEL_OPACITY[k]}`, title: `${LABELS[k].text}: ${counts[k]}` }))),
    h("div", { class: "legend" }, LABEL_ORDER.map(k => h("span", {}, h("span", { class: "sw", style: `background:${LABEL_COLOR[k]};opacity:${LABEL_OPACITY[k]}` }), `${LABELS[k].text} ${counts[k]}`))));
}
function changeItems(items, limit) {
  const shown = limit ? items.slice(0, limit) : items;
  return h("ul", { class: "changes" }, shown.map(i => h("li", {}, i.symbol ? h("a", { class: "sym", href: "#stock/" + i.symbol }, i.symbol) : h("span", {}), h("span", {}, i.text_en))));
}

async function viewOverview() {
  const [meta, daily, investor, brief] = await Promise.all([getJSON("meta.json"), getJSON("daily.json"), getJSON("investor.json"), getJSON("brief_daily.json")]);
  const acc = daily.filter(e => e.flow_score > 0).slice(0, 5);
  const dist = [...daily].reverse().filter(e => e.flow_score < 0).slice(0, 5);
  const nAcc = daily.filter(e => e.label.includes("accumulation")).length, nDist = daily.filter(e => e.label.includes("distribution")).length;
  return [
    h("h1", {}, "Who is quietly buying, and who is selling?"),
    h("p", { class: "muted" }, `Flow Radar reads broker, foreign-investor, insider and shareholder data for the ${meta.n_stocks} ${meta.universe} stocks and turns it into two ranked lists: a daily one for flow, and a slower one for investors.`),
    h("div", { class: "grid tiles", style: "margin-top:16px" },
      h("div", { class: "card tile" }, h("div", { class: "big num" }, nAcc), h("div", { class: "cap" }, "stocks under accumulation")),
      h("div", { class: "card tile" }, h("div", { class: "big num" }, nDist), h("div", { class: "cap" }, "stocks under distribution")),
      h("div", { class: "card tile" }, h("div", { class: "big" }, daily[0]?.symbol || "–"), h("div", { class: "cap" }, `strongest flow today (${fmt.signed(daily[0]?.flow_score)})`)),
      h("div", { class: "card tile" }, h("div", { class: "big" }, investor[0]?.symbol || "–"), h("div", { class: "cap" }, `top of the investor list (${fmt.num(investor[0]?.investor_score)})`))),
    h("div", { style: "margin-top:14px" }, labelMix(daily)),
    h("div", { class: "grid cols-2 compact", style: "margin-top:4px" },
      h("section", {}, h("h2", {}, "Strongest accumulation"), h("div", { class: "rows" }, acc.length ? acc.map(e => dailyRow(e, { compact: true })) : h("p", { class: "muted" }, "No stock has a positive flow score today."))),
      h("section", {}, h("h2", {}, "Strongest distribution"), h("div", { class: "rows" }, dist.length ? dist.map(e => dailyRow(e, { compact: true })) : h("p", { class: "muted" }, "No stock has a negative flow score today.")))),
    h("p", { style: "margin-top:10px" }, h("a", { href: "#daily" }, `See all ${daily.length} stocks in the daily flow list →`)),
    h("div", { class: "grid cols-2" },
      h("section", {}, h("h2", {}, "What changed since the previous trading day"),
        h("div", { class: "card" }, (brief.items || []).length ? changeItems(brief.items, 7) : h("p", { class: "muted" }, "Nothing notable changed."),
          (brief.items || []).length > 7 ? h("p", { style: "margin:10px 0 0" }, h("a", { href: "#changes" }, `All ${brief.items.length} changes →`)) : null)),
      h("section", { class: "compact" }, h("h2", {}, "For investors: top of the weekly list"),
        h("div", { class: "rows" }, investor.slice(0, 4).map(e => investorRow(e, { compact: true }))),
        h("p", { style: "margin-top:10px" }, h("a", { href: "#investor" }, "See the full investor list →")))),
  ];
}

function listView({ data, title, intro, row, filters }) {
  const state = { q: "", filter: "all", sector: "", sort: "rank" };
  const sectors = [...new Set(data.map(e => e.sector).filter(Boolean))].sort();
  const rows = h("div", { class: "rows" }), count = h("span", { class: "count" });
  const draw = () => {
    const q = state.q.trim().toLowerCase();
    let shown = data.filter(e => (!q || e.symbol.toLowerCase().includes(q) || (e.name || "").toLowerCase().includes(q))
      && (!state.sector || e.sector === state.sector) && (filters[state.filter]?.test || (() => true))(e));
    if (state.sort === "reverse") shown = [...shown].reverse();
    rows.replaceChildren(...(shown.length ? shown.map(e => row(e)) : [h("p", { class: "muted" }, "No stock matches these filters.")]));
    count.textContent = `${shown.length} of ${data.length} stocks`;
  };
  const chips = h("div", { class: "chips" }, Object.entries(filters).map(([key, f]) => {
    const b = h("button", { class: "chip" + (key === "all" ? " on" : ""), type: "button", onclick: () => {
      state.filter = key; chips.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c === b)); draw(); } }, f.text);
    return b;
  }));
  draw();
  return [h("h1", {}, title), h("p", { class: "muted" }, intro),
    h("div", { class: "tools" },
      h("input", { type: "search", placeholder: "Search symbol or name", "aria-label": "Search", oninput: ev => { state.q = ev.target.value; draw(); } }), chips,
      h("select", { "aria-label": "Sector", onchange: ev => { state.sector = ev.target.value; draw(); } }, h("option", { value: "" }, "All sectors"), sectors.map(x => h("option", { value: x }, x))),
      h("select", { "aria-label": "Order", onchange: ev => { state.sort = ev.target.value; draw(); } }, h("option", { value: "rank" }, "Top of list first"), h("option", { value: "reverse" }, "Bottom of list first")),
      count), rows];
}
async function viewDaily() {
  return listView({ data: await getJSON("daily.json"), title: "Daily flow list",
    intro: "Every stock ranked by flow score, from −100 (heavy distribution) to +100 (heavy accumulation). The score updates after each trading day. Open “Why this score” to see what it is made of.",
    row: e => dailyRow(e),
    filters: { all: { text: "All" }, acc: { text: "Accumulation", test: e => e.label.includes("accumulation") }, neu: { text: "Neutral", test: e => e.label === "neutral" },
               dist: { text: "Distribution", test: e => e.label.includes("distribution") }, flag: { text: "Flagged", test: e => (e.flags || []).length > 0 } } });
}
async function viewInvestor() {
  return listView({ data: await getJSON("investor.json"), title: "Investor list",
    intro: "A slower ranking for longer horizons, scored 0 to 100. It combines company quality, valuation against peers, and whether large holders have been adding over weeks and months. It changes weekly; the shareholder data behind it updates monthly.",
    row: e => investorRow(e),
    filters: { all: { text: "All" }, top: { text: "Top 10", test: e => e.rank <= 10 }, q: { text: "High quality", test: e => (e.pillars?.quality ?? 0) >= 60 },
               v: { text: "Good value", test: e => (e.pillars?.valuation ?? 0) >= 60 }, f: { text: "Being accumulated", test: e => (e.pillars?.slow_flow ?? 0) >= 60 } } });
}

function brokerTable(rows, close) {
  return table([
    { title: "Broker", cell: b => [h("b", {}, b.code), " ", b.name || ""] },
    { title: "Type", cell: b => `${words(b.cohort)}, ${b.is_foreign ? "foreign" : "domestic"}` },
    { title: "Net value", cls: "num", cell: b => fmt.idr(b.net_value) },
    { title: "Avg price", cls: "num", cell: b => fmt.int(b.avg_price) },
    { title: "Price now vs avg", cls: "num", cell: b => b.avg_price && close ? fmt.spct(close / b.avg_price - 1, 1) : "–" },
  ], rows || []);
}
async function viewStock(symbol) {
  let d;
  try { d = await getJSON(`stocks/${encodeURIComponent(symbol)}.json`); }
  catch (e) { return [h("h1", {}, symbol), h("p", { class: "muted" }, "This stock is not in the list. Use the search box at the top to pick one.")]; }
  const [daily, investor] = await Promise.all([getJSON("daily.json"), getJSON("investor.json")]);
  const day = d.daily || {}, inv = d.investor || {}, sr = d.series || {};
  const scale = (sr.holder_mix || []).some(r => r.institutional_pct > 1.5) ? 1 : 100;
  const mix = (sr.holder_mix || []).map(r => ({ date: r.date, institutional_pct: r.institutional_pct * scale, individual_pct: r.individual_pct * scale, foreign_pct: r.foreign_pct * scale }));
  const fund = d.fundamentals || [];
  return [
    h("p", { class: "small", style: "margin-top:16px" }, h("a", { href: "#daily" }, "← Daily flow list")),
    h("h1", { style: "margin-top:4px" }, d.symbol, " ", h("span", { class: "muted", style: "font-weight:400;font-size:18px" }, day.name || inv.name || "")),
    h("p", { class: "muted" }, [day.sector || inv.sector, `Last close ${fmt.int(day.close)}`, `${fmt.spct(day.change_1d)} on the day`, `${fmt.spct(day.return_10d)} over 10 days`,
      day.volume_ratio != null ? `volume ${fmt.num(day.volume_ratio, 1)}× its usual level` : null].filter(Boolean).join(" · ")),
    h("div", { class: "grid cols-2" },
      h("div", { class: "card" },
        h("h3", {}, "Daily flow"),
        h("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" }, h("span", { class: "tile" }, h("span", { class: "big num" }, fmt.signed(day.flow_score))), badge(day.label),
          h("span", { class: "muted small" }, `Rank ${day.rank} of ${daily.length}`), delta(day, "the previous trading day")),
        h("div", { style: "margin:10px 0 2px" }, divBar(day.flow_score ?? 0)),
        h("div", {}, flagList(day)), reasonList(day),
        h("h3", { style: "margin-top:16px" }, "What the score is made of"), h("p", { class: "muted small" }, "Each bar is that signal's contribution, in points. Right of centre adds to accumulation, left adds to distribution."),
        flowParts(day)),
      h("div", { class: "card" },
        h("h3", {}, "Investor view"),
        h("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" }, h("span", { class: "tile" }, h("span", { class: "big num" }, fmt.num(inv.investor_score))),
          h("span", { class: "muted small" }, `out of 100 · rank ${inv.rank} of ${investor.length}`), delta(inv, "a week ago")),
        h("div", { style: "margin:10px 0 12px" }, magBar(inv.investor_score ?? 0)),
        pillarBars(inv), reasonList(inv),
        inv.coverage < 1 ? h("p", { class: "muted small", style: "margin-top:8px" }, `Based on ${fmt.pct(inv.coverage, 0)} of the usual inputs; the rest are not reported for this company.`) : null,
        h("details", { class: "more", style: "margin-top:10px" }, h("summary", {}, "Show every input"), inputTable(inv)))),
    h("h2", {}, "Price and flow over time"),
    h("div", { class: "grid cols-3" },
      chart("Price", "Daily close, in rupiah.", [{ name: "close", color: "var(--series-1)", points: pts(sr.price || [], "close") }], { format: fmt.int }),
      chart("Foreign investors, each day", "Net buying or selling by foreign investors, in rupiah.", [{ name: "net foreign flow", points: pts(sr.foreign_flow || [], "net") }], { bars: true, diverging: true }),
      chart("Foreign investors, running total", "The daily figures added up since the start of the window.", [{ name: "cumulative net flow", color: "var(--series-1)", points: pts(sr.foreign_flow || [], "cum") }], { zero: true }),
      chart("Flow score history", "The daily flow score over the last 20 trading days.", [{ name: "flow score", color: "var(--series-1)", points: pts(sr.flow_score || [], "score") }], { zero: true, format: v => fmt.signed(v, 0) }),
      chart("Who holds the shares", "Monthly snapshots, as a share of all shares.", [
        { name: "institutions", color: "var(--series-1)", points: pts(mix, "institutional_pct") },
        { name: "individuals", color: "var(--series-2)", points: pts(mix, "individual_pct") },
        { name: "foreign", color: "var(--series-3)", points: pts(mix, "foreign_pct") }], { endLabels: true, domain: [0, 100], format: v => fmt.num(v, 0) + "%" }),
      chart("Trading volume", "Shares traded each day.", [{ name: "volume", color: "var(--series-1)", points: pts(sr.price || [], "volume") }], { bars: true })),
    h("h2", {}, "Which brokers moved it"),
    h("p", { class: "muted" }, `Net buying and selling per broker over the last two weeks. “Price now vs avg” compares the last close (${fmt.int(day.close)}) with what that broker paid or received on average.`),
    h("div", { class: "grid cols-2" },
      h("div", { class: "card" }, h("h3", {}, "Biggest net buyers"), brokerTable(d.top_brokers?.buyers, day.close)),
      h("div", { class: "card" }, h("h3", {}, "Biggest net sellers"), brokerTable(d.top_brokers?.sellers, day.close))),
    h("div", { class: "grid cols-2" },
      h("section", {}, h("h2", {}, "Insider filings, last 30 days"), h("div", { class: "card" }, (d.filings || []).length
        ? table([{ title: "Date", cell: f => fmt.date(f.date) }, { title: "Transaction", cell: f => words(f.transaction_type) }, { title: "Filed by", cell: f => words(f.holder_type) }], d.filings)
        : h("p", { class: "muted", style: "margin:0" }, "No insider filings in the last 30 days."))),
      h("section", {}, h("h2", {}, "Events"), h("div", { class: "card" }, (d.events || []).length
        ? table([{ title: "Date", cell: e => fmt.date(e.date) }, { title: "Event", cell: e => words(e.type) }, { title: "Detail", cell: e => words(e.detail) }], d.events)
        : h("p", { class: "muted", style: "margin:0" }, "No dividends, rights issues or stock splits in the 30 days either side of today.")))),
    h("h2", {}, "Fundamentals"),
    h("div", { class: "card" }, table([
      { title: "Measure", cell: f => (INPUTS[f.key] || [words(f.key)])[0] },
      { title: "This company", cls: "num", cell: f => fmt.raw(f.value, (INPUTS[f.key] || [])[1] === "pct" ? "pct" : "x") },
      { title: "Peer average", cls: "num", cell: f => f.peer_avg == null ? "" : fmt.num(f.peer_avg, 2) + "×" },
      { title: "Better than", cls: "num", cell: f => f.percentile == null ? "not reported" : fmt.pct(f.percentile, 0) + " of list" },
      { title: "", cell: f => f.percentile == null ? "" : magBar(f.percentile * 100) },
    ], fund)),
  ];
}

function groupedChanges(brief) {
  const groups = new Map();
  for (const item of brief.items || []) { if (!groups.has(item.kind)) groups.set(item.kind, []); groups.get(item.kind).push(item); }
  if (!groups.size) return [h("div", { class: "card" }, h("p", { class: "muted", style: "margin:0" }, "Nothing notable changed."))];
  return [h("div", { class: "grid cols-2" }, [...groups].map(([kind, items]) => h("div", { class: "card" }, h("h3", {}, `${KINDS[kind] || words(kind)} (${items.length})`), changeItems(items))))];
}
async function viewChanges() {
  const [daily, weekly] = await Promise.all([getJSON("brief_daily.json"), getJSON("brief_weekly.json")]);
  const upcoming = [...(daily.upcoming || []), ...(weekly.upcoming || [])];
  return [
    h("h1", {}, "What changed"),
    h("p", { class: "muted" }, "The same summary that goes out as the daily and weekly brief on Telegram and email."),
    h("h2", {}, `Since the previous trading day (${fmt.date(daily.as_of)})`), groupedChanges(daily),
    h("h2", {}, `Over the past week (${fmt.date(weekly.as_of)})`), groupedChanges(weekly),
    h("h2", {}, "Coming up"),
    h("div", { class: "card" }, upcoming.length
      ? table([{ title: "Date", cell: u => fmt.date(u.date) }, { title: "Stock", cell: u => h("a", { href: "#stock/" + u.symbol }, u.symbol) }, { title: "Event", cell: u => words(u.type) }], upcoming)
      : h("p", { class: "muted", style: "margin:0" }, "No dividends, rights issues or stock splits scheduled for these stocks in the next 30 days.")),
  ];
}

function viewHelp() {
  const gloss = pairs => h("dl", { class: "gloss" }, pairs.map(([t, d]) => [h("dt", {}, t), h("dd", {}, d)]));
  return [
    h("h1", {}, "How to read this"),
    h("p", { class: "muted" }, "Flow Radar shows what large investors have been doing in each stock. It does not tell you what to do, and a high score is not a prediction."),
    h("h2", {}, "The two lists"),
    h("div", { class: "grid cols-2" },
      h("div", { class: "card" }, h("h3", {}, "Daily flow list"), h("p", {}, "For people watching short-term moves. Each stock gets a flow score from −100 to +100, updated after every trading day."),
        h("p", { class: "muted", style: "margin:0" }, "Above zero means large investors have been net buyers (accumulation). Below zero means they have been net sellers (distribution).")),
      h("div", { class: "card" }, h("h3", {}, "Investor list"), h("p", {}, "For longer horizons. Each stock gets a score from 0 to 100 built from three parts, each a comparison with the other stocks in the list."),
        h("p", { class: "muted", style: "margin:0" }, "It moves slowly: fundamentals change quarterly and shareholder data monthly."))),
    h("h2", {}, "What the flow score is made of"), h("div", { class: "card" }, gloss(Object.values(COMPONENTS))),
    h("h2", {}, "What the investor score is made of"), h("div", { class: "card" }, gloss(Object.values(PILLARS))),
    h("h2", {}, "Labels and flags"),
    h("div", { class: "card" }, gloss([
      ...LABEL_ORDER.map(k => [badge(k), { strong_accumulation: "Flow score of +40 or more.", accumulation: "Flow score from +15 to +40.", neutral: "Flow score between −15 and +15.",
                                         distribution: "Flow score from −40 to −15.", strong_distribution: "Flow score of −40 or less." }[k]]),
      [h("span", { class: "flag" }, FLAGS.divergence_accumulation), "Large investors were net buyers while the price was flat or falling."],
      [h("span", { class: "flag" }, FLAGS.divergence_distribution), "Large investors were net sellers while the price was flat or rising."],
      [h("span", { class: "flag" }, FLAGS.unusual_volume), "The day's volume was more than twice the stock's 20-day median."]])),
    h("h2", {}, "Words used here"),
    h("div", { class: "card" }, gloss([
      ["Accumulation", "Large investors buying more than they sell over a period."],
      ["Distribution", "Large investors selling more than they buy over a period."],
      ["Foreign flow", "Buying minus selling by foreign investors, counted by who the investor is, whichever broker they used."],
      ["Institutional broker", "A broker whose clients are mostly funds and institutions, as opposed to retail traders."],
      ["Better than … of list", "The share of the other stocks in the list that this stock beats on that measure."]])),
    h("h2", {}, "Limits"),
    h("div", { class: "card" }, h("ul", { class: "reasons", style: "margin:0" },
      h("li", {}, "Data is end of day. Nothing here is live."),
      h("li", {}, "The list covers the LQ45 index only."),
      h("li", {}, "Broker data covers the last two weeks; prices and foreign flow cover about three months."),
      h("li", {}, "A broker's flow shows which broker executed the trades, not who the end client was."))),
  ];
}

// ---------- shell ----------
const VIEWS = { overview: viewOverview, daily: viewDaily, investor: viewInvestor, changes: viewChanges, help: viewHelp, briefs: viewChanges };
async function route() {
  const [name, arg] = (location.hash.slice(1) || "overview").split("/");
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.view === (name === "stock" ? "daily" : name)));
  try {
    const nodes = await (name === "stock" ? viewStock((arg || "").toUpperCase()) : (VIEWS[name] || viewOverview)());
    app.replaceChildren(...nodes.flat(4).filter(Boolean));
  } catch (err) {
    app.replaceChildren(h("p", { class: "error", style: "margin-top:20px" }, String(err.message || err)));
  }
  window.scrollTo(0, 0);
}

(async () => {
  try {
    const source = await pickSource();
    const [meta, daily] = await Promise.all([getJSON("meta.json"), getJSON("daily.json")]);
    const fresh = document.getElementById("freshness");
    fresh.replaceChildren("Data as of ", h("b", {}, fmt.date(meta.as_of)), `, end of day · ${meta.universe}, ${meta.n_stocks} stocks`);
    if (source !== "out") fresh.append(h("div", { class: "banner" },
      source === "sample" ? "Sample data: the scores, ranks and reasons on this page are placeholders, not real results." : "Example data from test fixtures, not real results."));
    document.getElementById("disclaimer").textContent = meta.disclaimer;
    document.getElementById("symbols").replaceChildren(...daily.map(e => h("option", { value: e.symbol }, e.name)));
    const jump = ev => {
      ev.preventDefault();
      const value = document.getElementById("jump-input").value.trim().toUpperCase();
      if (daily.some(e => e.symbol === value)) { location.hash = "stock/" + value; document.getElementById("jump-input").value = ""; }
    };
    document.getElementById("jump").addEventListener("submit", jump);
    document.getElementById("jump-input").addEventListener("change", jump);
    window.addEventListener("hashchange", route);
    route();
  } catch (err) {
    app.replaceChildren(h("p", { class: "error", style: "margin-top:20px" }, String(err.message || err)));
  }
})();
