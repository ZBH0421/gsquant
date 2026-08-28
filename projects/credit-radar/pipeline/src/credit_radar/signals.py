from __future__ import annotations

import math

import pandas as pd

from credit_radar.config import RadarSettings
from credit_radar.models import DataContractError


STATES = (
    "NORMAL",
    "DETERIORATING",
    "STRESSED",
    "EXTREME_STRESS",
    "STABILIZING",
    "CREDIT_REVERSAL",
    "CONFIRMED_RISK_ON",
)


def _number(row: pd.Series, key: str) -> float:
    value = row.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _price_confirmed(row: pd.Series, prefix: str) -> bool:
    close = _number(row, f"{prefix}_close")
    sma = _number(row, f"{prefix}_sma10w")
    momentum = _number(row, f"{prefix}_momentum_4w")
    return all(math.isfinite(value) for value in (close, sma, momentum)) and close > sma and momentum > 0


def classify_credit_states(frame: pd.DataFrame, settings: RadarSettings) -> pd.DataFrame:
    required = {
        "date",
        "hy",
        "hy_percentile",
        "hy_sma50",
        "hy_change_20d",
        "hy_high_20d",
        "ig_percentile",
        "vix_percentile",
        "spy_close",
        "spy_sma10w",
        "spy_momentum_4w",
        "qqq_close",
        "qqq_sma10w",
        "qqq_momentum_4w",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DataContractError(f"signal data missing columns: {', '.join(missing)}")

    result = frame.copy().sort_values("date", ignore_index=True)
    states: list[str] = []
    memories: list[int] = []
    spy_confirmations: list[bool] = []
    qqq_confirmations: list[bool] = []
    stress_memory = 0
    previous_change = math.nan

    for position in range(len(result)):
        row = result.iloc[position]
        percentile = _number(row, "hy_percentile")
        hy = _number(row, "hy")
        sma = _number(row, "hy_sma50")
        change = _number(row, "hy_change_20d")
        prior_high = _number(row, "hy_high_20d")
        spy_confirmed = _price_confirmed(row, "spy")
        qqq_confirmed = _price_confirmed(row, "qqq")

        if math.isfinite(percentile) and percentile >= settings.extreme_percentile:
            state = "EXTREME_STRESS"
            stress_memory = settings.stress_memory_days
        elif math.isfinite(percentile) and percentile >= settings.stressed_percentile:
            state = "STRESSED"
            stress_memory = settings.stress_memory_days
        else:
            reversal = (
                stress_memory > 0
                and all(math.isfinite(value) for value in (hy, sma, change))
                and hy < sma
                and change < 0
            )
            stabilizing = (
                stress_memory > 0
                and all(math.isfinite(value) for value in (hy, prior_high, change, previous_change))
                and hy < prior_high
                and change < previous_change
            )
            deteriorating = (
                math.isfinite(percentile)
                and percentile >= settings.deteriorating_percentile
                and all(math.isfinite(value) for value in (hy, sma, change))
                and hy > sma
                and change > 0
            )
            if reversal and (spy_confirmed or qqq_confirmed):
                state = "CONFIRMED_RISK_ON"
            elif reversal:
                state = "CREDIT_REVERSAL"
            elif stabilizing:
                state = "STABILIZING"
            elif deteriorating:
                state = "DETERIORATING"
            else:
                state = "NORMAL"
            if stress_memory > 0:
                stress_memory -= 1

        states.append(state)
        memories.append(stress_memory)
        spy_confirmations.append(spy_confirmed)
        qqq_confirmations.append(qqq_confirmed)
        previous_change = change

    result["state"] = states
    result["stress_memory_days"] = memories
    result["spy_confirmed"] = spy_confirmations
    result["qqq_confirmed"] = qqq_confirmations
    return result


def build_cross_asset_evidence(latest: pd.Series, settings: RadarSettings) -> dict[str, object]:
    hy = _number(latest, "hy_percentile")
    ig = _number(latest, "ig_percentile")
    vix = _number(latest, "vix_percentile")
    gap = settings.divergence_percentile_gap
    hy_ig_gap = hy - ig
    hy_vix_gap = hy - vix
    labels: list[str] = []
    if math.isfinite(hy_ig_gap) and hy_ig_gap >= gap:
        labels.append("HY_SPECIFIC_STRESS")
    if (
        math.isfinite(hy)
        and math.isfinite(ig)
        and hy >= settings.stressed_percentile
        and ig >= settings.stressed_percentile
    ):
        labels.append("SYSTEMIC_CREDIT_STRESS")
    if math.isfinite(hy_vix_gap) and hy_vix_gap >= gap:
        labels.append("CREDIT_LEADS_VOL")
    elif math.isfinite(hy_vix_gap) and hy_vix_gap <= -gap:
        labels.append("VOL_LEADS_CREDIT")

    return {
        "labels": labels,
        "hy_ig_gap": round(hy_ig_gap, 2) if math.isfinite(hy_ig_gap) else None,
        "hy_vix_gap": round(hy_vix_gap, 2) if math.isfinite(hy_vix_gap) else None,
        "formula": (
            f"HY-IG >= {gap:g} => HY_SPECIFIC_STRESS; "
            f"HY-VIX >= {gap:g} => CREDIT_LEADS_VOL; HY-VIX <= -{gap:g} => VOL_LEADS_CREDIT"
        ),
        "falsification": (
            f"Divergence labels are invalid when the relevant absolute percentile gap is < {gap:g}."
        ),
    }
