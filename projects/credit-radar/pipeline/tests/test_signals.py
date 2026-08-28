import pandas as pd

from conftest import load_module


def _settings():
    config = load_module("credit_radar.config")
    return config.RadarSettings.for_tests(stress_memory_days=60)


def test_state_machine_moves_from_stress_to_reversal_and_price_confirmation() -> None:
    signals = load_module("credit_radar.signals")
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=7, freq="D"),
            "hy": [3.0, 4.5, 5.0, 5.5, 5.0, 4.4, 4.2],
            "hy_percentile": [50.0, 75.0, 90.0, 97.0, 80.0, 69.0, 65.0],
            "hy_sma50": [3.1, 4.0, 4.4, 4.8, 4.8, 4.6, 4.5],
            "hy_change_20d": [0.0, 0.5, 0.8, 1.0, 0.4, -0.2, -0.4],
            "hy_high_20d": [3.2, 4.4, 4.9, 5.4, 5.5, 5.5, 5.5],
            "ig_percentile": [50.0] * 7,
            "vix_percentile": [50.0] * 7,
            "spy_close": [100.0] * 7,
            "spy_sma10w": [101.0] * 6 + [99.0],
            "spy_momentum_4w": [-1.0] * 6 + [2.0],
            "qqq_close": [100.0] * 7,
            "qqq_sma10w": [101.0] * 7,
            "qqq_momentum_4w": [-1.0] * 7,
        }
    )

    result = signals.classify_credit_states(frame, _settings())

    assert result["state"].tolist() == [
        "NORMAL",
        "DETERIORATING",
        "STRESSED",
        "EXTREME_STRESS",
        "STABILIZING",
        "CREDIT_REVERSAL",
        "CONFIRMED_RISK_ON",
    ]
    assert result.iloc[-1]["spy_confirmed"]
    assert not result.iloc[-1]["qqq_confirmed"]


def test_cross_asset_evidence_is_formula_driven_and_falsifiable() -> None:
    signals = load_module("credit_radar.signals")
    latest = pd.Series(
        {
            "hy_percentile": 92.0,
            "ig_percentile": 60.0,
            "vix_percentile": 65.0,
        }
    )

    evidence = signals.build_cross_asset_evidence(latest, _settings())

    assert "HY_SPECIFIC_STRESS" in evidence["labels"]
    assert "CREDIT_LEADS_VOL" in evidence["labels"]
    assert evidence["hy_ig_gap"] == 32.0
    assert evidence["hy_vix_gap"] == 27.0
    assert "20" in evidence["formula"]
    assert evidence["falsification"]
