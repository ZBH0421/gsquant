from pathlib import Path

from cot_radar.config import load_settings

SETTINGS = Path("projects/cot-radar/config/settings.yaml")


def test_settings_define_only_es_and_nq() -> None:
    settings = load_settings(SETTINGS)

    assert set(settings.markets) == {"ES", "NQ"}
    assert settings.extreme_high == 90.0
    assert settings.extreme_low == 10.0
    assert settings.markets["ES"].proxy_symbol == "SPY"
    assert settings.markets["NQ"].proxy_symbol == "QQQ"


def test_thresholds_are_ordered() -> None:
    settings = load_settings(SETTINGS)

    assert 0 <= settings.extreme_low < settings.extreme_high <= 100
    assert settings.minimum_history_weeks <= settings.lookback_weeks


def test_v2_behavior_thresholds_are_centralized_in_settings() -> None:
    settings = load_settings(SETTINGS)

    assert settings.lookback_weeks == 156
    assert settings.price_sma_weeks == 10
    assert settings.price_momentum_weeks == 4
    assert settings.confirmation_delay_weeks == 2
    assert settings.divergence_percentile_gap == 20.0
    assert settings.minimum_backtest_samples == 10
    assert settings.publication_grace_days == 3
