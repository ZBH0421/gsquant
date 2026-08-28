from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from cot_radar.config import RadarSettings
from cot_radar.models import DataContractError, Evidence


def _number(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "資料不足"
    return f"{float(value):.{digits}f}"


def build_evidence(snapshot: Mapping[str, object], settings: RadarSettings) -> Evidence:
    symbol = str(snapshot["symbol"])
    state = str(snapshot["state"])
    report_date = pd.Timestamp(cast(Any, snapshot["report_date"])).date().isoformat()
    percentile = _number(snapshot.get("leveraged_percentile"))
    net_pct = _number(snapshot.get("leveraged_net_pct_oi"))
    weekly_change = _number(snapshot.get("leveraged_weekly_change"))
    asset_net = _number(snapshot.get("asset_manager_net_pct_oi"))
    proxy = str(snapshot.get("proxy_symbol", settings.markets[symbol].proxy_symbol))

    facts = (
        f"截至 {report_date}，{symbol} Leveraged Funds 淨部位為未平倉量的 "
        f"{net_pct}%，位於前 {settings.lookback_weeks} 週 prior-only 第 "
        f"{percentile} 百分位，單週變化 {weekly_change} 個百分點；"
        f"Asset Managers 淨部位為 {asset_net}%。"
    )
    rule = (
        f"規則狀態為 {state}。極端門檻固定為第 {settings.extreme_high:.0f}/"
        f"{settings.extreme_low:.0f} 百分位，價格確認使用 {proxy} 的 "
        f"{settings.price_sma_weeks} 週均線與 {settings.price_momentum_weeks} 週動能。"
    )

    if state == "EXTREME_LONG":
        inference = "槓桿資金多頭部位高度擁擠，若開始減倉，平倉流量可能放大下行波動。"
        confirmation = "部位先退出高端極值區，且代理價格轉弱，才會提高反轉敘事可信度。"
        invalidation = "若淨多部位續增且代理價格維持均線上方，反轉推論失效。"
    elif state == "EXTREME_SHORT":
        inference = "槓桿資金空頭部位高度擁擠，若開始回補，回補流量可能放大上行波動。"
        confirmation = "部位先退出低端極值區，且代理價格轉強，才會提高反轉敘事可信度。"
        invalidation = "若淨空部位續增且代理價格維持均線下方，反轉推論失效。"
    elif state in {"UNWINDING_LONG", "CONFIRMED_BEARISH"}:
        inference = "先前擁擠的多頭正在鬆動，這可能增加多頭踩踏與下行加速風險。"
        confirmation = "代理價格跌破均線且中期動能為負，會支持多頭平倉敘事。"
        invalidation = "若槓桿淨多重新擴張且代理價格重回均線上方，敘事失效。"
    elif state in {"UNWINDING_SHORT", "CONFIRMED_BULLISH"}:
        inference = "先前擁擠的空頭正在回補，這可能增加軋空與上行加速風險。"
        confirmation = "代理價格站上均線且中期動能為正，會支持空頭回補敘事。"
        invalidation = "若槓桿淨空重新擴張且代理價格跌回均線下方，敘事失效。"
    else:
        inference = "目前沒有完整的極端擁擠到反轉證據鏈，較適合作為背景監測。"
        confirmation = "新的極端部位、隨後鬆動與價格同向確認，才會形成反轉敘事。"
        invalidation = "NORMAL 狀態沒有方向性反轉主張，因此不設定交易型失效點。"

    alternatives = (
        "部位變化也可能來自合約換月、總未平倉量改變、避險需求或交易者分類調整，"
        "不能直接等同單一基金的方向性押注。"
    )
    return Evidence(facts, rule, inference, alternatives, confirmation, invalidation)


def load_subjective_notes(path: Path) -> list[dict[str, str]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("notes"), list):
        raise DataContractError("notes file must contain a notes list")
    notes: list[dict[str, str]] = []
    for item in cast(list[object], raw["notes"]):
        if not isinstance(item, dict):
            raise DataContractError("each note must be a mapping")
        row = cast(dict[str, Any], item)
        required = {"symbol", "date", "author", "text"}
        if not required.issubset(row):
            raise DataContractError("each note requires symbol, date, author, and text")
        symbol = str(row["symbol"])
        if symbol not in {"ES", "NQ"}:
            raise DataContractError(f"unsupported note symbol: {symbol}")
        notes.append({key: str(row[key]) for key in sorted(required)})
    return notes
