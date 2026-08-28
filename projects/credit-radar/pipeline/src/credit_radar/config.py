from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from credit_radar.models import DataContractError


@dataclass(frozen=True)
class RadarSettings:
    percentile_lookback: int
    percentile_minimum: int
    deteriorating_percentile: float
    stressed_percentile: float
    extreme_percentile: float
    spread_sma_days: int
    spread_short_change_days: int
    spread_medium_change_days: int
    stress_memory_days: int
    price_sma_weeks: int
    price_momentum_weeks: int
    divergence_percentile_gap: float
    minimum_backtest_samples: int
    backtest_horizons_weeks: tuple[int, ...]
    stale_after_days: int

    @classmethod
    def for_tests(
        cls,
        *,
        percentile_lookback: int = 756,
        percentile_minimum: int = 252,
        deteriorating_percentile: float = 70.0,
        stressed_percentile: float = 85.0,
        extreme_percentile: float = 95.0,
        spread_sma_days: int = 50,
        spread_short_change_days: int = 5,
        spread_medium_change_days: int = 20,
        stress_memory_days: int = 60,
        price_sma_weeks: int = 10,
        price_momentum_weeks: int = 4,
        divergence_percentile_gap: float = 20.0,
        minimum_backtest_samples: int = 10,
        backtest_horizons_weeks: tuple[int, ...] = (1, 4, 8, 13, 26),
        stale_after_days: int = 7,
    ) -> RadarSettings:
        settings = cls(
            percentile_lookback=percentile_lookback,
            percentile_minimum=percentile_minimum,
            deteriorating_percentile=deteriorating_percentile,
            stressed_percentile=stressed_percentile,
            extreme_percentile=extreme_percentile,
            spread_sma_days=spread_sma_days,
            spread_short_change_days=spread_short_change_days,
            spread_medium_change_days=spread_medium_change_days,
            stress_memory_days=stress_memory_days,
            price_sma_weeks=price_sma_weeks,
            price_momentum_weeks=price_momentum_weeks,
            divergence_percentile_gap=divergence_percentile_gap,
            minimum_backtest_samples=minimum_backtest_samples,
            backtest_horizons_weeks=backtest_horizons_weeks,
            stale_after_days=stale_after_days,
        )
        settings.validate()
        return settings

    @classmethod
    def load(cls, path: Path) -> RadarSettings:
        raw_obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw_obj, dict):
            raise DataContractError("credit radar settings must be a mapping")
        raw = cast(dict[str, Any], raw_obj)
        try:
            settings = cls(
                percentile_lookback=int(raw["percentile_lookback"]),
                percentile_minimum=int(raw["percentile_minimum"]),
                deteriorating_percentile=float(raw["deteriorating_percentile"]),
                stressed_percentile=float(raw["stressed_percentile"]),
                extreme_percentile=float(raw["extreme_percentile"]),
                spread_sma_days=int(raw["spread_sma_days"]),
                spread_short_change_days=int(raw["spread_short_change_days"]),
                spread_medium_change_days=int(raw["spread_medium_change_days"]),
                stress_memory_days=int(raw["stress_memory_days"]),
                price_sma_weeks=int(raw["price_sma_weeks"]),
                price_momentum_weeks=int(raw["price_momentum_weeks"]),
                divergence_percentile_gap=float(raw["divergence_percentile_gap"]),
                minimum_backtest_samples=int(raw["minimum_backtest_samples"]),
                backtest_horizons_weeks=tuple(int(item) for item in raw["backtest_horizons_weeks"]),
                stale_after_days=int(raw["stale_after_days"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataContractError(f"invalid credit radar settings: {exc}") from exc
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.percentile_lookback < 1:
            raise DataContractError("percentile_lookback must be positive")
        if not 1 <= self.percentile_minimum <= self.percentile_lookback:
            raise DataContractError("percentile_minimum must be within lookback")
        if not (
            0 <= self.deteriorating_percentile
            < self.stressed_percentile
            < self.extreme_percentile
            <= 100
        ):
            raise DataContractError("credit percentile thresholds must be ordered within 0..100")
        positive_ints = (
            self.spread_sma_days,
            self.spread_short_change_days,
            self.spread_medium_change_days,
            self.stress_memory_days,
            self.price_sma_weeks,
            self.price_momentum_weeks,
            self.minimum_backtest_samples,
            self.stale_after_days,
        )
        if any(value < 1 for value in positive_ints):
            raise DataContractError("window and sample settings must be positive")
        if not 0 <= self.divergence_percentile_gap <= 100:
            raise DataContractError("divergence_percentile_gap must be within 0..100")
        if not self.backtest_horizons_weeks or any(
            horizon < 1 for horizon in self.backtest_horizons_weeks
        ):
            raise DataContractError("backtest horizons must be positive")


def load_settings(path: Path) -> RadarSettings:
    return RadarSettings.load(path)
