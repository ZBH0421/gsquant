import pandas as pd

from conftest import load_module


def test_weekly_proxy_alignment_uses_only_price_observations_available_by_credit_date() -> None:
    pipeline = load_module("credit_radar.pipeline")
    credit = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-13"]),
            "hy": [3.0],
            "ig": [1.0],
            "vix": [15.0],
        }
    )
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-09", "2026-01-16"]),
            "close": [100.0, 200.0],
            "sma": [95.0, 150.0],
            "momentum": [2.0, 50.0],
        }
    )

    result = pipeline.align_price_features(credit, prices, prefix="spy")

    assert result.iloc[0]["spy_close"] == 100.0
    assert result.iloc[0]["spy_sma10w"] == 95.0
    assert result.iloc[0]["spy_momentum_4w"] == 2.0
