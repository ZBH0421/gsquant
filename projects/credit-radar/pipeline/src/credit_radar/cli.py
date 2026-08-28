from __future__ import annotations

import argparse
from pathlib import Path

from credit_radar.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Credit Stress / Reversal Radar artifacts")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("projects/credit-radar/config/settings.yaml"),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("projects/credit-radar"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_pipeline(project_root=args.root, settings_path=args.config)
    print(f"Credit Radar {result['as_of']}: {result['state']}")


if __name__ == "__main__":
    main()
