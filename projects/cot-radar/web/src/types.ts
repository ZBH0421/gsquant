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
  leveraged_four_week_change?: number | null;
  asset_manager_net_pct_oi?: number | null;
  asset_manager_net_oi_pct?: number | null;
  asset_manager_percentile?: number | null;
  asset_manager_weekly_change?: number | null;
  asset_manager_four_week_change?: number | null;
  close?: number | null;
  proxy_close?: number | null;
  price_sma?: number | null;
  price_momentum?: number | null;
  evidence?: Evidence;
  narrative?: Evidence;
  subjective_notes?: SubjectiveNote[];
  note?: SubjectiveNote | null;
}

export interface ComparisonMarket {
  leveraged_net_pct_oi: number | null;
  asset_manager_net_pct_oi: number | null;
  leveraged_percentile: number | null;
  leveraged_change_1w: number | null;
  leveraged_change_4w: number | null;
  asset_manager_change_1w: number | null;
  asset_manager_change_4w: number | null;
  price_momentum_4w: number | null;
  price_vs_sma_10w: number | null;
  state: RadarState;
  proxy_symbol: string;
}

export interface MarketComparison {
  markets: Record<"ES" | "NQ", ComparisonMarket>;
  synchronized_crowding: boolean;
  position_divergence: boolean;
  percentile_gap: number | null;
  more_extreme_market: "ES" | "NQ" | null;
  evidence: string;
  falsification: string;
  formula: string;
}

export interface StateRule {
  entry: string;
  hold: string;
  exit: string;
  price_confirmation: string;
  invalidation: string;
}

export interface Methodology {
  lookback_weeks?: number;
  minimum_history_weeks?: number;
  extreme_high?: number;
  extreme_low?: number;
  unwind_memory_weeks?: number;
  confirmation_delay_weeks?: number;
  price_sma_weeks?: number;
  price_momentum_weeks?: number;
  divergence_percentile_gap?: number;
  minimum_backtest_samples?: number;
  price_proxies?: Record<string, string>;
  state_machine?: Record<string, StateRule>;
  [key: string]: unknown;
}

export interface DashboardData {
  generated_at: string;
  report_date?: string;
  latest_report_date?: string;
  markets: MarketSnapshot[];
  comparison?: MarketComparison;
  data_status?: StatusData;
  methodology?: Methodology;
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
  leveraged_weekly_change?: number | null;
  leveraged_four_week_change?: number | null;
  asset_manager_net_pct_oi?: number | null;
  asset_manager_net_oi_pct?: number | null;
  asset_manager_percentile?: number | null;
  asset_manager_weekly_change?: number | null;
  asset_manager_four_week_change?: number | null;
  close?: number | null;
  price_sma?: number | null;
  price_momentum?: number | null;
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
  signal_direction?: string;
  horizon_weeks: number;
  sample_count: number;
  median_forward_return: number | null;
  reversal_win_rate: number | null;
  median_max_adverse_excursion: number | null;
  small_sample?: boolean;
  proxy_symbol?: string;
  price_provider?: string;
  period_start?: string;
  period_end?: string;
}

export interface BacktestMetadata {
  horizons_weeks?: number[];
  minimum_sample_size?: number;
  availability_assumption?: string;
  historical_release_limit?: string;
  disclaimer?: string;
  price_provider?: string;
  price_proxies?: Record<string, string>;
}

export interface BacktestData {
  metadata?: BacktestMetadata;
  summary?: BacktestRow[];
  rows?: BacktestRow[];
}

export interface StatusData {
  generated_at: string;
  latest_report_date: string;
  scheduled_release_at?: string;
  fetched_at?: string;
  last_successful_update_at?: string;
  last_update_attempt_at?: string;
  last_update_succeeded?: boolean;
  next_scheduled_update_at?: string;
  next_expected_report_date?: string;
  next_expected_release_at?: string;
  price_provider: string;
  stale: boolean;
  publication_state?: "current" | "waiting_for_cftc" | "stale" | string;
  warning?: string | null;
  stale_after_days?: number;
  publication_grace_days?: number;
  cftc_dataset?: string;
}
