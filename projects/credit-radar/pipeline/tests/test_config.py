from pathlib import Path

from conftest import load_module


CONFIG = Path("projects/credit-radar/config/settings.yaml")


def test_default_settings_match_research_contract() -> None:
    config = load_module("credit_radar.config")
    settings = config.RadarSettings.load(CONFIG)

    assert settings.percentile_lookback == 756
    assert settings.percentile_minimum == 252
    assert settings.deteriorating_percentile == 70.0
    assert settings.stressed_percentile == 85.0
    assert settings.extreme_percentile == 95.0
    assert settings.spread_sma_days == 50
    assert settings.spread_short_change_days == 5
    assert settings.spread_medium_change_days == 20
    assert settings.stress_memory_days == 60
    assert settings.price_sma_weeks == 10
    assert settings.price_momentum_weeks == 4
    assert settings.divergence_percentile_gap == 20.0
    assert settings.minimum_backtest_samples == 10
    assert settings.backtest_horizons_weeks == (1, 4, 8, 13, 26)
