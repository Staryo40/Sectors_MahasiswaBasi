// Mirrors backend/radar/export/schemas. Keep JSON key names unchanged.
export type Source = "out" | "fixtures" | "sample";
export type Horizon = "daily" | "investor";
export type DailyEntry = {
  symbol: string;
  name: string;
  sector: string;
  rank: number;
  rank_prev: number | null;
  flow_score: number;
  flow_score_prev: number | null;
  label:
    | "strong_accumulation"
    | "accumulation"
    | "neutral"
    | "distribution"
    | "strong_distribution";
  components: {
    key: string;
    value: number;
    weight: number;
    contribution: number;
  }[];
  flags: (
    "divergence_accumulation" | "divergence_distribution" | "unusual_volume"
  )[];
  reasons: { code: string; params: Record<string, unknown>; text_en: string }[];
  close: number | null;
  change_1d: number | null;
  return_10d: number | null;
  volume_ratio: number | null;
};
export type InvestorEntry = {
  symbol: string;
  name: string;
  sector: string;
  rank: number;
  rank_prev: number | null;
  investor_score: number;
  pillars: {
    quality: number | null;
    valuation: number | null;
    slow_flow: number | null;
  };
  components: {
    key: string;
    pillar: "quality" | "valuation" | "slow_flow";
    raw: number | null;
    percentile: number | null;
  }[];
  coverage: number;
  reasons: { code: string; params: Record<string, unknown>; text_en: string }[];
};
export type Stock = {
  symbol: string;
  daily: DailyEntry;
  investor: InvestorEntry;
  series: {
    price: { date: string; close: number | null; volume: number | null }[];
    foreign_flow: {
      date: string;
      net: number | null;
      cum: number;
      share: number | null;
    }[];
    flow_score: { date: string; score: number }[];
    holder_mix: {
      date: string;
      institutional_pct: number | null;
      individual_pct: number | null;
      foreign_pct: number | null;
    }[];
  };
  top_brokers: {
    buyers: {
      code: string;
      name: string;
      cohort: "institutional" | "mixed" | "retail" | "unknown";
      is_foreign: boolean;
      net_value: number;
      avg_price: number | null;
    }[];
    sellers: {
      code: string;
      name: string;
      cohort: "institutional" | "mixed" | "retail" | "unknown";
      is_foreign: boolean;
      net_value: number;
      avg_price: number | null;
    }[];
  };
  filings: {
    date: string;
    transaction_type: "accumulation" | "distribution" | "others";
    holder_type: string;
  }[];
  events: { date: string; type: string; detail: string }[];
  fundamentals: {
    key: string;
    value: number | null;
    peer_avg: number | null;
    percentile: number | null;
  }[];
};
export type Meta = {
  as_of: string;
  generated_at: string;
  universe: string;
  n_stocks: number;
  credits_used: number;
  disclaimer: string;
};
export type Brief = {
  as_of: string;
  items: {
    kind:
      | "new_top5"
      | "score_flip"
      | "streak_started"
      | "streak_ended"
      | "divergence"
      | "insider_filing"
      | "suspension"
      | "rank_mover"
      | "holder_shift";
    code: string;
    symbol: string;
    params: Record<string, unknown>;
    text_en: string;
  }[];
  upcoming: { date: string; symbol: string; type: string }[];
  disclaimer: string;
};
export interface Snapshot {
  source: Source;
  meta: Meta;
  daily: DailyEntry[];
  investor: InvestorEntry[];
  dailyBrief: Brief;
  weeklyBrief: Brief;
}
