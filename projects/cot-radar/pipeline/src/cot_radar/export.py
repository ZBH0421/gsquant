from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from cot_radar.config import RadarSettings
from cot_radar.models import DataContractError
from cot_radar.narratives import build_evidence

ARTIFACT_NAMES = {
    "dashboard.json",
    "history.json",
    "backtest.json",
    "status.json",
    "signals.json",
    "signals.csv",
}


def _clean(value: Any) -> Any:
    if value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [_clean(row) for row in frame.to_dict(orient="records")]


def _backtest_summary(backtest: pd.DataFrame) -> list[dict[str, Any]]:
    if backtest.empty:
        return []
    valid = backtest.dropna(subset=["forward_return"]).copy()
    if valid.empty:
        return []
    grouped = valid.groupby(
        ["symbol", "state", "extreme_direction", "horizon_weeks"],
        dropna=False,
    )
    summary = grouped.agg(
        sample_count=("forward_return", "size"),
        median_forward_return=("forward_return", "median"),
        reversal_win_rate=("reversal_win", "mean"),
        median_max_adverse_excursion=("max_adverse_excursion", "median"),
    ).reset_index()
    return _records(summary)


def build_artifacts(
    signals: pd.DataFrame,
    backtest: pd.DataFrame,
    settings: RadarSettings,
    *,
    price_provider: str,
    generated_at: pd.Timestamp,
    notes: list[dict[str, str]],
) -> dict[str, Any]:
    if set(signals["symbol"].unique()) != {"ES", "NQ"}:
        raise DataContractError("signals must contain ES and NQ")
    current = signals.sort_values("report_date").groupby("symbol", sort=True).tail(1)
    markets: list[dict[str, Any]] = []
    for raw_snapshot in current.to_dict(orient="records"):
        snapshot = cast(dict[str, Any], raw_snapshot)
        evidence = asdict(build_evidence(snapshot, settings))
        market = _clean(snapshot)
        market["display_name"] = settings.markets[str(snapshot["symbol"])].display_name
        market["evidence"] = evidence
        market["subjective_notes"] = [
            note for note in notes if note["symbol"] == snapshot["symbol"]
        ]
        markets.append(market)

    latest = pd.Timestamp(signals["report_date"].max())
    age_days = (generated_at.tz_localize(None).normalize() - latest.normalize()).days
    history_columns = [
        "symbol",
        "report_date",
        "state",
        "extreme_direction",
        "leveraged_net_pct_oi",
        "leveraged_percentile",
        "asset_manager_net_pct_oi",
        "asset_manager_percentile",
        "price_normalized",
    ]
    available_history = [column for column in history_columns if column in signals.columns]
    signal_columns = [column for column in signals.columns if not column.startswith("_")]

    dashboard = {
        "generated_at": generated_at,
        "report_date": latest,
        "markets": markets,
        "methodology": {
            "lookback_weeks": settings.lookback_weeks,
            "minimum_history_weeks": settings.minimum_history_weeks,
            "extreme_high": settings.extreme_high,
            "extreme_low": settings.extreme_low,
            "unwind_memory_weeks": settings.unwind_memory_weeks,
            "price_sma_weeks": settings.price_sma_weeks,
            "price_momentum_weeks": settings.price_momentum_weeks,
            "price_proxies": {"ES": "SPY", "NQ": "QQQ"},
        },
    }
    status = {
        "generated_at": generated_at,
        "latest_report_date": latest,
        "price_provider": price_provider,
        "stale": age_days > settings.stale_after_days,
        "stale_after_days": settings.stale_after_days,
        "cftc_dataset": settings.dataset_id,
    }
    signal_records = _records(signals[signal_columns])
    return {
        "dashboard.json": _clean(dashboard),
        "history.json": {"history": _records(signals[available_history])},
        "backtest.json": {"summary": _backtest_summary(backtest), "events": _records(backtest)},
        "status.json": _clean(status),
        "signals.json": {"signals": signal_records},
        "signals.csv": signals[signal_columns].to_csv(index=False),
    }


def _validate_artifacts(artifacts: dict[str, Any]) -> None:
    if set(artifacts) != ARTIFACT_NAMES:
        raise DataContractError("artifact set is incomplete")
    dashboard = artifacts["dashboard.json"]
    if not isinstance(dashboard, dict):
        raise DataContractError("dashboard artifact must be an object")
    markets = dashboard.get("markets")
    if not isinstance(markets, list):
        raise DataContractError("dashboard markets must be a list")
    symbols = {market.get("symbol") for market in markets if isinstance(market, dict)}
    if symbols != {"ES", "NQ"}:
        raise DataContractError("dashboard must contain ES and NQ")


def write_artifacts(artifacts: dict[str, Any], output: Path) -> int:
    _validate_artifacts(artifacts)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".cot-radar-", dir=output.parent))
    try:
        for name, value in artifacts.items():
            target = temporary / name
            if isinstance(value, str):
                target.write_text(value, encoding="utf-8")
            else:
                target.write_text(
                    json.dumps(value, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        output.mkdir(parents=True, exist_ok=True)
        for name in ARTIFACT_NAMES:
            os.replace(temporary / name, output / name)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return len(ARTIFACT_NAMES)
