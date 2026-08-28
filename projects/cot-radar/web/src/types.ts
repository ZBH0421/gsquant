export type RadarState =
  | "NORMAL"
  | "EXTREME_LONG"
  | "EXTREME_SHORT"
  | "UNWINDING_LONG"
  | "UNWINDING_SHORT"
  | "CONFIRMED_BEARISH"
  | "CONFIRMED_BULLISH"
  | string;

export interface Evidence {
  objective_facts?: string;
  rule_classification?: string;
  market_inference?: string;
  alternative_explanations?: string;
  facts?: string | string[];
  rule?: string;
  inference?: string;
  alternatives?: string;
  alternative?: string;
  confirmation: string;
  invalidation: string;
}

export interface SubjectiveNote {
  symbol: string;
  date: string;
  author: string;
  text: string;
}

export interface MarketSnapshot {
  symbol: "ES" | "NQ";
  display_name: string;
  market_name?: string;
  proxy_symbol: string;
  report_date: string;
  available_at?: string;
  state: RadarState;
  extreme_direction: string | null;
  leveraged_net_pct_oi?: number | null;
  leveraged_net_oi_pct?: number | null;
  leveraged_percentile: number | null;
  leveraged_weekly_change?: number | null;
  asset_manager_net_pct_oi?: number | null;
  asset_manager_net_oi_pct?: number | null;
  asset_manager_percentile?: number | null;
  close?: number | null;
  proxy_close?: number | null;
  price_sma?: number | null;
  price_momentum?: number | null;
  evidence?: Evidence;
  narrative?: Evidence;
  subjective_notes?: SubjectiveNote[];
  note?: SubjectiveNote | null;
}

export interface DashboardData {
  generated_at: string;
  report_date?: string;
  latest_report_date?: string;
  markets: MarketSnapshot[];
  methodology?: Record<string, unknown>;
  stale?: boolean;
  price_provider?: string;
}

export interface HistoryRow {
  symbol: "ES" | "NQ";
  report_date: string;
  state: RadarState;
  extreme_direction?: string | null;
  leveraged_net_pct_oi?: number | null;
  leveraged_net_oi_pct?: number | null;
  leveraged_percentile: number | null;
  asset_manager_net_pct_oi?: number | null;
  asset_manager_net_oi_pct?: number | null;
  asset_manager_percentile?: number | null;
  price_normalized?: number | null;
  proxy_close?: number | null;
}

export interface HistoryData {
  history?: HistoryRow[];
  markets?: Record<string, HistoryRow[]>;
}

export interface BacktestRow {
  symbol: string;
  state: string;
  extreme_direction: string;
  horizon_weeks: number;
  sample_count: number;
  median_forward_return: number | null;
  reversal_win_rate: number | null;
  median_max_adverse_excursion: number | null;
}

export interface BacktestData {
  summary?: BacktestRow[];
  rows?: BacktestRow[];
}

export interface StatusData {
  generated_at: string;
  latest_report_date: string;
  price_provider: string;
  stale: boolean;
  stale_after_days?: number;
  cftc_dataset?: string;
}
