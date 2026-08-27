import pandas as pd

from cot_radar.backtest import summarize_events
from cot_radar.config import RadarSettings
from cot_radar.narratives import build_evidence


def test_evidence_chain_keeps_fact_and_inference_separate() -> None:
    snapshot = {
        "symbol": "NQ",
        "report_date": pd.Timestamp("2026-08-18"),
        "state": "CONFIRMED_BEARISH",
        "leveraged_net_pct_oi": 12.4,
        "leveraged_percentile": 97.0,
        "leveraged_zscore": 2.1,
        "leveraged_weekly_change": -1.2,
        "asset_manager_net_pct_oi": 20.0,
        "proxy_symbol": "QQQ",
        "price_close": 580.0,
        "price_sma": 590.0,
        "price_momentum": -0.03,
    }

    evidence = build_evidence(snapshot, RadarSettings.for_tests())

    assert evidence.objective_facts
    assert "可能" in evidence.market_inference
    assert "買進" not in evidence.market_inference
    assert evidence.alternative_explanations
    assert evidence.invalidation


def test_backtest_uses_first_close_after_publication() -> None:
    events = pd.DataFrame(
        {
            "symbol": ["ES"],
            "state": ["UNWINDING_LONG"],
            "available_at": [pd.Timestamp("2026-01-09 15:30", tz="America/New_York")],
            "extreme_direction": ["long"],
        }
    )
    prices = pd.DataFrame(
        {
            "symbol": ["ES"] * 4,
            "date": pd.to_datetime(["2026-01-02", "2026-01-09", "2026-01-16", "2026-02-06"]),
            "close": [100.0, 102.0, 99.0, 95.0],
        }
    )

    rows = summarize_events(events, prices, horizons=(1, 3))

    assert rows.iloc[0]["baseline_date"] >= pd.Timestamp("2026-01-09")
    assert set(rows["horizon_weeks"]) == {1, 3}
    assert rows.loc[rows["horizon_weeks"] == 1, "reversal_win"].iloc[0]
