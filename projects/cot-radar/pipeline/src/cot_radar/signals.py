from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from gs_quant.timeseries import diff as gs_diff
from gs_quant.timeseries import moving_average

from cot_radar.config import RadarSettings
from cot_radar.models import DataContractError


def _price_features(prices: pd.DataFrame, settings: RadarSettings) -> pd.DataFrame:
    if not {"date", "close"}.issubset(prices.columns):
        raise DataContractError("price frame requires date and close")
    result = prices[["date", "close"]].copy()
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result = result.sort_values("date", ignore_index=True)
    indexed = pd.Series(
        result["close"].to_numpy(dtype=float),
        index=pd.DatetimeIndex(result["date"]),
    )
    sma = moving_average(indexed, settings.price_sma_weeks).reindex(indexed.index)
    result["price_sma"] = sma.to_numpy()
    change = gs_diff(indexed, settings.price_momentum_weeks)
    result["price_momentum"] = (
        change / indexed.shift(settings.price_momentum_weeks)
    ).to_numpy()
    first_close = float(result["close"].iloc[0])
    result["price_normalized"] = 100.0 * result["close"] / first_close
    return result


def _local_release_date(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("America/New_York").tz_localize(None)
    return timestamp.normalize()


def classify_states(
    positions: pd.DataFrame,
    prices: pd.DataFrame,
    settings: RadarSettings,
) -> pd.DataFrame:
    required = {
        "symbol",
        "report_date",
        "available_at",
        "leveraged_percentile",
        "leveraged_net_pct_oi",
    }
    missing = required.difference(positions.columns)
    if missing:
        raise DataContractError(f"signal data missing columns: {', '.join(sorted(missing))}")

    left = positions.sort_values("report_date").copy()
    left["_availability_date"] = left["available_at"].map(_local_release_date)
    right = _price_features(prices, settings)
    merged = pd.merge_asof(
        left.sort_values("_availability_date"),
        right,
        left_on="_availability_date",
        right_on="date",
        direction="forward",
        tolerance=pd.Timedelta(days=7),
    ).sort_values("report_date", ignore_index=True)

    states: list[str] = []
    directions: list[str | None] = []
    last_extreme: str | None = None
    reports_since_extreme = settings.unwind_memory_weeks + 1
    previous_net: float | None = None

    for row in merged.to_dict(orient="records"):
        percentile = float(row["leveraged_percentile"])
        net = float(row["leveraged_net_pct_oi"])
        state = "NORMAL"
        direction: str | None = None

        if np.isfinite(percentile) and percentile >= settings.extreme_high:
            state = "EXTREME_LONG"
            direction = "long"
            last_extreme = "long"
            reports_since_extreme = 0
        elif np.isfinite(percentile) and percentile <= settings.extreme_low:
            state = "EXTREME_SHORT"
            direction = "short"
            last_extreme = "short"
            reports_since_extreme = 0
        else:
            reports_since_extreme += 1
            change = np.nan if previous_net is None else net - previous_net
            is_unwind = (
                last_extreme == "long"
                and reports_since_extreme <= settings.unwind_memory_weeks
                and np.isfinite(change)
                and change < 0
            ) or (
                last_extreme == "short"
                and reports_since_extreme <= settings.unwind_memory_weeks
                and np.isfinite(change)
                and change > 0
            )
            if is_unwind:
                direction = last_extreme
                state = "UNWINDING_LONG" if direction == "long" else "UNWINDING_SHORT"
                price = float(row["close"]) if pd.notna(row.get("close")) else np.nan
                price_sma = (
                    float(row["price_sma"]) if pd.notna(row.get("price_sma")) else np.nan
                )
                momentum = (
                    float(row["price_momentum"])
                    if pd.notna(row.get("price_momentum"))
                    else np.nan
                )
                if reports_since_extreme >= 2 and np.isfinite(
                    [price, price_sma, momentum]
                ).all():
                    if direction == "long" and price < price_sma and momentum < 0:
                        state = "CONFIRMED_BEARISH"
                    elif direction == "short" and price > price_sma and momentum > 0:
                        state = "CONFIRMED_BULLISH"
        previous_net = net
        states.append(state)
        directions.append(direction)

    merged["state"] = states
    merged["extreme_direction"] = directions
    return merged.drop(columns=["_availability_date"])
