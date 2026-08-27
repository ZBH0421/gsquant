import json
from pathlib import Path

import pandas as pd

from cot_radar.config import RadarSettings
from cot_radar.pipeline import run_pipeline
from cot_radar.providers.prices import PriceResult


class FakeCftc:
    def fetch(self) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        dates = pd.date_range("2026-01-06", periods=5, freq="W-TUE")
        for symbol in ("ES", "NQ"):
            for index, date in enumerate(dates):
                rows.append(
                    {
                        "symbol": symbol,
                        "report_date": date,
                        "available_at": (
                            date.tz_localize("America/New_York")
                            + pd.Timedelta(days=3, hours=15, minutes=30)
                        ),
                        "market_name": symbol,
                        "contract_code": symbol,
                        "open_interest": 1000.0,
                        "dealer_long": 100.0,
                        "dealer_short": 120.0,
                        "asset_manager_long": 300.0 + index,
                        "asset_manager_short": 100.0,
                        "leveraged_long": 110.0 + index * 10,
                        "leveraged_short": 100.0,
                        "other_long": 50.0,
                        "other_short": 40.0,
                        "nonreportable_long": 20.0,
                        "nonreportable_short": 30.0,
                    }
                )
        return pd.DataFrame(rows)


class FakePrices:
    def fetch(self, symbol: str) -> PriceResult:
        multiplier = 1.0 if symbol == "SPY" else 1.5
        return PriceResult(
            pd.DataFrame(
                {
                    "date": pd.date_range("2025-12-19", periods=12, freq="W-FRI"),
                    "close": [multiplier * (100 + index) for index in range(12)],
                }
            ),
            "fixture",
        )


def test_run_pipeline_writes_identical_valid_artifacts(tmp_path: Path) -> None:
    settings = RadarSettings.for_tests().with_overrides(
        lookback_weeks=3,
        minimum_history_weeks=3,
        price_sma_weeks=2,
        price_momentum_weeks=1,
    )
    derived = tmp_path / "derived"
    web = tmp_path / "web"

    result = run_pipeline(
        settings=settings,
        cftc=FakeCftc(),
        prices=FakePrices(),
        notes=[],
        derived_output=derived,
        web_output=web,
        generated_at=pd.Timestamp("2026-02-14T00:00:00Z"),
    )

    assert result.generated_files == 6
    assert result.price_provider == "fixture"
    assert {path.name for path in derived.iterdir()} == {
        "dashboard.json",
        "history.json",
        "backtest.json",
        "status.json",
        "signals.json",
        "signals.csv",
    }
    assert (derived / "dashboard.json").read_bytes() == (
        web / "dashboard.json"
    ).read_bytes()
    status = json.loads((derived / "status.json").read_text())
    assert status["price_provider"] == "fixture"
