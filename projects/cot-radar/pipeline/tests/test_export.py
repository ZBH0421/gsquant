import json
from pathlib import Path

import pandas as pd
import pytest

from cot_radar.config import RadarSettings
from cot_radar.export import build_artifacts, write_artifacts
from cot_radar.models import DataContractError


def _signals() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "report_date": pd.Timestamp("2026-08-18"),
                "available_at": pd.Timestamp("2026-08-21 15:30", tz="America/New_York"),
                "state": "NORMAL",
                "extreme_direction": None,
                "leveraged_net_pct_oi": 2.0,
                "leveraged_percentile": 55.0,
                "leveraged_zscore": 0.2,
                "leveraged_weekly_change": 0.1,
                "leveraged_four_week_change": 0.4,
                "asset_manager_net_pct_oi": 10.0,
                "asset_manager_percentile": 70.0,
                "asset_manager_weekly_change": 0.2,
                "asset_manager_four_week_change": 0.8,
                "dealer_net_pct_oi": -4.0,
                "other_net_pct_oi": 1.0,
                "nonreportable_net_pct_oi": -1.0,
                "proxy_symbol": "SPY" if symbol == "ES" else "QQQ",
                "close": 650.0 if symbol == "ES" else 580.0,
                "price_sma": 640.0 if symbol == "ES" else 590.0,
                "price_momentum": 0.02 if symbol == "ES" else -0.01,
                "price_normalized": 100.0,
            }
            for symbol in ("ES", "NQ")
        ]
    )


def test_artifacts_include_both_markets_and_methodology(tmp_path: Path) -> None:
    artifacts = build_artifacts(
        _signals(),
        pd.DataFrame(),
        RadarSettings.for_tests(),
        price_provider="stooq",
        generated_at=pd.Timestamp("2026-08-22T00:00:00Z"),
        notes=[],
    )
    count = write_artifacts(artifacts, tmp_path)
    dashboard = json.loads((tmp_path / "dashboard.json").read_text())

    assert {item["symbol"] for item in dashboard["markets"]} == {"ES", "NQ"}
    assert dashboard["methodology"]["lookback_weeks"] == 156
    assert set(dashboard["methodology"]["state_machine"]) == {
        "NORMAL",
        "EXTREME_LONG",
        "EXTREME_SHORT",
        "UNWINDING_LONG",
        "UNWINDING_SHORT",
        "CONFIRMED_BEARISH",
        "CONFIRMED_BULLISH",
    }
    assert count == 6
    assert not (tmp_path / "prices.csv").exists()


def test_status_distinguishes_report_release_fetch_and_update_times() -> None:
    artifacts = build_artifacts(
        _signals(),
        pd.DataFrame(),
        RadarSettings.for_tests(),
        price_provider="stooq",
        generated_at=pd.Timestamp("2026-08-28T08:00:00Z"),
        notes=[],
    )

    status = artifacts["status.json"]
    assert status["latest_report_date"] == "2026-08-18T00:00:00"
    assert status["scheduled_release_at"].startswith("2026-08-21T15:30:00-04:00")
    assert status["fetched_at"] == "2026-08-28T08:00:00+00:00"
    assert status["last_successful_update_at"] == "2026-08-28T08:00:00+00:00"
    assert status["next_scheduled_update_at"].startswith("2026-08-29T08:00:00+08:00")
    assert status["next_expected_report_date"] == "2026-08-25T00:00:00"
    assert status["next_expected_release_at"].startswith("2026-08-28T15:30:00-04:00")
    assert status["cftc_dataset"] == "gpe5-46if"
    assert status["price_provider"] == "stooq"
    assert status["publication_state"] == "waiting_for_cftc"
    assert status["stale"] is False
    assert "等待 CFTC 發布" in status["warning"]


def test_status_becomes_stale_only_after_publication_grace_window() -> None:
    artifacts = build_artifacts(
        _signals(),
        pd.DataFrame(),
        RadarSettings.for_tests(),
        price_provider="stooq",
        generated_at=pd.Timestamp("2026-09-01T12:00:00Z"),
        notes=[],
    )

    status = artifacts["status.json"]
    assert status["publication_state"] == "stale"
    assert status["stale"] is True
    assert "資料可能已過期" in status["warning"]


