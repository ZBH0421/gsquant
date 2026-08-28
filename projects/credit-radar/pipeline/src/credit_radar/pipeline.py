from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from credit_radar.analytics import compute_credit_features, compute_price_features
from credit_radar.backtest import build_event_study
from credit_radar.config import RadarSettings
from credit_radar.export import build_dashboard, write_artifacts
from credit_radar.providers.fred import FRED_CSV_URL, FredProvider
from credit_radar.providers.http import HttpClient, HttpLike
from credit_radar.providers.prices import StooqPriceProvider
from credit_radar.signals import build_cross_asset_evidence, classify_credit_states

SERIES = {
    "HY": "BAMLH0A0HYM2",
    "IG": "BAMLC0A0CM",
    "VIX": "VIXCLS",
}


def align_price_features(
    credit: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    prefix: str,
) -> pd.DataFrame:
    left = credit.copy().sort_values("date", ignore_index=True)
    right = prices[["date", "close", "sma", "momentum"]].copy().sort_values(
        "date", ignore_index=True
    )
    left["date"] = pd.to_datetime(left["date"], errors="coerce")
    right["date"] = pd.to_datetime(right["date"], errors="coerce")
    right = right.rename(
        columns={
            "close": f"{prefix}_close",
            "sma": f"{prefix}_sma10w",
            "momentum": f"{prefix}_momentum_4w",
        }
    )
    return pd.merge_asof(left, right, on="date", direction="backward")


def _align_credit_series(
    hy: pd.DataFrame,
    ig: pd.DataFrame,
    vix: pd.DataFrame,
) -> pd.DataFrame:
    result = hy.rename(columns={"value": "hy"}).copy().sort_values("date", ignore_index=True)
    for source, name in ((ig, "ig"), (vix, "vix")):
        right = source.rename(columns={"value": name}).copy().sort_values("date", ignore_index=True)
        result = pd.merge_asof(result, right, on="date", direction="backward")
    return result.dropna(subset=["hy", "ig", "vix"]).reset_index(drop=True)


def _series_provenance(
    frame: pd.DataFrame,
    *,
    provider: str,
    series_id: str | None = None,
    proxy: str | None = None,
    source_url: str,
) -> dict[str, object]:
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    payload: dict[str, object] = {
        "provider": provider,
        "source_url": source_url,
        "history_start": dates.min().date().isoformat(),
        "latest_date": dates.max().date().isoformat(),
        "observations": int(len(frame)),
    }
    if series_id is not None:
        payload["series_id"] = series_id
    if proxy is not None:
        payload["proxy"] = proxy
    return payload


def run_pipeline(
    *,
    project_root: Path,
    settings_path: Path,
    http: HttpLike | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    settings = RadarSettings.load(settings_path)
    client: HttpLike = http or HttpClient()
    fred = FredProvider(client)
    prices_provider = StooqPriceProvider(client)

    hy = fred.fetch(SERIES["HY"])
    ig = fred.fetch(SERIES["IG"])
    vix = fred.fetch(SERIES["VIX"])
    credit = compute_credit_features(_align_credit_series(hy, ig, vix), settings)

    spy_raw = prices_provider.fetch("SPY")
    qqq_raw = prices_provider.fetch("QQQ")
    spy = compute_price_features(spy_raw, settings)
    qqq = compute_price_features(qqq_raw, settings)
    aligned = align_price_features(credit, spy, prefix="spy")
    aligned = align_price_features(aligned, qqq, prefix="qqq")
    states = classify_credit_states(aligned, settings)
    latest = states.iloc[-1]
    evidence = build_cross_asset_evidence(latest, settings)
    backtest = build_event_study(
        states[["date", "state"]],
        {"SPY": spy_raw, "QQQ": qqq_raw},
        settings,
        provider="stooq",
    )

    provenance = {
        "HY": _series_provenance(
            hy,
            provider="FRED",
            series_id=SERIES["HY"],
            source_url=FRED_CSV_URL,
        ),
        "IG": _series_provenance(
            ig,
            provider="FRED",
            series_id=SERIES["IG"],
            source_url=FRED_CSV_URL,
        ),
        "VIX": _series_provenance(
            vix,
            provider="FRED",
            series_id=SERIES["VIX"],
            source_url=FRED_CSV_URL,
        ),
        "SPY": _series_provenance(
            spy_raw,
            provider="stooq",
            proxy="ES",
            source_url="https://stooq.com/q/d/l/",
        ),
        "QQQ": _series_provenance(
            qqq_raw,
            provider="stooq",
            proxy="NQ",
            source_url="https://stooq.com/q/d/l/",
        ),
    }
    dashboard = build_dashboard(latest, evidence, backtest, provenance, settings)
    status = write_artifacts(
        project_root,
        states,
        dashboard,
        backtest,
        provenance,
        settings,
        generated_at=generated_at or datetime.now(UTC),
    )
    return {
        "dashboard": dashboard,
        "status": status,
        "state": str(latest["state"]),
        "as_of": pd.Timestamp(latest["date"]).date().isoformat(),
    }
