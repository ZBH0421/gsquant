import pandas as pd

from conftest import load_module


def test_event_study_uses_state_entries_and_suppresses_small_sample_win_rate() -> None:
    backtest = load_module("credit_radar.backtest")
    config = load_module("credit_radar.config")
    settings = config.RadarSettings.for_tests(
        minimum_backtest_samples=10,
        backtest_horizons_weeks=(1, 4),
    )
    dates = pd.date_range("2025-01-03", periods=12, freq="W-FRI")
    states = pd.DataFrame(
        {
            "date": dates,
            "state": ["NORMAL", "NORMAL", "CREDIT_REVERSAL"] + ["NORMAL"] * 9,
        }
    )
    prices = pd.DataFrame({"date": dates, "close": [100.0 + i for i in range(12)]})

    rows = backtest.build_event_study(states, {"SPY": prices}, settings, provider="stooq")
    four_week = next(
        row
        for row in rows
        if row["symbol"] == "SPY"
        and row["state"] == "CREDIT_REVERSAL"
        and row["horizon_weeks"] == 4
    )

    assert four_week["n"] == 1
    assert four_week["positive_return_rate"] is None
    assert four_week["small_sample"] is True
    assert four_week["proxy_label"] == "ES proxy (SPY), not ES settlement"
    assert four_week["median_return"] > 0
