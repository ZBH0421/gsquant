import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("react-plotly.js", () => ({
  default: ({ divId }: { divId?: string }) => <div data-testid={divId ?? "plot"} />,
}));

const stateMachine = {
  NORMAL: {
    entry: "沒有有效的極端、鬆動或價格確認條件。",
    hold: "極端記憶不存在或已失效。",
    exit: "Leveraged Funds 百分位進入第 90 百分位以上或第 10 百分位以下。",
    price_confirmation: "不需要。",
    invalidation: "新的極端條件成立即退出 NORMAL。",
  },
  EXTREME_LONG: {
    entry: "Leveraged Funds prior-only 百分位 >= 第 90 百分位。",
    hold: "百分位持續 >= 第 90 百分位。",
    exit: "百分位退出多頭極端區。",
    price_confirmation: "極端本身不使用價格確認。",
    invalidation: "百分位跌回極端門檻以下。",
  },
  EXTREME_SHORT: {
    entry: "Leveraged Funds prior-only 百分位 <= 第 10 百分位。",
    hold: "百分位持續 <= 第 10 百分位。",
    exit: "百分位退出空頭極端區。",
    price_confirmation: "極端本身不使用價格確認。",
    invalidation: "百分位升回極端門檻以上。",
  },
  UNWINDING_LONG: {
    entry: "最近 4 週內曾為 EXTREME_LONG，且淨部位／OI 較前週下降。",
    hold: "極端記憶仍有效且淨部位／OI 繼續下降。",
    exit: "部位不再下降、重新進入極端，或極端記憶到期。",
    price_confirmation: "滿 2 週後才可檢查價格確認。",
    invalidation: "部位下降條件中斷或記憶到期。",
  },
  UNWINDING_SHORT: {
    entry: "最近 4 週內曾為 EXTREME_SHORT，且淨部位／OI 較前週上升。",
    hold: "極端記憶仍有效且淨部位／OI 繼續上升。",
    exit: "部位不再上升、重新進入極端，或極端記憶到期。",
    price_confirmation: "滿 2 週後才可檢查價格確認。",
    invalidation: "部位上升條件中斷或記憶到期。",
  },
  CONFIRMED_BEARISH: {
    entry: "UNWINDING_LONG 加上價格確認。",
    hold: "多頭鬆動與價格弱勢持續。",
    exit: "價格確認失效時退回 UNWINDING_LONG。",
    price_confirmation: "價格 < 10 週均線且 4 週動能 < 0。",
    invalidation: "價格或部位確認失效。",
  },
  CONFIRMED_BULLISH: {
    entry: "UNWINDING_SHORT 加上價格確認。",
    hold: "空頭回補與價格強勢持續。",
    exit: "價格確認失效時退回 UNWINDING_SHORT。",
    price_confirmation: "價格 > 10 週均線且 4 週動能 > 0。",
    invalidation: "價格或部位確認失效。",
  },
};

const status = {
  generated_at: "2026-08-28T08:00:00Z",
  latest_report_date: "2026-08-18T00:00:00",
  scheduled_release_at: "2026-08-21T15:30:00-04:00",
  fetched_at: "2026-08-28T08:00:00Z",
  last_successful_update_at: "2026-08-28T08:00:00Z",
  last_update_attempt_at: "2026-08-28T08:00:00Z",
  last_update_succeeded: true,
  next_scheduled_update_at: "2026-08-29T08:00:00+08:00",
  next_expected_report_date: "2026-08-25T00:00:00",
  next_expected_release_at: "2026-08-28T15:30:00-04:00",
  stale: false,
  publication_state: "waiting_for_cftc",
  warning: "等待 CFTC 發布下一期 TFF Futures Only；目前顯示最近一次成功資料，不代表更新失敗。",
  price_provider: "stooq",
  cftc_dataset: "gpe5-46if",
};

