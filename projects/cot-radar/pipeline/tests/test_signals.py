import pandas as pd

from cot_radar.config import RadarSettings
from cot_radar.signals import classify_states


def _positions(percentiles: list[float], nets: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-06", periods=len(percentiles), freq="W-TUE")
    return pd.DataFrame(
        {
            "symbol": "ES",
            "report_date": dates,
            "available_at": dates
            + pd.Timedelta(days=3, hours=15, minutes=30),
            "leveraged_percentile": percentiles,
            "leveraged_net_pct_oi": nets,
        }
    )


def _prices(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-12-19", periods=len(closes), freq="W-FRI"),
            "close": closes,
        }
    )


def test_long_extreme_must_exit_before_confirmation() -> None:
    settings = RadarSettings.for_tests().with_overrides(
        price_sma_weeks=2,
        price_momentum_weeks=1,
        unwind_memory_weeks=4,
    )
    positions = _positions([50, 92, 85, 80], [1.0, 4.0, 3.0, 2.0])
    prices = _prices([100, 102, 104, 103, 99, 96, 92])

    result = classify_states(positions, prices, settings)

    assert result["state"].tolist()[-3:] == [
        "EXTREME_LONG",
        "UNWINDING_LONG",
        "CONFIRMED_BEARISH",
    ]


def test_price_weakness_inside_extreme_is_not_confirmed() -> None:
    settings = RadarSettings.for_tests().with_overrides(
        price_sma_weeks=2,
        price_momentum_weeks=1,
    )
    positions = _positions([50, 92, 95], [1.0, 4.0, 3.5])
    prices = _prices([100, 104, 103, 95, 90])

    result = classify_states(positions, prices, settings)

    assert result.iloc[-1]["state"] == "EXTREME_LONG"


def test_confirmation_delay_comes_from_settings() -> None:
    settings = RadarSettings.for_tests().with_overrides(
        price_sma_weeks=2,
        price_momentum_weeks=1,
        confirmation_delay_weeks=1,
    )
    positions = _positions([50, 92, 80], [1.0, 4.0, 2.0])
    prices = _prices([100, 104, 103, 98, 92, 88])

    result = classify_states(positions, prices, settings)

    assert result.iloc[-1]["state"] == "CONFIRMED_BEARISH"


def test_confirmed_state_falls_back_to_unwinding_when_price_confirmation_breaks() -> None:
    settings = RadarSettings.for_tests().with_overrides(
        price_sma_weeks=2,
        price_momentum_weeks=1,
        confirmation_delay_weeks=1,
    )
    positions = _positions([50, 92, 80, 75], [1.0, 4.0, 3.0, 2.0])
    prices = _prices([100, 104, 103, 98, 92, 96, 101])

    result = classify_states(positions, prices, settings)

    assert result.iloc[-2]["state"] == "CONFIRMED_BEARISH"
    assert result.iloc[-1]["state"] == "UNWINDING_LONG"


def test_unwind_memory_expiry_exits_to_normal() -> None:
    settings = RadarSettings.for_tests().with_overrides(
        price_sma_weeks=2,
        price_momentum_weeks=1,
        unwind_memory_weeks=2,
        confirmation_delay_weeks=1,
    )
    positions = _positions([50, 92, 80, 79, 78, 77], [1.0, 4.0, 3.0, 2.5, 2.0, 1.5])
    prices = _prices([100, 104, 103, 98, 92, 90, 88, 86, 84])

    result = classify_states(positions, prices, settings)

    assert result.iloc[-1]["state"] == "NORMAL"
    assert result.iloc[-1]["extreme_direction"] is None
