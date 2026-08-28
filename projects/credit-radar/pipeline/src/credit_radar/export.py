from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from credit_radar.config import RadarSettings


INTERPRETATIONS = {
    "NORMAL": "信用市場未觸發預設壓力條件。",
    "DETERIORATING": "HY 利差與趨勢顯示信用環境正在惡化，但尚未進入高壓力區。",
    "STRESSED": "HY 壓力已進入歷史高分位區，這不是直接的交易訊號。",
    "EXTREME_STRESS": "HY 壓力處於公開歷史樣本的極端區，需等待修復證據。",
    "STABILIZING": "近期曾有高壓力，利差惡化速度正在放慢，但尚未完成反轉。",
    "CREDIT_REVERSAL": "近期高壓力後，HY 已低於趨勢線且 20D 變化轉負。",
    "CONFIRMED_RISK_ON": "信用修復已出現，且至少一個股票代理價格同時確認。",
}


def _finite_or_none(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_dashboard(
    latest: pd.Series,
    evidence: dict[str, object],
    backtest: list[dict[str, object]],
    provenance: dict[str, dict[str, object]],
    settings: RadarSettings,
) -> dict[str, object]:
    state = str(latest["state"])
    spy_confirmed = bool(latest.get("spy_confirmed", False))
    qqq_confirmed = bool(latest.get("qqq_confirmed", False))
    return {
        "as_of": pd.Timestamp(latest["date"]).date().isoformat(),
        "state": state,
        "facts": {
            "hy_oas": _finite_or_none(latest.get("hy")),
            "ig_oas": _finite_or_none(latest.get("ig")),
            "vix": _finite_or_none(latest.get("vix")),
            "hy_percentile": _finite_or_none(latest.get("hy_percentile")),
            "ig_percentile": _finite_or_none(latest.get("ig_percentile")),
            "vix_percentile": _finite_or_none(latest.get("vix_percentile")),
            "hy_change_5d": _finite_or_none(latest.get("hy_change_5d")),
            "hy_change_20d": _finite_or_none(latest.get("hy_change_20d")),
            "hy_sma50": _finite_or_none(latest.get("hy_sma50")),
        },
        "interpretation": {
            "label": state,
            "summary": INTERPRETATIONS.get(state, "未定義狀態。"),
            "disclaimer": "研究狀態，不是買賣建議。",
        },
        "confirmation": {
            "SPY": {
                "market": "ES",
                "confirmed": spy_confirmed,
                "close": _finite_or_none(latest.get("spy_close")),
                "sma_10w": _finite_or_none(latest.get("spy_sma10w")),
                "momentum_4w": _finite_or_none(latest.get("spy_momentum_4w")),
                "proxy_label": "ES proxy (SPY), not ES settlement",
            },
            "QQQ": {
                "market": "NQ",
                "confirmed": qqq_confirmed,
                "close": _finite_or_none(latest.get("qqq_close")),
                "sma_10w": _finite_or_none(latest.get("qqq_sma10w")),
                "momentum_4w": _finite_or_none(latest.get("qqq_momentum_4w")),
                "proxy_label": "NQ proxy (QQQ), not NQ settlement",
            },
        },
        "cross_asset": evidence,
        "backtest": backtest,
        "sources": provenance,
        "methodology": {
            "percentile": (
                f"Prior-only rolling percentile: {settings.percentile_lookback} observations, "
                f"minimum {settings.percentile_minimum}; current and future observations excluded."
            ),
            "state_thresholds": {
                "deteriorating": settings.deteriorating_percentile,
                "stressed": settings.stressed_percentile,
                "extreme": settings.extreme_percentile,
                "sma_days": settings.spread_sma_days,
                "change_days": settings.spread_medium_change_days,
                "stress_memory_days": settings.stress_memory_days,
            },
        },
        "limitations": {
            "fred_ice_history_years": 3,
            "history_note": (
                "FRED public ICE BofA OAS history is currently limited to roughly three years; "
                "older analogues require another licensed or archived source."
            ),
            "proxy_note": "SPY/QQQ are equity proxies and are not ES/NQ futures settlement data.",
            "backtest_note": "Historical event-study results do not imply future performance.",
        },
    }


def _json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_clean(item) for item in value]
    if isinstance(value, tuple):
        return [_json_clean(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if value is pd.NA:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_clean(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def write_artifacts(
    project_root: Path,
    states: pd.DataFrame,
    dashboard: dict[str, object],
    backtest: list[dict[str, object]],
    provenance: dict[str, dict[str, object]],
    settings: RadarSettings,
    *,
    generated_at: datetime | None = None,
    warning: str | None = None,
) -> dict[str, object]:
    generated = generated_at or datetime.now(UTC)
    generated = generated.astimezone(UTC)
    latest_dates = {
        key: str(source.get("latest_date", "")) for key, source in provenance.items()
    }
    hy_latest = pd.Timestamp(latest_dates.get("HY")) if latest_dates.get("HY") else None
    age_days: int | None = None
    stale = False
    if hy_latest is not None and not pd.isna(hy_latest):
        age_days = (generated.date() - hy_latest.date()).days
        stale = age_days > settings.stale_after_days
    status: dict[str, object] = {
        "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "last_successful_fetch_utc": generated.isoformat().replace("+00:00", "Z"),
        "latest_observation_dates": latest_dates,
        "stale": stale,
        "age_days": age_days,
        "stale_after_days": settings.stale_after_days,
        "warning": warning,
        "providers": {
            key: source.get("provider") for key, source in provenance.items()
        },
    }
    dashboard_payload = dict(dashboard)
    dashboard_payload["data_status"] = status

    derived = project_root / "data" / "derived"
    public_data = project_root / "web" / "public" / "data"
    history_records = states.to_dict(orient="records")
    _write_json(derived / "dashboard.json", dashboard_payload)
    _write_json(derived / "history.json", history_records)
    _write_json(derived / "backtest.json", backtest)
    _write_json(derived / "status.json", status)
    derived.mkdir(parents=True, exist_ok=True)
    states.to_csv(derived / "credit_state.csv", index=False)

    _write_json(public_data / "dashboard.json", dashboard_payload)
    _write_json(public_data / "history.json", history_records)
    _write_json(public_data / "backtest.json", backtest)
    _write_json(public_data / "status.json", status)
    return status
