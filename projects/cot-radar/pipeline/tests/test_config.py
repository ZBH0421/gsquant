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
