from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from cot_radar.analytics import add_position_metrics
from cot_radar.backtest import summarize_events
from cot_radar.config import RadarSettings
from cot_radar.export import build_artifacts, write_artifacts
from cot_radar.models import DataContractError, PipelineResult
from cot_radar.providers.prices import PriceResult
from cot_radar.signals import classify_states


class CftcLike(Protocol):
    def fetch(self) -> pd.DataFrame: ...


class PriceLike(Protocol):
    def fetch(self, symbol: str) -> PriceResult: ...


def _signal_events(signals: pd.DataFrame) -> pd.DataFrame:
    events: list[pd.DataFrame] = []
    for _, market in signals.groupby("symbol", sort=False):
        ordered = market.sort_values("report_date").copy()
        changed = ordered["state"].ne(ordered["state"].shift(1))
        events.append(
            ordered.loc[
                changed & ordered["state"].ne("NORMAL"),
                ["symbol", "state", "available_at", "extreme_direction"],
            ]
        )
    return pd.concat(events, ignore_index=True) if events else pd.DataFrame()


def run_pipeline(
    *,
    settings: RadarSettings,
    cftc: CftcLike,
    prices: PriceLike,
    notes: list[dict[str, str]],
    derived_output: Path,
    web_output: Path,
    generated_at: pd.Timestamp,
) -> PipelineResult:
    raw_positions = cftc.fetch()
    metrics = add_position_metrics(raw_positions, settings)

    signal_frames: list[pd.DataFrame] = []
    price_frames: list[pd.DataFrame] = []
    providers: set[str] = set()
    for symbol, market in settings.markets.items():
        positions = metrics.loc[metrics["symbol"] == symbol].copy()
        if positions.empty:
            raise DataContractError(f"CFTC data contains no rows for {symbol}")
        result = prices.fetch(market.proxy_symbol)
        providers.add(result.provider)
        classified = classify_states(positions, result.frame, settings)
        classified["proxy_symbol"] = market.proxy_symbol
        signal_frames.append(classified)

        price_frame = result.frame.copy()
        price_frame["symbol"] = symbol
        price_frames.append(price_frame)

    signals = pd.concat(signal_frames, ignore_index=True).sort_values(
        ["symbol", "report_date"],
        ignore_index=True,
    )
    combined_prices = pd.concat(price_frames, ignore_index=True)
    events = _signal_events(signals)
    if events.empty:
        backtest = pd.DataFrame()
    else:
        backtest = summarize_events(
            events,
            combined_prices,
            settings.backtest_horizons,
        )

    provider_name = (
        next(iter(providers))
        if len(providers) == 1
        else f"mixed:{','.join(sorted(providers))}"
    )
    artifacts = build_artifacts(
        signals,
        backtest,
        settings,
        price_provider=provider_name,
        generated_at=generated_at,
        notes=notes,
    )

    count = write_artifacts(artifacts, derived_output)
    write_artifacts(artifacts, web_output)
    latest = pd.Timestamp(signals["report_date"].max()).date().isoformat()
    return PipelineResult(count, latest, provider_name)
