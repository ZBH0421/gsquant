from __future__ import annotations

from io import StringIO

import pandas as pd

from credit_radar.models import DataContractError
from credit_radar.providers.http import HttpLike


class StooqPriceProvider:
    SYMBOLS = {"SPY": "spy.us", "QQQ": "qqq.us"}

    def __init__(self, http: HttpLike) -> None:
        self.http = http

    def fetch(self, symbol: str) -> pd.DataFrame:
        if symbol not in self.SYMBOLS:
            raise DataContractError(f"unsupported Stooq proxy symbol: {symbol}")
        text = self.http.get_text(
            "https://stooq.com/q/d/l/",
            {"s": self.SYMBOLS[symbol], "i": "w"},
        )
        try:
            raw = pd.read_csv(StringIO(text))
        except Exception as exc:
            raise DataContractError(f"Stooq {symbol} response is not valid CSV") from exc
        renamed = raw.rename(columns={"Date": "date", "Close": "close"})
        if not {"date", "close"}.issubset(renamed.columns):
            raise DataContractError(f"Stooq {symbol} response is missing date/close")
        result = renamed[["date", "close"]].copy()
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result["close"] = pd.to_numeric(result["close"], errors="coerce")
        result = result.dropna()
        result["date"] = result["date"].dt.tz_localize(None).dt.normalize()
        result = result[result["close"] > 0]
        result = result.drop_duplicates("date", keep="last").sort_values("date", ignore_index=True)
        if result.empty:
            raise DataContractError(f"Stooq {symbol} returned no valid observations")
        return result
