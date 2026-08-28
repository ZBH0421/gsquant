from __future__ import annotations

import numpy as np
import pandas as pd
from gs_quant.timeseries import moving_average as gs_moving_average

from credit_radar.config import RadarSettings
from credit_radar.models import DataContractError


def prior_percentile(series: pd.Series, lookback: int, min_periods: int) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    result = pd.Series(np.nan, index=values.index, dtype=float)
    for position in range(len(values)):
        current = values.iloc[position]
        history = values.iloc[max(0, position - lookback) : position].dropna()
        if pd.notna(current) and len(history) >= min_periods:
            result.iloc[position] = float((history <= current).mean() * 100.0)
    return result


def _moving_average(series: pd.Series, window: int) -> pd.Series:
    indexed = pd.Series(
        pd.to_numeric(series, errors="coerce").to_numpy(dtype=float),
        index=pd.date_range("2000-01-01", periods=len(series), freq="D"),
    )
    calculated = gs_moving_average(indexed, window).reindex(indexed.index)
    return pd.Series(calculated.to_numpy(dtype=float), index=series.index)


def compute_credit_features(frame: pd.DataFrame, settings: RadarSettings) -> pd.DataFrame:
    required = {"date", "hy", "ig", "vix"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DataContractError(f"credit data missing columns: {', '.join(missing)}")
    result = frame.copy().sort_values("date", ignore_index=True)
    result["date"] = (
        pd.to_datetime(result["date"], errors="coerce")
        .dt.tz_localize(None)
        .dt.normalize()
    )
    for column in ("hy", "ig", "vix"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[["date", "hy", "ig", "vix"]].isna().any().any():
        raise DataContractError("credit data contains invalid dates or values")

    result["hy_percentile"] = prior_percentile(
        result["hy"], settings.percentile_lookback, settings.percentile_minimum
    )
    result["ig_percentile"] = prior_percentile(
        result["ig"], settings.percentile_lookback, settings.percentile_minimum
    )
    result["vix_percentile"] = prior_percentile(
        result["vix"], settings.percentile_lookback, settings.percentile_minimum
    )
    result["hy_sma50"] = _moving_average(result["hy"], settings.spread_sma_days)
    result["hy_change_5d"] = result["hy"].diff(settings.spread_short_change_days)
    result["hy_change_20d"] = result["hy"].diff(settings.spread_medium_change_days)
    result["hy_high_20d"] = (
        result["hy"].shift(1).rolling(settings.spread_medium_change_days, min_periods=1).max()
    )
    return result


def compute_price_features(frame: pd.DataFrame, settings: RadarSettings) -> pd.DataFrame:
    required = {"date", "close"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DataContractError(f"price data missing columns: {', '.join(missing)}")
    result = frame[["date", "close"]].copy().sort_values("date", ignore_index=True)
    result["date"] = (
        pd.to_datetime(result["date"], errors="coerce")
        .dt.tz_localize(None)
        .dt.normalize()
    )
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    if result.isna().any().any() or (result["close"] <= 0).any():
        raise DataContractError("price data contains invalid dates or closes")
    result["sma"] = _moving_average(result["close"], settings.price_sma_weeks)
    result["momentum"] = result["close"].pct_change(settings.price_momentum_weeks) * 100.0
    return result
