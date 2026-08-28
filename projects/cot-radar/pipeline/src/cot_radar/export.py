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


def _as_utc(value: pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _scheduled_release(report_date: pd.Timestamp) -> pd.Timestamp:
    calendar_date = pd.Timestamp(report_date).tz_localize(None).normalize()
    release_date = calendar_date + pd.Timedelta(days=3)
    return release_date.tz_localize("America/New_York") + pd.Timedelta(hours=15, minutes=30)


def _next_scheduled_update(generated_at: pd.Timestamp) -> pd.Timestamp:
    now = _as_utc(generated_at).tz_convert("Asia/Taipei")
    midnight = now.normalize()
    days_until_saturday = (5 - now.weekday()) % 7
    candidate = midnight + pd.Timedelta(days=days_until_saturday, hours=8)
    if candidate <= now:
        candidate += pd.Timedelta(days=7)
    return candidate


def _publication_status(
    latest: pd.Timestamp,
    generated_at: pd.Timestamp,
    settings: RadarSettings,
) -> dict[str, Any]:
    now = _as_utc(generated_at)
    latest_release = _scheduled_release(latest)
    next_report = pd.Timestamp(latest).tz_localize(None).normalize() + pd.Timedelta(days=7)
    next_release = _scheduled_release(next_report)
    latest_release_utc = latest_release.tz_convert("UTC")
    next_release_utc = next_release.tz_convert("UTC")
    recent_success_deadline = latest_release_utc + pd.Timedelta(days=2)
    grace_deadline = next_release_utc + pd.Timedelta(days=settings.publication_grace_days)

    publication_state = "current"
    warning: str | None = None
    stale = False
    if now < next_release_utc:
        if now > recent_success_deadline:
            publication_state = "waiting_for_cftc"
            warning = (
                "等待 CFTC 發布下一期 TFF Futures Only；目前顯示最近一次成功資料，"
                "不代表更新失敗。"
            )
    elif now <= grace_deadline:
        publication_state = "waiting_for_cftc"
        warning = (
            "等待 CFTC 發布：正常排程時間已到，但官方資料可能因假日或營運因素延遲；"
            "系統保留最近一次成功資料。"
        )
    else:
        publication_state = "stale"
        stale = True
        warning = (
            "資料可能已過期：下一期已超過正常發布時間與寬限期；"
            "系統仍保留最近一次成功資料，請核對 CFTC 官方來源。"
        )

    return {
        "scheduled_release_at": latest_release,
        "next_expected_report_date": next_report,
        "next_expected_release_at": next_release,
        "next_scheduled_update_at": _next_scheduled_update(generated_at),
        "publication_state": publication_state,
        "stale": stale,
        "warning": warning,
    }


def _state_machine_methodology(settings: RadarSettings) -> dict[str, dict[str, str]]:
    high = f"第 {settings.extreme_high:g} 百分位"
    low = f"第 {settings.extreme_low:g} 百分位"
    memory = f"{settings.unwind_memory_weeks} 週"
    delay = f"{settings.confirmation_delay_weeks} 週"
    sma = f"{settings.price_sma_weeks} 週均線"
    momentum = f"{settings.price_momentum_weeks} 週動能"
    return {
        "NORMAL": {
            "entry": "沒有有效的極端、鬆動或價格確認條件。",
            "hold": "極端記憶不存在或已失效。",
            "exit": f"Leveraged Funds 百分位進入 {high} 以上或 {low} 以下。",
            "price_confirmation": "不需要。",
            "invalidation": "新的極端條件成立即退出 NORMAL。",
        },
        "EXTREME_LONG": {
            "entry": f"Leveraged Funds prior-only 百分位 >= {high}。",
            "hold": f"百分位持續 >= {high}。",
            "exit": "百分位退出多頭極端區。",
            "price_confirmation": "極端本身不使用價格確認。",
            "invalidation": "百分位跌回極端門檻以下。",
        },
        "EXTREME_SHORT": {
            "entry": f"Leveraged Funds prior-only 百分位 <= {low}。",
            "hold": f"百分位持續 <= {low}。",
            "exit": "百分位退出空頭極端區。",
            "price_confirmation": "極端本身不使用價格確認。",
            "invalidation": "百分位升回極端門檻以上。",
        },
        "UNWINDING_LONG": {
            "entry": f"最近 {memory} 內曾為 EXTREME_LONG，且淨部位／OI 較前週下降。",
            "hold": "極端記憶仍有效且淨部位／OI 繼續下降。",
            "exit": "部位不再下降、重新進入極端，或極端記憶到期。",
            "price_confirmation": f"滿 {delay} 後才可檢查價格確認。",
            "invalidation": "部位下降條件中斷或記憶到期。",
        },
        "UNWINDING_SHORT": {
            "entry": f"最近 {memory} 內曾為 EXTREME_SHORT，且淨部位／OI 較前週上升。",
            "hold": "極端記憶仍有效且淨部位／OI 繼續上升。",
            "exit": "部位不再上升、重新進入極端，或極端記憶到期。",
            "price_confirmation": f"滿 {delay} 後才可檢查價格確認。",
            "invalidation": "部位上升條件中斷或記憶到期。",
        },
        "CONFIRMED_BEARISH": {
            "entry": f"UNWINDING_LONG 條件成立，且價格低於 {sma}、{momentum} < 0。",
            "hold": f"多頭鬆動持續，價格仍低於 {sma} 且 {momentum} < 0。",
            "exit": "價格確認失效時退回 UNWINDING_LONG；部位條件失效時回 NORMAL。",
            "price_confirmation": f"價格 < {sma} 且 {momentum} < 0。",
            "invalidation": f"價格 >= {sma}、{momentum} >= 0，或部位鬆動條件中斷。",
        },
        "CONFIRMED_BULLISH": {
            "entry": f"UNWINDING_SHORT 條件成立，且價格高於 {sma}、{momentum} > 0。",
            "hold": f"空頭回補持續，價格仍高於 {sma} 且 {momentum} > 0。",
            "exit": "價格確認失效時退回 UNWINDING_SHORT；部位條件失效時回 NORMAL。",
            "price_confirmation": f"價格 > {sma} 且 {momentum} > 0。",
            "invalidation": f"價格 <= {sma}、{momentum} <= 0，或部位回補條件中斷。",
        },
    }


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    result = float(value)
    return result if np.isfinite(result) else None


def _comparison(current: pd.DataFrame, settings: RadarSettings) -> dict[str, Any]:
    rows = {
        str(row["symbol"]): cast(dict[str, Any], row)
        for row in current.to_dict(orient="records")
    }
    markets: dict[str, dict[str, Any]] = {}
    for symbol in ("ES", "NQ"):
        row = rows[symbol]
        close = _optional_float(row.get("close"))
        sma = _optional_float(row.get("price_sma"))
        price_vs_sma = None
        if close is not None and sma not in (None, 0.0):
            price_vs_sma = close / cast(float, sma) - 1.0
        markets[symbol] = {
            "leveraged_net_pct_oi": _optional_float(row.get("leveraged_net_pct_oi")),
            "asset_manager_net_pct_oi": _optional_float(row.get("asset_manager_net_pct_oi")),
            "leveraged_percentile": _optional_float(row.get("leveraged_percentile")),
            "leveraged_change_1w": _optional_float(row.get("leveraged_weekly_change")),
            "leveraged_change_4w": _optional_float(row.get("leveraged_four_week_change")),
            "asset_manager_change_1w": _optional_float(row.get("asset_manager_weekly_change")),
            "asset_manager_change_4w": _optional_float(row.get("asset_manager_four_week_change")),
            "price_momentum_4w": _optional_float(row.get("price_momentum")),
            "price_vs_sma_10w": price_vs_sma,
            "state": str(row.get("state", "NORMAL")),
            "proxy_symbol": settings.markets[symbol].proxy_symbol,
        }

    es_percentile = markets["ES"]["leveraged_percentile"]
    nq_percentile = markets["NQ"]["leveraged_percentile"]
    percentile_gap: float | None = None
    position_divergence = False
    synchronized_crowding = False
    more_extreme_market: str | None = None
    if isinstance(es_percentile, float) and isinstance(nq_percentile, float):
        percentile_gap = abs(es_percentile - nq_percentile)
        position_divergence = percentile_gap >= settings.divergence_percentile_gap
        synchronized_crowding = (
            es_percentile >= settings.extreme_high
            and nq_percentile >= settings.extreme_high
        ) or (
            es_percentile <= settings.extreme_low
            and nq_percentile <= settings.extreme_low
        )
        es_extremity = abs(es_percentile - 50.0)
        nq_extremity = abs(nq_percentile - 50.0)
        if es_extremity > nq_extremity:
            more_extreme_market = "ES"
        elif nq_extremity > es_extremity:
            more_extreme_market = "NQ"

    if percentile_gap is None:
        evidence = "ES／NQ 尚無足夠的 prior-only 百分位資料，無法判定部位分歧。"
    else:
        verdict = "判定部位分歧" if position_divergence else "不判定部位分歧"
        evidence = (
            f"ES Leveraged Funds 156 週 prior-only 百分位 {es_percentile:.1f}，"
            f"NQ {nq_percentile:.1f}，差距 {percentile_gap:.1f} 個百分點；"
            f"公開門檻為 {settings.divergence_percentile_gap:.1f}，故{verdict}。"
        )
    falsification = (
        f"當 ES／NQ Leveraged Funds prior-only 百分位差距低於 "
        f"{settings.divergence_percentile_gap:.1f} 個百分點時，部位分歧判定失效。"
    )
    return {
        "markets": markets,
        "synchronized_crowding": synchronized_crowding,
        "position_divergence": position_divergence,
        "percentile_gap": percentile_gap,
        "more_extreme_market": more_extreme_market,
        "evidence": evidence,
        "falsification": falsification,
        "formula": (
            "divergence = abs(ES leveraged prior-only percentile - "
            "NQ leveraged prior-only percentile) >= configured threshold"
        ),
    }


def _backtest_summary(
    backtest: pd.DataFrame,
    settings: RadarSettings,
    price_provider: str,
) -> list[dict[str, Any]]:
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
        period_start=("baseline_date", "min"),
        period_end=("baseline_date", "max"),
    ).reset_index()
    rows: list[dict[str, Any]] = []
    for raw_row in summary.to_dict(orient="records"):
        row = cast(dict[str, Any], raw_row)
        symbol = str(row["symbol"])
        direction = str(row["extreme_direction"])
        sample_count = int(row["sample_count"])
        small_sample = sample_count < settings.minimum_backtest_samples
        if small_sample:
            row["reversal_win_rate"] = np.nan
        row["small_sample"] = small_sample
        row["signal_direction"] = (
            "bearish" if direction == "long" else "bullish" if direction == "short" else "neutral"
        )
        row["proxy_symbol"] = settings.markets[symbol].proxy_symbol
        row["price_provider"] = price_provider
        rows.append(_clean(row))
    return rows


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

    latest = pd.Timestamp(signals["report_date"].max()).tz_localize(None).normalize()
    freshness = _publication_status(latest, generated_at, settings)
    status = {
        "generated_at": generated_at,
        "latest_report_date": latest,
        "fetched_at": generated_at,
        "last_successful_update_at": generated_at,
        "last_update_attempt_at": generated_at,
        "last_update_succeeded": True,
        "price_provider": price_provider,
        "stale_after_days": settings.stale_after_days,
        "publication_grace_days": settings.publication_grace_days,
        "cftc_dataset": settings.dataset_id,
        **freshness,
    }
    history_columns = [
        "symbol",
        "report_date",
        "state",
        "extreme_direction",
        "leveraged_net_pct_oi",
        "leveraged_percentile",
        "leveraged_weekly_change",
        "leveraged_four_week_change",
        "asset_manager_net_pct_oi",
        "asset_manager_percentile",
        "asset_manager_weekly_change",
        "asset_manager_four_week_change",
        "close",
        "price_sma",
        "price_momentum",
        "price_normalized",
    ]
    available_history = [column for column in history_columns if column in signals.columns]
    signal_columns = [column for column in signals.columns if not column.startswith("_")]

    dashboard = {
        "generated_at": generated_at,
        "report_date": latest,
        "markets": markets,
        "comparison": _comparison(current, settings),
        "data_status": status,
        "methodology": {
            "lookback_weeks": settings.lookback_weeks,
            "minimum_history_weeks": settings.minimum_history_weeks,
            "extreme_high": settings.extreme_high,
            "extreme_low": settings.extreme_low,
            "unwind_memory_weeks": settings.unwind_memory_weeks,
            "confirmation_delay_weeks": settings.confirmation_delay_weeks,
            "price_sma_weeks": settings.price_sma_weeks,
            "price_momentum_weeks": settings.price_momentum_weeks,
            "divergence_percentile_gap": settings.divergence_percentile_gap,
            "minimum_backtest_samples": settings.minimum_backtest_samples,
            "price_proxies": {"ES": "SPY", "NQ": "QQQ"},
            "state_machine": _state_machine_methodology(settings),
        },
    }
    signal_records = _records(signals[signal_columns])
    backtest_metadata = {
        "horizons_weeks": list(settings.backtest_horizons),
        "minimum_sample_size": settings.minimum_backtest_samples,
        "availability_assumption": (
            "COT 通常反映週二部位，並以正常排程週五 15:30 America/New_York 可得後"
            "的第一個週線價格作為回測起點。"
        ),
        "historical_release_limit": (
            "歷史資料無法逐筆重建所有假日或營運延遲發布時間；延遲週的結果可能偏樂觀。"
        ),
        "disclaimer": "歷史統計僅描述過去樣本，不代表未來報酬或交易建議。",
        "price_provider": price_provider,
        "price_proxies": {symbol: market.proxy_symbol for symbol, market in settings.markets.items()},
    }
    return {
        "dashboard.json": _clean(dashboard),
        "history.json": {"history": _records(signals[available_history])},
        "backtest.json": {
            "metadata": _clean(backtest_metadata),
            "summary": _backtest_summary(backtest, settings, price_provider),
            "events": _records(backtest),
        },
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
    comparison = dashboard.get("comparison")
    if not isinstance(comparison, dict):
        raise DataContractError("dashboard comparison must be an object")
    status = artifacts["status.json"]
    if not isinstance(status, dict) or status.get("cftc_dataset") is None:
        raise DataContractError("status artifact is incomplete")


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