const dashboard = {
  generated_at: status.generated_at,
  report_date: status.latest_report_date,
  data_status: status,
  methodology: {
    lookback_weeks: 156,
    extreme_high: 90,
    extreme_low: 10,
    price_sma_weeks: 10,
    price_momentum_weeks: 4,
    divergence_percentile_gap: 20,
    minimum_backtest_samples: 10,
    state_machine: stateMachine,
  },
  comparison: {
    markets: {
      ES: {
        leveraged_net_pct_oi: 8,
        asset_manager_net_pct_oi: 12.1,
        leveraged_percentile: 95,
        leveraged_change_1w: 1.5,
        leveraged_change_4w: 4,
        asset_manager_change_1w: 0.2,
        asset_manager_change_4w: 0.8,
        price_momentum_4w: 0.02,
        price_vs_sma_10w: 0.015625,
        state: "EXTREME_LONG",
        proxy_symbol: "SPY",
      },
      NQ: {
        leveraged_net_pct_oi: 3,
        asset_manager_net_pct_oi: 9.3,
        leveraged_percentile: 70,
        leveraged_change_1w: 0.1,
        leveraged_change_4w: 0.4,
        asset_manager_change_1w: 0.1,
        asset_manager_change_4w: 0.3,
        price_momentum_4w: -0.01,
        price_vs_sma_10w: -0.0169,
        state: "NORMAL",
        proxy_symbol: "QQQ",
      },
    },
    synchronized_crowding: false,
    position_divergence: true,
    percentile_gap: 25,
    more_extreme_market: "ES",
    evidence: "ES Leveraged Funds 156 週 prior-only 百分位 95.0，NQ 70.0，差距 25.0 個百分點；公開門檻為 20.0，故判定部位分歧。",
    falsification: "當 ES／NQ Leveraged Funds prior-only 百分位差距低於 20.0 個百分點時，部位分歧判定失效。",
    formula: "divergence = abs(ES percentile - NQ percentile) >= threshold",
  },
  markets: [
    {
      symbol: "ES",
      display_name: "E-mini S&P 500",
      market_name: "S&P 500 Consolidated - CHICAGO MERCANTILE EXCHANGE",
      proxy_symbol: "SPY",
      report_date: "2026-08-18",
      available_at: "2026-08-21T19:30:00Z",
      state: "EXTREME_LONG",
      extreme_direction: "long",
      leveraged_net_pct_oi: 8,
      leveraged_percentile: 95,
      leveraged_weekly_change: 1.5,
      leveraged_four_week_change: 4,
      asset_manager_net_pct_oi: 12.1,
      asset_manager_percentile: 82,
      close: 650,
      price_sma: 640,
      price_momentum: 0.02,
      evidence: {
        objective_facts: "截至 2026-08-18，ES 槓桿基金淨部位位於第 95.0 百分位。",
        rule_classification: "EXTREME_LONG",
        market_inference: "多頭部位擁擠。",
        alternative_explanations: "換月也可能造成部位變化。",
        confirmation: "部位鬆動且價格跌破均線可提高可信度。",
        invalidation: "部位重新增加且價格創高則撤銷。",
      },
      subjective_notes: [],
    },
    {
      symbol: "NQ",
      display_name: "E-mini Nasdaq-100",
      market_name: "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE",
      proxy_symbol: "QQQ",
      report_date: "2026-08-18",
      available_at: "2026-08-21T19:30:00Z",
      state: "NORMAL",
      extreme_direction: null,
      leveraged_net_pct_oi: 3,
      leveraged_percentile: 70,
      leveraged_weekly_change: 0.1,
      leveraged_four_week_change: 0.4,
      asset_manager_net_pct_oi: 9.3,
      asset_manager_percentile: 68,
      close: 580,
      price_sma: 590,
      price_momentum: -0.01,
      evidence: {
        objective_facts: "槓桿基金淨部位未進入極端區。",
        rule_classification: "NORMAL",
        market_inference: "尚無極端擁擠。",
        alternative_explanations: "彙總分類不代表單一基金方向。",
        confirmation: "等待公開規則條件成立。",
        invalidation: "目前無反轉推論。",
      },
      subjective_notes: [],
    },
  ],
};

const history = {
  history: [
    {
      symbol: "ES",
      report_date: "2026-08-11",
      state: "NORMAL",
      leveraged_percentile: 80,
      leveraged_net_pct_oi: 3.5,
      asset_manager_net_pct_oi: 11,
      price_normalized: 99,
    },
    {
      symbol: "ES",
      report_date: "2026-08-18",
      state: "EXTREME_LONG",
      leveraged_percentile: 95,
      leveraged_net_pct_oi: 8,
      asset_manager_net_pct_oi: 12.1,
      price_normalized: 100,
    },
    {
      symbol: "NQ",
      report_date: "2026-08-18",
      state: "NORMAL",
      leveraged_percentile: 70,
      leveraged_net_pct_oi: 3,
      asset_manager_net_pct_oi: 9.3,
      price_normalized: 100,
    },
  ],
};

const backtest = {
  metadata: {
    horizons_weeks: [1, 4, 8, 13],
    minimum_sample_size: 10,
    availability_assumption: "COT 通常反映週二部位，並以正常排程週五 15:30 America/New_York 可得後的第一個週線價格作為回測起點。",
    historical_release_limit: "歷史資料無法逐筆重建所有假日或營運延遲發布時間；延遲週的結果可能偏樂觀。",
    disclaimer: "歷史統計僅描述過去樣本，不代表未來報酬或交易建議。",
    price_provider: "stooq",
    price_proxies: { ES: "SPY", NQ: "QQQ" },
  },
  summary: [
    {
      symbol: "ES",
      state: "CONFIRMED_BEARISH",
      extreme_direction: "long",
      signal_direction: "bearish",
      horizon_weeks: 4,
      sample_count: 2,
      median_forward_return: -0.015,
      reversal_win_rate: null,
      median_max_adverse_excursion: 0.015,
      small_sample: true,
      proxy_symbol: "SPY",
      price_provider: "stooq",
      period_start: "2026-07-03T00:00:00",
      period_end: "2026-08-07T00:00:00",
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const responseData = url.includes("dashboard")
      ? dashboard
      : url.includes("history")
        ? history
        : url.includes("backtest")
          ? backtest
          : status;
    return Promise.resolve(new Response(JSON.stringify(responseData), { status: 200 }));
  }));
});

