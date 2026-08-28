import pandas as pd

from conftest import load_module


def test_dashboard_contract_separates_facts_interpretation_confirmation_and_sources() -> None:
    export = load_module("credit_radar.export")
    config = load_module("credit_radar.config")
    settings = config.RadarSettings.for_tests()
    latest = pd.Series(
        {
            "date": pd.Timestamp("2026-08-27"),
            "state": "CREDIT_REVERSAL",
            "hy": 2.65,
            "ig": 0.80,
            "vix": 15.0,
            "hy_percentile": 80.0,
            "ig_percentile": 55.0,
            "vix_percentile": 45.0,
            "hy_change_5d": -0.10,
            "hy_change_20d": -0.30,
            "hy_sma50": 2.80,
            "spy_confirmed": True,
            "qqq_confirmed": False,
            "spy_close": 650.0,
            "spy_sma10w": 640.0,
            "spy_momentum_4w": 2.0,
            "qqq_close": 570.0,
            "qqq_sma10w": 575.0,
            "qqq_momentum_4w": -1.0,
        }
    )
    evidence = {
        "labels": ["HY_SPECIFIC_STRESS"],
        "hy_ig_gap": 25.0,
        "hy_vix_gap": 35.0,
        "formula": "gap >= 20",
        "falsification": "gap < 20",
    }
    provenance = {
        "HY": {"provider": "FRED", "series_id": "BAMLH0A0HYM2"},
        "IG": {"provider": "FRED", "series_id": "BAMLC0A0CM"},
        "VIX": {"provider": "FRED", "series_id": "VIXCLS"},
        "SPY": {"provider": "stooq", "proxy": "ES"},
        "QQQ": {"provider": "stooq", "proxy": "NQ"},
    }

    dashboard = export.build_dashboard(latest, evidence, [], provenance, settings)

    assert dashboard["state"] == "CREDIT_REVERSAL"
    assert dashboard["facts"]["hy_oas"] == 2.65
    assert dashboard["interpretation"]["label"] == "CREDIT_REVERSAL"
    assert dashboard["confirmation"]["SPY"]["confirmed"] is True
    assert dashboard["confirmation"]["QQQ"]["confirmed"] is False
    assert "not ES settlement" in dashboard["confirmation"]["SPY"]["proxy_label"]
    assert dashboard["sources"]["HY"]["series_id"] == "BAMLH0A0HYM2"
    assert dashboard["limitations"]["fred_ice_history_years"] == 3
