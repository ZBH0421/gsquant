from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from cot_radar.config import load_settings
from cot_radar.narratives import load_subjective_notes
from cot_radar.pipeline import PriceLike, run_pipeline
from cot_radar.providers.cftc import CftcProvider
from cot_radar.providers.http import HttpClient
from cot_radar.providers.prices import (
    AlphaVantageProvider,
    AutoPriceProvider,
    PriceResult,
    StooqProvider,
    YahooFinanceProvider,
)


class SinglePriceProvider:
    def __init__(
        self,
        provider: AlphaVantageProvider | StooqProvider | YahooFinanceProvider,
        name: str,
    ) -> None:
        self.provider = provider
        self.name = name

    def fetch(self, symbol: str) -> PriceResult:
        return PriceResult(self.provider.fetch(symbol), self.name)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate CFTC positioning and reversal radar artifacts",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path("projects/cot-radar/config/settings.yaml"),
    )
    parser.add_argument(
        "--notes",
        type=Path,
        default=Path("projects/cot-radar/narratives/notes.yaml"),
    )
    parser.add_argument(
        "--derived-output",
        type=Path,
        default=Path("projects/cot-radar/data/derived"),
    )
    parser.add_argument(
        "--web-output",
        type=Path,
        default=Path("projects/cot-radar/web/public/data"),
    )
    parser.add_argument(
        "--price-provider",
        choices=("auto", "alpha_vantage", "stooq"),
        default="auto",
    )
    return parser


def _prices(name: str, http: HttpClient) -> PriceLike:
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    alpha = AlphaVantageProvider(http, key) if key else None
    stooq = StooqProvider(http)
    yahoo = YahooFinanceProvider(http)
    if name == "auto":
        return AutoPriceProvider(alpha, stooq, yahoo)
    if name == "alpha_vantage":
        if alpha is None:
            raise SystemExit("ALPHA_VANTAGE_API_KEY is required for alpha_vantage")
        return SinglePriceProvider(alpha, "alpha_vantage")
    return SinglePriceProvider(stooq, "stooq")


def main() -> int:
    args = _parser().parse_args()
    settings = load_settings(args.settings)
    result = run_pipeline(
        settings=settings,
        cftc=CftcProvider(HttpClient(), settings),
        prices=_prices(args.price_provider, HttpClient()),
        notes=load_subjective_notes(args.notes),
        derived_output=args.derived_output,
        web_output=args.web_output,
        generated_at=pd.Timestamp.now(tz="UTC"),
    )
    print(
        f"generated={result.generated_files} "
        f"report_date={result.latest_report_date} "
        f"price_provider={result.price_provider}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
