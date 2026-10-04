export const LABELS: Record<string, { text: string; cls: string }> = {
  strong_accumulation: { text: "Strong accumulation", cls: "pos strong" },
  accumulation: { text: "Accumulation", cls: "pos" },
  neutral: { text: "Neutral", cls: "" },
  distribution: { text: "Distribution", cls: "neg" },
  strong_distribution: { text: "Strong distribution", cls: "neg strong" },
};
export const LABEL_ORDER = [
  "strong_accumulation",
  "accumulation",
  "neutral",
  "distribution",
  "strong_distribution",
];
export const LABEL_COLOR: Record<string, string> = {
  strong_accumulation: "var(--pos)",
  accumulation: "var(--pos)",
  neutral: "var(--flat)",
  distribution: "var(--neg)",
  strong_distribution: "var(--neg)",
};
export const LABEL_OPACITY = {
  strong_accumulation: 1,
  accumulation: 0.55,
  neutral: 1,
  distribution: 0.55,
  strong_distribution: 1,
};

export const COMPONENTS: Record<string, [string, string]> = {
  foreign_5d: [
    "Foreign flow, last 5 days",
    "Net foreign accumulation or distribution over 5 trading days, compared with what is normal for this stock.",
  ],
  foreign_streak: [
    "Foreign flow streak",
    "How many days in a row foreign investors were net accumulators or net distributors.",
  ],
  broker_concentration: [
    "Broker concentration",
    "Whether the three biggest net accumulators outweigh the three biggest net distributors over the last two weeks.",
  ],
  institutional_net: [
    "Institutional brokers",
    "The net position of brokers classed as institutional over the last two weeks.",
  ],
  divergence: [
    "Flow against price",
    "Flow pointing one way while the price moved the other way over 10 days.",
  ],
  insider: [
    "Insider filings",
    "The balance of insider transactions reported in the last 30 days.",
  ],
};
export const PILLARS: Record<string, [string, string]> = {
  quality: [
    "Quality",
    "Profitability and growth compared with the other stocks in the list.",
  ],
  valuation: [
    "Valuation",
    "Price multiples against peer averages, plus dividend yield.",
  ],
  slow_flow: [
    "Slow flow",
    "Foreign flow over 20 and 90 days, the monthly change in who holds the shares, and insider filings.",
  ],
};
export const INPUTS: Record<string, [string, string]> = {
  roe_ttm: ["Return on equity", "pct"],
  net_profit_margin: ["Net profit margin", "pct"],
  der_mrq: ["Debt to equity", "x"],
  yoy_quarter_earnings_growth: ["Earnings growth, year on year", "pct"],
  yoy_quarter_revenue_growth: ["Revenue growth, year on year", "pct"],
  pe_ttm: ["Price to earnings", "x"],
  pb_mrq: ["Price to book", "x"],
  pe_relative: ["PE against peers", "x"],
  pb_relative: ["PB against peers", "x"],
  yield_ttm: ["Dividend yield", "pct"],
  foreign_20d: ["Foreign flow, 20 days (share of market cap)", "pct3"],
  foreign_90d: ["Foreign flow, 90 days (share of market cap)", "pct3"],
  holder_shift: ["Change in institutional share", "pp"],
  insider: ["Insider filings balance", "ratio"],
};
export const FLAGS: Record<string, string> = {
  divergence_accumulation: "Accumulation while price fell",
  divergence_distribution: "Distribution while price rose",
  unusual_volume: "Unusual volume",
};
export const KINDS: Record<string, string> = {
  new_top5: "Entered the top 5",
  score_flip: "Label changed",
  streak_started: "Streak started",
  streak_ended: "Streak ended",
  divergence: "Flow against price",
  insider_filing: "Insider filing",
  suspension: "Suspension",
  rank_mover: "Rank movers",
  holder_shift: "Holder shifts",
};
export const words = (v: unknown) => {
  const t = String(v ?? "").replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};
