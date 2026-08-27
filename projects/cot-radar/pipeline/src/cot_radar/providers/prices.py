from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any, cast

import pandas as pd

from cot_radar.models import DataContractError
from cot_radar.providers.http import HttpLike


@dataclass(frozen=True)
class PriceResult:
    frame: pd.DataFrame
    provider: str


def _normalize_prices(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise DataContractError(f"price data missing columns: {', '.join(sorted(missing))}")
    result = frame[["date", "close"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    if result.isna().any().any() or (result["close"] <= 0).any():
        raise DataContractError("price data contains invalid dates or closes")
    return result.drop_duplicates("date", keep="last").sort_values("date", ignore_index=True)


class AlphaVantageProvider:
    def __init__(self, http: HttpLike, api_key: str) -> None:
        self.http = http
        self.api_key = api_key

    def fetch(self, symbol: str) -> pd.DataFrame:
        if not self.api_key:
            raise DataContractError("Alpha Vantage API key is not configured")
        payload = self.http.get_json(
            "https://www.alphavantage.co/query",
            {
                "function": "TIME_SERIES_WEEKLY",
                "symbol": symbol,
                "apikey": self.api_key,
            },
        )
        if not isinstance(payload, dict):
            raise DataContractError("Alpha Vantage response must be an object")
        raw = cast(dict[str, Any], payload)
        series = raw.get("Weekly Time Series")
        if not isinstance(series, dict):
            message = raw.get("Information") or raw.get("Note") or raw.get("Error Message")
            raise DataContractError(f"Alpha Vantage returned no weekly series: {message}")
        rows = [
            {"date": date, "close": values.get("4. close")}
            for date, values in cast(dict[str, dict[str, Any]], series).items()
        ]
        return _normalize_prices(pd.DataFrame(rows))


class StooqProvider:
    SYMBOLS = {"SPY": "spy.us", "QQQ": "qqq.us"}

    def __init__(self, http: HttpLike) -> None:
        self.http = http

    def fetch(self, symbol: str) -> pd.DataFrame:
        if symbol not in self.SYMBOLS:
            raise DataContractError(f"Stooq proxy symbol is unsupported: {symbol}")
        text = self.http.get_text(
            "https://stooq.com/q/d/l/",
            {"s": self.SYMBOLS[symbol], "i": "w"},
        )
        raw = pd.read_csv(StringIO(text))
        return _normalize_prices(raw.rename(columns={"Date": "date", "Close": "close"}))


class AutoPriceProvider:
    def __init__(
        self,
        alpha_vantage: AlphaVantageProvider | None,
        stooq: StooqProvider,
    ) -> None:
        self.alpha_vantage = alpha_vantage
        self.stooq = stooq

    def fetch(self, symbol: str) -> PriceResult:
        if self.alpha_vantage is not None:
            try:
                return PriceResult(self.alpha_vantage.fetch(symbol), "alpha_vantage")
            except DataContractError:
                pass
        return PriceResult(self.stooq.fetch(symbol), "stooq")
