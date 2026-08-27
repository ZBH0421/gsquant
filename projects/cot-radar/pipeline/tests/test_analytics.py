import pandas as pd
import pytest

from cot_radar.analytics import add_position_metrics, prior_percentile, prior_zscore
from cot_radar.config import RadarSettings


def test_prior_percentile_excludes_current_observation() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 100.0])
    result = prior_percentile(series, window=3, minimum=3)

    assert result.iloc[-1] == 100.0
    assert result.iloc[:3].isna().all()


def test_prior_zscore_does_not_dilute_current_extreme() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 100.0])
    result = prior_zscore(series, window=3, minimum=3)

    assert result.iloc[-1] == pytest.approx(98.0)
    assert result.iloc[:3].isna().all()


def test_add_position_metrics_normalizes_each_market(
    settings: RadarSettings,
) -> None:
    rows: list[dict[str, object]] = []
    for symbol in ("ES", "NQ"):
        for week, net in enumerate((10.0, 20.0, 30.0, 40.0)):
            rows.append(
                {
                    "symbol": symbol,
                    "report_date": pd.Timestamp("2026-01-06") + pd.Timedelta(weeks=week),
                    "open_interest": 1000.0,
                    "leveraged_long": 100.0 + net,
                    "leveraged_short": 100.0,
                    "asset_manager_long": 300.0,
                    "asset_manager_short": 100.0,
                    "dealer_long": 100.0,
                    "dealer_short": 120.0,
                    "other_long": 50.0,
                    "other_short": 40.0,
                    "nonreportable_long": 20.0,
                    "nonreportable_short": 30.0,
                }
            )

    result = add_position_metrics(
        pd.DataFrame(rows),
        settings.with_overrides(lookback_weeks=3, minimum_history_weeks=3),
    )

    latest = result.groupby("symbol").tail(1)
    assert set(latest["leveraged_net_pct_oi"]) == {4.0}
    assert set(latest["leveraged_percentile"]) == {100.0}
    assert set(latest["leveraged_weekly_change"]) == {1.0}


@pytest.fixture
def settings() -> RadarSettings:
    return RadarSettings.for_tests()
