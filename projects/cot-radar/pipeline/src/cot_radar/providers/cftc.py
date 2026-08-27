from __future__ import annotations

from typing import Any, cast

import pandas as pd

from cot_radar.config import RadarSettings
from cot_radar.models import DataContractError
from cot_radar.providers.http import HttpLike


FIELD_MAP = {
    "report_date_as_yyyy_mm_dd": "report_date",
    "market_and_exchange_names": "market_name",
    "cftc_contract_market_code": "contract_code",
    "open_interest_all": "open_interest",
    "dealer_positions_long_all": "dealer_long",
    "dealer_positions_short_all": "dealer_short",
    "asset_mgr_positions_long": "asset_manager_long",
    "asset_mgr_positions_short": "asset_manager_short",
    "lev_money_positions_long": "leveraged_long",
    "lev_money_positions_short": "leveraged_short",
    "other_rept_positions_long": "other_long",
    "other_rept_positions_short": "other_short",
    "nonrept_positions_long_all": "nonreportable_long",
    "nonrept_positions_short_all": "nonreportable_short",
}


class CftcProvider:
    def __init__(self, http: HttpLike, settings: RadarSettings) -> None:
        self.http = http
        self.settings = settings
        self.url = f"{settings.base_url}/{settings.dataset_id}.json"

    def _market_catalog(self) -> list[dict[str, Any]]:
        payload = self.http.get_json(
            self.url,
            {
                "$select": "market_and_exchange_names,cftc_contract_market_code",
                "$group": "market_and_exchange_names,cftc_contract_market_code",
                "$limit": self.settings.page_size,
            },
        )
        if not isinstance(payload, list):
            raise DataContractError("CFTC market catalog must be a list")
        return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]

    def _resolve_contracts(self) -> dict[str, str]:
        catalog = self._market_catalog()
        resolved: dict[str, str] = {}
        for symbol, market in self.settings.markets.items():
            for pattern in market.contract_patterns:
                matches = {
                    str(row.get("cftc_contract_market_code", ""))
                    for row in catalog
                    if pattern.upper()
                    in str(row.get("market_and_exchange_names", "")).upper()
                }
                matches.discard("")
                if len(matches) == 1:
                    resolved[symbol] = matches.pop()
                    break
            if symbol not in resolved:
                raise DataContractError(f"unable to resolve one CFTC contract for {symbol}")
        if len(set(resolved.values())) != len(resolved):
            raise DataContractError("ES and NQ resolved to the same CFTC contract")
        return resolved

    def _download_rows(self, contract_codes: set[str]) -> list[dict[str, Any]]:
        quoted = ",".join(f"'{code.replace(chr(39), chr(39) * 2)}'" for code in sorted(contract_codes))
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = self.http.get_json(
                self.url,
                {
                    "$where": f"cftc_contract_market_code in({quoted})",
                    "$order": "report_date_as_yyyy_mm_dd,cftc_contract_market_code",
                    "$limit": self.settings.page_size,
                    "$offset": offset,
                },
            )
            if not isinstance(payload, list):
                raise DataContractError("CFTC rows payload must be a list")
            page = [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]
            rows.extend(page)
            if len(page) < self.settings.page_size:
                break
            offset += self.settings.page_size
        if not rows:
            raise DataContractError("CFTC returned no ES/NQ rows")
        return rows

    def fetch(self) -> pd.DataFrame:
        resolved = self._resolve_contracts()
        rows = self._download_rows(set(resolved.values()))
        for official_name in FIELD_MAP:
            if any(official_name not in row or row[official_name] in (None, "") for row in rows):
                raise DataContractError(f"CFTC field {official_name} is missing")

        frame = pd.DataFrame(rows).rename(columns=FIELD_MAP)
        frame = frame[list(FIELD_MAP.values())]
        symbol_by_code = {code: symbol for symbol, code in resolved.items()}
        frame["symbol"] = frame["contract_code"].map(symbol_by_code)
        if frame["symbol"].isna().any():
            raise DataContractError("CFTC returned an unresolved contract code")

        numeric_columns = [
            column
            for column in frame.columns
            if column.endswith("_long")
            or column.endswith("_short")
            or column == "open_interest"
        ]
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            if frame[column].isna().any():
                raise DataContractError(f"CFTC field {column} contains non-numeric data")

        frame["report_date"] = pd.to_datetime(frame["report_date"], errors="coerce").dt.normalize()
        if frame["report_date"].isna().any():
            raise DataContractError("CFTC report_date contains invalid dates")
        release_dates = frame["report_date"] + pd.Timedelta(days=3)
        frame["available_at"] = (
            release_dates.dt.tz_localize("America/New_York")
            + pd.Timedelta(hours=15, minutes=30)
        )

        if frame.duplicated(["symbol", "report_date"]).any():
            raise DataContractError("CFTC returned duplicate symbol/report_date rows")
        return frame.sort_values(["symbol", "report_date"], ignore_index=True)
