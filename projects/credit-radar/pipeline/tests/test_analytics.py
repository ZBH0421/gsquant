import math

import pandas as pd

from conftest import load_module


def test_prior_percentile_excludes_current_and_future_values() -> None:
    analytics = load_module("credit_radar.analytics")
    values = pd.Series([1.0, 3.0, 2.0, 4.0, 5.0])

    result = analytics.prior_percentile(values, lookback=3, min_periods=2)

    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    assert result.iloc[2] == 50.0
    assert result.iloc[3] == 100.0
    assert result.iloc[4] == 100.0

    changed_future = pd.Series([1.0, 3.0, 2.0, 4.0, -999.0])
    changed = analytics.prior_percentile(changed_future, lookback=3, min_periods=2)
    pd.testing.assert_series_equal(result.iloc[:4], changed.iloc[:4])


def test_credit_features_add_spread_trend_and_changes() -> None:
    analytics = load_module("credit_radar.analytics")
    config = load_module("credit_radar.config")
    settings = config.RadarSettings.for_tests(
        percentile_lookback=20,
        percentile_minimum=5,
        spread_sma_days=10,
        spread_short_change_days=5,
        spread_medium_change_days=20,
    )
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=30, freq="D"),
            "hy": [float(value) for value in range(1, 31)],
            "ig": [float(value) / 10 for value in range(1, 31)],
            "vix": [10.0 + float(value) for value in range(30)],
        }
    )

    result = analytics.compute_credit_features(frame, settings)

    assert result.iloc[-1]["hy_change_5d"] == 5.0
    assert result.iloc[-1]["hy_change_20d"] == 20.0
    assert result.iloc[-1]["hy_sma50"] == 25.5
    assert result.iloc[-1]["hy_high_20d"] == 29.0
    assert result.iloc[-1]["hy_percentile"] == 100.0
