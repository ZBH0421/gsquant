import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("react-plotly.js", () => ({
  default: ({ divId }: { divId?: string }) => <div data-testid={divId ?? "plot"} />,
}));

const dashboard = {
  generated_at: "2026-08-27T00:00:00Z",
  latest_report_date: "2026-08-18",
  stale: false,
  price_provider: "stooq",
  markets: [
    {
      symbol: "ES",
      display_name: "E-mini S&P 500",
      proxy_symbol: "SPY",
      report_date: "2026-08-18",
      available_at: "2026-08-21T19:30:00Z",
      state: "EXTREME",
      extreme_direction: "LONG",
      leveraged_net_oi_pct: 4.2,
      leveraged_percentile: 96.4,
      leveraged_weekly_change: -0.3,
      asset_manager_net_oi_pct: 12.1,
      proxy_close: 650,
      price_sma: 630,
      price_momentum: 0.02,
      evidence: {
        objective_facts: "截至 2026-08-18，ES 槓桿基金淨部位位於第 96.4 百分位。",
        rule_classification: "LONG EXTREME",
        market_inference: "多頭部位擁擠。",
        alternative_explanations: "換月也可能造成部位變化。",
        confirmation: "部位鬆動且價格跌破均線可提高可信度。",
        invalidation: "部位重新增加且價格創高則撤銷。"
      },
      note: null
    },
    {
      symbol: "NQ",
      display_name: "E-mini Nasdaq-100",
      proxy_symbol: "QQQ",
      report_date: "2026-08-18",
      available_at: "2026-08-21T19:30:00Z",
      state: "NORMAL",
      extreme_direction: null,
      leveraged_net_oi_pct: 1.2,
      leveraged_percentile: 54.0,
      leveraged_weekly_change: 0.1,
      asset_manager_net_oi_pct: 9.3,
      proxy_close: 580,
      price_sma: 570,
      price_momentum: 0.01,
      evidence: {
        objective_facts: "槓桿基金淨部位接近歷史中位數。",
        rule_classification: "NORMAL",
        market_inference: "尚無極端擁擠。",
        alternative_explanations: "彙總分類不代表單一基金方向。",
        confirmation: "等待部位進入極端區。",
        invalidation: "目前無反轉推論。"
      },
      note: null
    }
  ]
};

const history = {
  markets: {
    ES: [
      { report_date: "2026-08-11", state: "NORMAL", leveraged_percentile: 80, leveraged_net_oi_pct: 3.5, asset_manager_net_oi_pct: 11, proxy_close: 640 },
      { report_date: "2026-08-18", state: "EXTREME", leveraged_percentile: 96.4, leveraged_net_oi_pct: 4.2, asset_manager_net_oi_pct: 12.1, proxy_close: 650 }
    ],
    NQ: []
  }
};

const backtest = { rows: [] };
const status = { generated_at: dashboard.generated_at, latest_report_date: dashboard.latest_report_date, stale: false, price_provider: "stooq" };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const value = url.includes("dashboard") ? dashboard : url.includes("history") ? history : url.includes("backtest") ? backtest : status;
    return Promise.resolve(new Response(JSON.stringify(value), { status: 200 }));
  }));
});

describe("COT Radar", () => {
  it("shows ES and NQ latest states with traceable narrative", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: /CFTC 期貨部位擁擠/ })).toBeInTheDocument();
    expect(await screen.findByText("E-mini S&P 500")).toBeInTheDocument();
    expect(screen.getByText("E-mini Nasdaq-100")).toBeInTheDocument();
    expect(screen.getByText("EXTREME")).toBeInTheDocument();
    expect(screen.getByText("客觀事實")).toBeInTheDocument();
    expect(screen.getByText(/截至 2026-08-18，ES 槓桿基金/)).toBeInTheDocument();
    expect(screen.getByText("確認與失效條件")).toBeInTheDocument();
    expect(screen.getByText(/SPY.*代理/)).toBeInTheDocument();
  });

  it("navigates to historical validation and methodology", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("E-mini S&P 500");

    await user.click(screen.getByRole("button", { name: "歷史驗證" }));
    expect(await screen.findByRole("heading", { name: "歷史訊號驗證" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "方法與資料" }));
    await waitFor(() => expect(screen.getByText(/prior-only/)).toBeInTheDocument());
    expect(screen.getByText(/週二部位.*週五發布/)).toBeInTheDocument();
  });
});
