from __future__ import annotations

import pandas as pd
import pytest

from conftest import load_module


class FakeHttp:
    def __init__(self, text: str) -> None:
        self.text = text

    def get_text(self, url: str, params: dict[str, str] | None = None) -> str:
        del url, params
        return self.text


def test_fred_provider_normalizes_series_and_drops_missing_observations() -> None:
    fred = load_module("credit_radar.providers.fred")
    provider = fred.FredProvider(
        FakeHttp("DATE,BAMLH0A0HYM2\n2026-08-25,2.70\n2026-08-26,.\n2026-08-27,2.65\n")
    )

    result = provider.fetch("BAMLH0A0HYM2")

    assert result.columns.tolist() == ["date", "value"]
    assert result["value"].tolist() == [2.70, 2.65]
    assert result["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-08-25", "2026-08-27"]


def test_fred_provider_rejects_series_without_valid_values() -> None:
    fred = load_module("credit_radar.providers.fred")
    models = load_module("credit_radar.models")
    provider = fred.FredProvider(FakeHttp("DATE,VIXCLS\n2026-08-25,.\n"))

    with pytest.raises(models.DataContractError):
        provider.fetch("VIXCLS")


def test_stooq_provider_returns_positive_weekly_close_series() -> None:
    prices = load_module("credit_radar.providers.prices")
    provider = prices.StooqPriceProvider(
        FakeHttp("Date,Open,High,Low,Close,Volume\n2026-08-21,100,102,99,101,1000\n")
    )

    result = provider.fetch("SPY")

    assert result.iloc[0]["close"] == 101.0
    assert isinstance(result.iloc[0]["date"], pd.Timestamp)
