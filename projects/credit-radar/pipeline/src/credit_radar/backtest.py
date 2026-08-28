from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from credit_radar.config import RadarSettings
from credit_radar.models import DataContractError


TARGET_STATES = {"STRESSED", "EXTREME_STRESS", "CREDIT_REVERSAL", "CONFIRMED_RISK_ON"}
PROXY_LABELS = {
    "SPY": "ES proxy (SPY), not ES settlement",
    "QQQ": "NQ proxy (QQQ), not NQ settlement",
}


def build_event_study(
    states: pd.DataFrame,
    prices_by_symbol: dict[str, pd.DataFrame],
    settings: RadarSettings,
    *,
    provider: str,
) -> list[dict[str, object]]:
    if not {"date", "state"}.issubset(states.columns):
        raise DataContractError("state history requires date and state")
    ordered_states = states[["date", "state"]].copy().sort_values("date", ignore_index=True)
    ordered_states["date"] = pd.to_datetime(ordered_states["date"], errors="coerce")
    previous = ordered_states["state"].shift(1)
    entries = ordered_states[
        ordered_states["state"].isin(TARGET_STATES) & (ordered_states["state"] != previous)
    ]

    grouped: dict[tuple[str, str, int], list[tuple[float, float, float, pd.Timestamp]]] = (
        defaultdict(list)
    )
    for symbol, raw_prices in prices_by_symbol.items():
        if symbol not in PROXY_LABELS:
            raise DataContractError(f"unsupported backtest proxy: {symbol}")
        prices = raw_prices[["date", "close"]].copy().sort_values("date", ignore_index=True)
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna().reset_index(drop=True)
        if prices.empty:
            continue
        price_dates = pd.DatetimeIndex(prices["date"])
        for _, event in entries.iterrows():
            event_date = pd.Timestamp(event["date"])
            start_index = int(price_dates.searchsorted(event_date, side="left"))
            if start_index >= len(prices):
                continue
            start_close = float(prices.iloc[start_index]["close"])
            state = str(event["state"])
            for horizon in settings.backtest_horizons_weeks:
                end_index = start_index + horizon
                if end_index >= len(prices):
                    continue
                path = pd.to_numeric(
                    prices.iloc[start_index : end_index + 1]["close"], errors="coerce"
                ).astype(float)
                if path.isna().any() or start_close <= 0:
                    continue
                path_returns = (path / start_close - 1.0) * 100.0
                forward_return = float(path_returns.iloc[-1])
                mae = float(path_returns.min())
                mfe = float(path_returns.max())
                grouped[(symbol, state, horizon)].append(
                    (forward_return, mae, mfe, event_date)
                )

    rows: list[dict[str, object]] = []
    for (symbol, state, horizon), observations in sorted(grouped.items()):
        returns = np.array([item[0] for item in observations], dtype=float)
        maes = np.array([item[1] for item in observations], dtype=float)
        mfes = np.array([item[2] for item in observations], dtype=float)
        dates = [item[3] for item in observations]
        sample_size = len(observations)
        positive_rate: float | None = None
        if sample_size >= settings.minimum_backtest_samples:
            positive_rate = float((returns > 0).mean() * 100.0)
        rows.append(
            {
                "symbol": symbol,
                "state": state,
                "horizon_weeks": horizon,
                "n": sample_size,
                "median_return": float(np.median(returns)),
                "positive_return_rate": positive_rate,
                "median_mae": float(np.median(maes)),
                "median_mfe": float(np.median(mfes)),
                "max_adverse_excursion": float(maes.min()),
                "max_favorable_excursion": float(mfes.max()),
                "sample_start": min(dates).date().isoformat(),
                "sample_end": max(dates).date().isoformat(),
                "small_sample": sample_size < settings.minimum_backtest_samples,
                "provider": provider,
                "proxy_label": PROXY_LABELS[symbol],
            }
        )
    return rows
