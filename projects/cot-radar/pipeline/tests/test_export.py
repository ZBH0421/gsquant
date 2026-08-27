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
                "asset_manager_net_pct_oi": 10.0,
                "asset_manager_percentile": 70.0,
                "dealer_net_pct_oi": -4.0,
                "other_net_pct_oi": 1.0,
                "nonreportable_net_pct_oi": -1.0,
                "proxy_symbol": "SPY" if symbol == "ES" else "QQQ",
                "price_close": 650.0,
                "price_sma": 640.0,
                "price_momentum": 0.02,
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
    assert count == 6
    assert not (tmp_path / "prices.csv").exists()


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