def test_comparison_is_formula_backed_and_names_the_more_extreme_market() -> None:
    signals = _signals()
    signals.loc[signals["symbol"] == "ES", "leveraged_percentile"] = 95.0
    signals.loc[signals["symbol"] == "NQ", "leveraged_percentile"] = 70.0
    signals.loc[signals["symbol"] == "ES", "leveraged_net_pct_oi"] = 8.0
    signals.loc[signals["symbol"] == "NQ", "leveraged_net_pct_oi"] = 3.0
    signals.loc[signals["symbol"] == "ES", "leveraged_weekly_change"] = 1.5
    signals.loc[signals["symbol"] == "ES", "leveraged_four_week_change"] = 4.0

    artifacts = build_artifacts(
        signals,
        pd.DataFrame(),
        RadarSettings.for_tests(),
        price_provider="stooq",
        generated_at=pd.Timestamp("2026-08-22T00:00:00Z"),
        notes=[],
    )

    comparison = artifacts["dashboard.json"]["comparison"]
    assert comparison["markets"]["ES"]["leveraged_net_pct_oi"] == 8.0
    assert comparison["markets"]["ES"]["leveraged_change_1w"] == 1.5
    assert comparison["markets"]["ES"]["leveraged_change_4w"] == 4.0
    assert comparison["markets"]["ES"]["price_momentum_4w"] == 0.02
    assert comparison["markets"]["ES"]["price_vs_sma_10w"] == pytest.approx(0.015625)
    assert comparison["position_divergence"] is True
    assert comparison["percentile_gap"] == 25.0
    assert comparison["more_extreme_market"] == "ES"
    assert comparison["synchronized_crowding"] is False
    assert "95.0" in comparison["evidence"]
    assert "70.0" in comparison["evidence"]
    assert "20.0" in comparison["falsification"]


def test_small_backtest_samples_suppress_win_rate_conclusions() -> None:
    backtest = pd.DataFrame(
        [
            {
                "symbol": "ES",
                "state": "CONFIRMED_BEARISH",
                "extreme_direction": "long",
                "horizon_weeks": 4,
                "baseline_date": pd.Timestamp("2026-07-03"),
                "forward_return": -0.02,
                "reversal_win": True,
                "max_adverse_excursion": 0.01,
            },
            {
                "symbol": "ES",
                "state": "CONFIRMED_BEARISH",
                "extreme_direction": "long",
                "horizon_weeks": 4,
                "baseline_date": pd.Timestamp("2026-08-07"),
                "forward_return": -0.01,
                "reversal_win": True,
                "max_adverse_excursion": 0.02,
            },
        ]
    )
    artifacts = build_artifacts(
        _signals(),
        backtest,
        RadarSettings.for_tests(),
        price_provider="stooq",
        generated_at=pd.Timestamp("2026-08-22T00:00:00Z"),
        notes=[],
    )

    row = artifacts["backtest.json"]["summary"][0]
    assert row["sample_count"] == 2
    assert row["small_sample"] is True
    assert row["reversal_win_rate"] is None
    assert row["signal_direction"] == "bearish"
    assert row["proxy_symbol"] == "SPY"
    assert row["price_provider"] == "stooq"
    assert row["period_start"].startswith("2026-07-03")
    assert row["period_end"].startswith("2026-08-07")
    metadata = artifacts["backtest.json"]["metadata"]
    assert metadata["horizons_weeks"] == [1, 4, 8, 13]
    assert metadata["minimum_sample_size"] == 10
    assert "週二" in metadata["availability_assumption"]
    assert "週五" in metadata["availability_assumption"]
    assert "延遲" in metadata["historical_release_limit"]
    assert "未來" in metadata["disclaimer"]


def test_failed_write_preserves_previous_snapshot(tmp_path: Path) -> None:
    (tmp_path / "dashboard.json").write_text('{"stable": true}')
    before = (tmp_path / "dashboard.json").read_bytes()

    with pytest.raises(DataContractError):
        write_artifacts({"dashboard.json": {"markets": [{"symbol": "ES"}]}}, tmp_path)

    assert (tmp_path / "dashboard.json").read_bytes() == before


def test_artifact_json_converts_pandas_nat_to_null(tmp_path: Path) -> None:
    signals = _signals()
    signals["unavailable_date"] = pd.NaT
    artifacts = build_artifacts(
        signals,
        pd.DataFrame(),
        RadarSettings.for_tests(),
        price_provider="yahoo_finance",
        generated_at=pd.Timestamp("2026-08-22T00:00:00Z"),
        notes=[],
    )

    write_artifacts(artifacts, tmp_path)

    payload = json.loads((tmp_path / "signals.json").read_text())
    assert payload["signals"][0]["unavailable_date"] is None