describe("COT Radar", () => {
  it("shows ES and NQ latest states with traceable narrative", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: /CFTC 期貨部位擁擠/ })).toBeInTheDocument();
    expect(await screen.findByText("E-mini S&P 500")).toBeInTheDocument();
    expect(screen.getByText("E-mini Nasdaq-100")).toBeInTheDocument();
    expect(screen.getByText("EXTREME_LONG")).toBeInTheDocument();
    expect(screen.getByText("客觀事實")).toBeInTheDocument();
    expect(screen.getByText(/截至 2026-08-18，ES 槓桿基金/)).toBeInTheDocument();
    expect(screen.getByText("確認與失效條件")).toBeInTheDocument();
    expect(screen.getByText(/SPY.*代理/)).toBeInTheDocument();
    expect(screen.getByText(/CFTC 官方市場：S&P 500 Consolidated/)).toBeInTheDocument();
  });

  it("separates CFTC report release fetch and update timestamps", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "資料新鮮度與更新狀態" })).toBeInTheDocument();
    expect(screen.getByText("CFTC 部位所屬星期二")).toBeInTheDocument();
    expect(screen.getByText("正常排程發布時間")).toBeInTheDocument();
    expect(screen.getByText("系統實際抓取時間")).toBeInTheDocument();
    expect(screen.getByText("最近一次成功更新")).toBeInTheDocument();
    expect(screen.getByText("下一次預定更新")).toBeInTheDocument();
    expect(screen.getByText("gpe5-46if")).toBeInTheDocument();
    expect(screen.getAllByText("stooq").length).toBeGreaterThan(0);
    expect(screen.getByText(/等待 CFTC 發布下一期/)).toBeInTheDocument();
  });

  it("renders deterministic ES NQ comparison and falsification evidence", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "ES／NQ 客觀比較" })).toBeInTheDocument();
    expect(screen.getByText("同步擁擠：否")).toBeInTheDocument();
    expect(screen.getByText("部位分歧：是")).toBeInTheDocument();
    expect(screen.getByText("更極端市場：ES")).toBeInTheDocument();
    expect(screen.getByText(/差距 25.0 個百分點/)).toBeInTheDocument();
    expect(screen.getByText(/低於 20.0 個百分點時.*失效/)).toBeInTheDocument();
    expect(screen.getByText("4.0")).toBeInTheDocument();
  });

  it("marks small backtest samples and suppresses misleading win rates", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("E-mini S&P 500");

    await user.click(screen.getByRole("button", { name: "歷史驗證" }));
    expect(await screen.findByRole("heading", { name: "歷史訊號驗證" })).toBeInTheDocument();
    expect(screen.getByText(/樣本不足.*10/)).toBeInTheDocument();
    expect(screen.getByText("不顯示")).toBeInTheDocument();
    expect(screen.getByText(/SPY.*stooq/)).toBeInTheDocument();
    expect(screen.getByText(/不代表未來報酬/)).toBeInTheDocument();
  });

  it("shows public state rules sources and derived downloads", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("E-mini S&P 500");

    await user.click(screen.getByRole("button", { name: "方法與資料" }));
    await waitFor(() => expect(screen.getByText(/prior-only/)).toBeInTheDocument());
    expect(screen.getByText(/週二部位.*週五發布/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "狀態機公開規則" })).toBeInTheDocument();
    expect(screen.getByText("CONFIRMED_BEARISH")).toBeInTheDocument();
    expect(screen.getByText(/價格 < 10 週均線且 4 週動能 < 0/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CFTC TFF Futures Only" })).toHaveAttribute("href", expect.stringContaining("gpe5-46if"));
    expect(screen.getByRole("link", { name: "signals.csv" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "status.json" })).toBeInTheDocument();
    expect(screen.getByText(/不提供完整原始價格序列/)).toBeInTheDocument();
  });

  it("keeps a timezone-naive CFTC timestamp on its stated calendar date", async () => {
    const originalTimezone = process.env.TZ;
    process.env.TZ = "Asia/Taipei";
    const liveStatus = {
      ...status,
      latest_report_date: "2026-08-18T00:00:00",
    };
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const responseData = url.includes("dashboard")
        ? dashboard
        : url.includes("history")
          ? history
          : url.includes("backtest")
            ? backtest
            : liveStatus;
      return Promise.resolve(new Response(JSON.stringify(responseData), { status: 200 }));
    }));

    try {
      render(<App />);
      expect((await screen.findAllByText("2026年8月18日")).length).toBeGreaterThan(0);
    } finally {
      if (originalTimezone === undefined) delete process.env.TZ;
      else process.env.TZ = originalTimezone;
    }
  });
});