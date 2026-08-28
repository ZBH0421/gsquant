from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import yaml

from cot_radar.models import DataContractError


@dataclass(frozen=True)
class MarketSettings:
    display_name: str
    proxy_symbol: str
    contract_patterns: tuple[str, ...]


@dataclass(frozen=True)
class RadarSettings:
    dataset_id: str
    base_url: str
    page_size: int
    markets: dict[str, MarketSettings]
    lookback_weeks: int
    minimum_history_weeks: int
    extreme_high: float
    extreme_low: float
    unwind_memory_weeks: int
    price_sma_weeks: int
    price_momentum_weeks: int
    stale_after_days: int
    backtest_horizons: tuple[int, ...]

    @classmethod
    def for_tests(cls) -> RadarSettings:
        return cls(
            dataset_id="gpe5-46if",
            base_url="https://publicreporting.cftc.gov/resource",
            page_size=50_000,
            markets={
                "ES": MarketSettings(
                    "E-mini S&P 500",
                    "SPY",
                    ("E-MINI S&P 500", "S&P 500 CONSOLIDATED"),
                ),
                "NQ": MarketSettings(
                    "E-mini Nasdaq-100",
                    "QQQ",
                    ("NASDAQ-100", "NASDAQ MINI"),
                ),
            },
            lookback_weeks=156,
            minimum_history_weeks=52,
            extreme_high=90.0,
            extreme_low=10.0,
            unwind_memory_weeks=4,
            price_sma_weeks=10,
            price_momentum_weeks=4,
            stale_after_days=10,
            backtest_horizons=(1, 4, 8, 13),
        )

    def with_overrides(
        self,
        *,
        lookback_weeks: int | None = None,
        minimum_history_weeks: int | None = None,
        unwind_memory_weeks: int | None = None,
        price_sma_weeks: int | None = None,
        price_momentum_weeks: int | None = None,
    ) -> RadarSettings:
        return replace(
            self,
            lookback_weeks=self.lookback_weeks if lookback_weeks is None else lookback_weeks,
            minimum_history_weeks=(
                self.minimum_history_weeks
                if minimum_history_weeks is None
                else minimum_history_weeks
            ),
            unwind_memory_weeks=(
                self.unwind_memory_weeks
                if unwind_memory_weeks is None
                else unwind_memory_weeks
            ),
            price_sma_weeks=(
                self.price_sma_weeks if price_sma_weeks is None else price_sma_weeks
            ),
            price_momentum_weeks=(
                self.price_momentum_weeks
                if price_momentum_weeks is None
                else price_momentum_weeks
            ),
        )


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DataContractError(f"{name} must be a mapping")
    return cast(dict[str, Any], value)


def load_settings(path: Path) -> RadarSettings:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "settings")
    dataset = _mapping(raw.get("dataset"), "dataset")
    signal = _mapping(raw.get("signals"), "signals")
    market_rows = _mapping(raw.get("markets"), "markets")

    markets: dict[str, MarketSettings] = {}
    for symbol, value in market_rows.items():
        row = _mapping(value, f"market {symbol}")
        patterns = row.get("contract_patterns")
        if not isinstance(patterns, list) or not patterns:
            raise DataContractError(f"market {symbol} requires contract_patterns")
        markets[symbol] = MarketSettings(
            display_name=str(row["display_name"]),
            proxy_symbol=str(row["proxy_symbol"]),
            contract_patterns=tuple(str(item) for item in patterns),
        )

    settings = RadarSettings(
        dataset_id=str(dataset["id"]),
        base_url=str(dataset["base_url"]).rstrip("/"),
        page_size=int(dataset["page_size"]),
        markets=markets,
        lookback_weeks=int(signal["lookback_weeks"]),
        minimum_history_weeks=int(signal["minimum_history_weeks"]),
        extreme_high=float(signal["extreme_high"]),
        extreme_low=float(signal["extreme_low"]),
        unwind_memory_weeks=int(signal["unwind_memory_weeks"]),
        price_sma_weeks=int(signal["price_sma_weeks"]),
        price_momentum_weeks=int(signal["price_momentum_weeks"]),
        stale_after_days=int(signal["stale_after_days"]),
        backtest_horizons=tuple(int(item) for item in signal["backtest_horizons"]),
    )
    if set(settings.markets) != {"ES", "NQ"}:
        raise DataContractError("MVP settings must define exactly ES and NQ")
    if not 0 <= settings.extreme_low < settings.extreme_high <= 100:
        raise DataContractError("extreme thresholds must be ordered within 0..100")
    if settings.minimum_history_weeks > settings.lookback_weeks:
        raise DataContractError("minimum history cannot exceed lookback")
    return settings
