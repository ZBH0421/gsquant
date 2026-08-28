from __future__ import annotations

from dataclasses import dataclass


class DataContractError(ValueError):
    """Raised when upstream or generated data violates the expected contract."""


@dataclass(frozen=True)
class Evidence:
    objective_facts: str
    rule_classification: str
    market_inference: str
    alternative_explanations: str
    confirmation: str
    invalidation: str


@dataclass(frozen=True)
class PipelineResult:
    generated_files: int
    latest_report_date: str
    price_provider: str
