from typing import Any

import pandas as pd
import pytest

from cot_radar.config import RadarSettings
from cot_radar.models import DataContractError
from cot_radar.providers.cftc import CftcProvider
from cot_radar.providers.prices import (
    AlphaVantageProvider,
    AutoPriceProvider,
    PriceResult,
    StooqProvider,
    YahooFinanceProvider,
)


class FakeCftcHttp:
    def __init__(self, missing_open_interest: bool = False) -> None:
        self.missing_open_interest = missing_open_interest

    def get_json(self, url: str, params: dict[str, str | int]) -> Any:
        if "$select" in params:
            return [
                {
                    "market_and_exchange_names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
                    "cftc_contract_market_code": "13874+",
                },
                {
                    "market_and_exchange_names": (
                        "NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE"
                    ),
                    "cftc_contract_market_code": "20974+",
                },
            ]

        base = {
            "report_date_as_yyyy_mm_dd": "2026-08-18T00:00:00.000",
            "market_and_exchange_names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
            "cftc_contract_market_code": "13874+",
            "open_interest_all": "1000",
            "dealer_positions_long_all": "100",
            "dealer_positions_short_all": "120",
            "asset_mgr_positions_long": "300",
            "asset_mgr_positions_short": "100",
            "lev_money_positions_long": "220",
            "lev_money_positions_short": "180",
            "other_rept_positions_long": "50",
            "other_rept_positions_short": "40",
            "nonrept_positions_long_all": "20",
            "nonrept_positions_short_all": "30",
        }
        nq = dict(base)
        nq["market_and_exchange_names"] = (
            "NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE"
        )
        nq["cftc_contract_market_code"] = "20974+"
        if self.missing_open_interest:
            base.pop("open_interest_all")
        return [base, nq]


class FakePriceHttp:
    def __init__(self, *, alpha_fails: bool = False) -> None:
        self.alpha_fails = alpha_fails

    def get_json(self, url: str, params: dict[str, str | int]) -> Any:
        if self.alpha_fails:
            return {"Information": "rate limit"}
        return {
            "Weekly Time Series": {
                "2026-08-21": {"4. close": "650.25"},
                "2026-08-14": {"4. close": "645.00"},
            }
        }

    def get_text(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
    ) -> str:
        return (
            "Date,Open,High,Low,Close,Volume\n"
            "2026-08-14,1,2,1,645.0,10\n"
            "2026-08-21,1,2,1,650.0,10\n"
        )


def test_cftc_resolves_configured_market_patterns() -> None:
    frame = CftcProvider(FakeCftcHttp(), RadarSettings.for_tests()).fetch()

    assert set(frame["symbol"]) == {"ES", "NQ"}
    assert frame.sort_values(["symbol", "report_date"]).index.equals(frame.index)
    assert str(frame.iloc[0]["available_at"].tz) == "America/New_York"


def test_cftc_rejects_missing_required_columns() -> None:
    with pytest.raises(DataContractError, match="open_interest_all"):
        CftcProvider(
            FakeCftcHttp(missing_open_interest=True),
            RadarSettings.for_tests(),
        ).fetch()


def test_alpha_vantage_parses_weekly_close() -> None:
    frame = AlphaVantageProvider(FakePriceHttp(), "secret").fetch("SPY")

    assert list(frame.columns) == ["date", "close"]
    assert frame.iloc[-1]["close"] == pytest.approx(650.25)


def test_auto_provider_falls_back_and_reports_source() -> None:
    http = FakePriceHttp(alpha_fails=True)
    result = AutoPriceProvider(
        AlphaVantageProvider(http, "secret"),
        StooqProvider(http),
    ).fetch("SPY")

    assert isinstance(result, PriceResult)
    assert result.provider == "stooq"
    assert not result.frame.empty
    assert pd.api.types.is_datetime64_any_dtype(result.frame["date"])


class FakeYahooHttp:
    def get_json(self, url: str, params: dict[str, str | int]) -> Any:
        assert "query1.finance.yahoo.com" in url
        assert params["interval"] == "1wk"
        return {
            "chart": {
                "result": [
                    {
                        "timestamp": [1786665600, 1787270400],
                        "indicators": {
                            "quote": [{"close": [645.0, 650.25]}],
                        },
                    }
                ],
                "error": None,
            }
        }

    def get_text(
        self,
        url: str,
        params: dict[str, str | int] | None = None,
    ) -> str:
        return "upstream unavailable"


def test_yahoo_finance_parses_keyless_weekly_close() -> None:
    frame = YahooFinanceProvider(FakeYahooHttp()).fetch("SPY")

    assert list(frame.columns) == ["date", "close"]
    assert frame.iloc[-1]["close"] == pytest.approx(650.25)


def test_auto_provider_falls_through_invalid_stooq_payload() -> None:
    http = FakeYahooHttp()
    result = AutoPriceProvider(
        None,
        StooqProvider(http),
        YahooFinanceProvider(http),
    ).fetch("QQQ")

    assert result.provider == "yahoo_finance"
    assert len(result.frame) == 2
