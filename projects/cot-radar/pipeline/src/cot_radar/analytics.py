from __future__ import annotations

import numpy as np
import pandas as pd
from gs_quant.timeseries import diff as gs_diff

from cot_radar.config import RadarSettings
from cot_radar.models import DataContractError

POSITION_CATEGORIES = (
    "leveraged",
    "asset_manager",
    "dealer",
    "other",
    "nonreportable",
)


def prior_percentile(series: pd.Series, window: int, minimum: int) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    result = pd.Series(np.nan, index=values.index, dtype=float)
    for position in range(len(values)):
        current = values.iloc[position]
        history = values.iloc[max(0, position - window) : position].dropna()
        if pd.notna(current) and len(history) >= minimum:
            result.iloc[position] = float((history <= current).mean() * 100.0)
    return result


def prior_zscore(series: pd.Series, window: int, minimum: int) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    result = pd.Series(np.nan, index=values.index, dtype=float)
    for position in range(len(values)):
        current = values.iloc[position]
        history = values.iloc[max(0, position - window) : position].dropna()
        if pd.notna(current) and len(history) >= minimum:
            standard_deviation = float(history.std(ddof=1))
            if standard_deviation > 0:
                result.iloc[position] = (
                    float(current) - float(history.mean())
                ) / standard_deviation
    return result


def _difference(series: pd.Series, observations: int = 1) -> pd.Series:
    indexed = pd.Series(
        series.to_numpy(dtype=float),
        index=pd.date_range("2000-01-01", periods=len(series), freq="D"),
    )
    calculated = gs_diff(indexed, observations)
    return pd.Series(calculated.to_numpy(dtype=float), index=series.index)


def add_position_metrics(frame: pd.DataFrame, settings: RadarSettings) -> pd.DataFrame:
    required = {"symbol", "report_date", "open_interest"}
    for category in POSITION_CATEGORIES:
        required.update({f"{category}_long", f"{category}_short"})
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DataContractError(f"position data missing columns: {', '.join(missing)}")

    results: list[pd.DataFrame] = []
    ordered = frame.sort_values(["symbol", "report_date"]).reset_index(drop=True)
    for _, group in ordered.groupby("symbol", sort=False):
        market = group.copy()
        open_interest = pd.to_numeric(market["open_interest"], errors="coerce")
        if open_interest.isna().any() or (open_interest <= 0).any():
            raise DataContractError("open_interest must be positive numeric data")

        for category in POSITION_CATEGORIES:
            long_values = pd.to_numeric(market[f"{category}_long"], errors="coerce")
            short_values = pd.to_numeric(market[f"{category}_short"], errors="coerce")
            if long_values.isna().any() or short_values.isna().any():
                raise DataContractError(f"{category} positions must be numeric")
            net = long_values - short_values
            net_pct = 100.0 * net / open_interest
            market[f"{category}_net"] = net
            market[f"{category}_net_pct_oi"] = net_pct
            market[f"{category}_weekly_change"] = _difference(net_pct)
            market[f"{category}_four_week_change"] = _difference(net_pct, 4)

            if category in {"leveraged", "asset_manager"}:
                market[f"{category}_percentile"] = prior_percentile(
                    net_pct,
                    settings.lookback_weeks,
                    settings.minimum_history_weeks,
                )
                market[f"{category}_zscore"] = prior_zscore(
                    net_pct,
                    settings.lookback_weeks,
                    settings.minimum_history_weeks,
                )
        results.append(market)

    return pd.concat(results, ignore_index=True).sort_values(
        ["symbol", "report_date"],
        ignore_index=True,
    )
