from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from cot_radar.models import DataContractError


def _local_date(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("America/New_York").tz_localize(None)
    return timestamp.normalize()


def summarize_events(
    events: pd.DataFrame,
    prices: pd.DataFrame,
    horizons: Iterable[int],
) -> pd.DataFrame:
    required_events = {"symbol", "state", "available_at", "extreme_direction"}
    required_prices = {"symbol", "date", "close"}
    if not required_events.issubset(events.columns):
        raise DataContractError("event frame is missing required columns")
    if not required_prices.issubset(prices.columns):
        raise DataContractError("backtest price frame is missing required columns")

    output: list[dict[str, object]] = []
    horizon_values = tuple(int(value) for value in horizons)
    for event in events.to_dict(orient="records"):
        symbol = str(event["symbol"])
        market_prices = prices.loc[prices["symbol"] == symbol, ["date", "close"]].copy()
        market_prices["date"] = pd.to_datetime(market_prices["date"]).dt.normalize()
        market_prices = market_prices.sort_values("date", ignore_index=True)
        available_date = _local_date(event["available_at"])
        matches = market_prices.index[market_prices["date"] >= available_date]
        baseline_index = int(matches[0]) if len(matches) else -1

        for horizon in horizon_values:
            row: dict[str, object] = {
                "symbol": symbol,
                "state": str(event["state"]),
                "extreme_direction": event["extreme_direction"],
                "available_date": available_date,
                "horizon_weeks": horizon,
                "baseline_date": pd.NaT,
                "forward_return": np.nan,
                "reversal_win": None,
                "max_adverse_excursion": np.nan,
            }
            if baseline_index >= 0:
                baseline = float(market_prices.iloc[baseline_index]["close"])
                row["baseline_date"] = market_prices.iloc[baseline_index]["date"]
                end_index = baseline_index + horizon
                if end_index < len(market_prices):
                    path = (
                        market_prices.iloc[baseline_index + 1 : end_index + 1]["close"]
                        .astype(float)
                        .div(baseline)
                        .sub(1.0)
                    )
                    forward = float(path.iloc[-1])
                    direction = str(event["extreme_direction"])
                    row["forward_return"] = forward
                    row["reversal_win"] = (
                        forward < 0 if direction == "long" else forward > 0
                    )
                    if direction == "long":
                        row["max_adverse_excursion"] = max(0.0, float(path.max()))
                    else:
                        row["max_adverse_excursion"] = max(0.0, float(-path.min()))
            output.append(row)
    return pd.DataFrame(output)
