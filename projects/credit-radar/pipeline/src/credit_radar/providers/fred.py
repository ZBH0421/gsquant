from __future__ import annotations

from io import StringIO

import pandas as pd

from credit_radar.models import DataContractError
from credit_radar.providers.http import HttpLike

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


class FredProvider:
    def __init__(self, http: HttpLike) -> None:
        self.http = http

    def fetch(self, series_id: str) -> pd.DataFrame:
        text = self.http.get_text(FRED_CSV_URL, {"id": series_id})
        try:
            raw = pd.read_csv(StringIO(text))
        except Exception as exc:
            raise DataContractError(f"FRED {series_id} response is not valid CSV") from exc
        if raw.shape[1] < 2:
            raise DataContractError(f"FRED {series_id} response has too few columns")

        date_column = next(
            (
                column
                for column in raw.columns
                if str(column).lower() in {"date", "observation_date"}
            ),
            raw.columns[0],
        )
        value_column = series_id if series_id in raw.columns else raw.columns[-1]
        result = pd.DataFrame(
            {
                "date": pd.to_datetime(raw[date_column], errors="coerce"),
                "value": pd.to_numeric(raw[value_column], errors="coerce"),
            }
        ).dropna()
        result["date"] = result["date"].dt.tz_localize(None).dt.normalize()
        result = result.drop_duplicates("date", keep="last").sort_values("date", ignore_index=True)
        if result.empty:
            raise DataContractError(f"FRED {series_id} returned no valid observations")
        return result
