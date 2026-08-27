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
    if result.empty or result.isna().any().any() or (result["close"] <= 0).any():
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


class YahooFinanceProvider:
    SYMBOLS = {"SPY", "QQQ"}

    def __init__(self, http: HttpLike) -> None:
        self.http = http

    def fetch(self, symbol: str) -> pd.DataFrame:
        if symbol not in self.SYMBOLS:
            raise DataContractError(f"Yahoo Finance proxy symbol is unsupported: {symbol}")
        payload = self.http.get_json(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            {
                "range": "max",
                "interval": "1wk",
                "events": "history",
                "includeAdjustedClose": "true",
            },
        )
        if not isinstance(payload, dict):
            raise DataContractError("Yahoo Finance response must be an object")
        chart = cast(dict[str, Any], payload).get("chart")
        if not isinstance(chart, dict):
            raise DataContractError("Yahoo Finance response has no chart object")
        results = chart.get("result")
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            raise DataContractError(f"Yahoo Finance returned no weekly series: {chart.get('error')}")
        series = cast(dict[str, Any], results[0])
        timestamps = series.get("timestamp")
        indicators = series.get("indicators")
        if not isinstance(timestamps, list) or not isinstance(indicators, dict):
            raise DataContractError("Yahoo Finance weekly series is malformed")
        quotes = indicators.get("quote")
        if not isinstance(quotes, list) or not quotes or not isinstance(quotes[0], dict):
            raise DataContractError("Yahoo Finance weekly quotes are missing")
        closes = cast(dict[str, Any], quotes[0]).get("close")
        if not isinstance(closes, list) or len(closes) != len(timestamps):
            raise DataContractError("Yahoo Finance timestamps and closes do not align")

        dates = pd.to_datetime(timestamps, unit="s", utc=True, errors="coerce")
        rows = [
            {"date": date.tz_convert(None), "close": close}
            for date, close in zip(dates, closes, strict=True)
            if pd.notna(date) and close is not None
        ]
        return _normalize_prices(pd.DataFrame(rows))


class AutoPriceProvider:
    def __init__(
        self,
        alpha_vantage: AlphaVantageProvider | None,
        stooq: StooqProvider,
        yahoo_finance: YahooFinanceProvider | None = None,
    ) -> None:
        self.alpha_vantage = alpha_vantage
        self.stooq = stooq
        self.yahoo_finance = yahoo_finance

    def fetch(self, symbol: str) -> PriceResult:
        if self.alpha_vantage is not None:
            try:
                return PriceResult(self.alpha_vantage.fetch(symbol), "alpha_vantage")
            except DataContractError:
                pass
        try:
            return PriceResult(self.stooq.fetch(symbol), "stooq")
        except DataContractError:
            fallback = self.yahoo_finance
            if fallback is None:
                raise
        return PriceResult(fallback.fetch(symbol), "yahoo_finance")
