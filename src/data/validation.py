"""Data validation and quality scoring for live research reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.data.periods import PeriodAlignmentResult, PeriodMetric, validate_matching_periods


@dataclass(frozen=True)
class ValidatedMetric:
    name: str
    value: object
    source: str
    date: str
    classification: str
    warning: str = ""
    source_url: str = ""
    provider: str = ""
    fiscal_period: str = ""
    confidence: str = "low"


@dataclass(frozen=True)
class DataQualityReport:
    metrics: tuple[ValidatedMetric, ...]
    missing_data_warnings: tuple[str, ...]
    stale_data_warnings: tuple[str, ...]
    inconsistent_date_warnings: tuple[str, ...]
    impossible_value_warnings: tuple[str, ...]
    data_quality_score: float
    mock_data_used: bool


ALLOWED_CLASSIFICATIONS = {
    "actual",
    "estimated",
    "model-generated",
    "unavailable",
    "fallback",
    "derived_calculation",
}


def validate_metrics(
    metrics: tuple[ValidatedMetric, ...],
    mock_data_used: bool = False,
) -> DataQualityReport:
    """Validate metric availability, dates, classification, and value sanity."""

    missing = []
    stale = []
    inconsistent = []
    impossible = []
    for metric in metrics:
        if metric.classification not in ALLOWED_CLASSIFICATIONS:
            inconsistent.append(f"{metric.name} has unsupported classification {metric.classification}.")
        if metric.value in (None, "", "Not available from current sources"):
            missing.append(f"{metric.name} is not available from current sources.")
        if not metric.date:
            stale.append(f"{metric.name} has no source date.")
        if isinstance(metric.value, (int, float)) and metric.value < 0 and metric.name.lower() in {"price", "shares outstanding", "revenue"}:
            impossible.append(f"{metric.name} has an impossible negative value.")
    penalty = len(missing) * 8 + len(stale) * 4 + len(inconsistent) * 8 + len(impossible) * 20
    if mock_data_used:
        penalty += 25
    score = max(0.0, 100.0 - penalty)
    return DataQualityReport(
        metrics=metrics,
        missing_data_warnings=tuple(missing),
        stale_data_warnings=tuple(stale),
        inconsistent_date_warnings=tuple(inconsistent),
        impossible_value_warnings=tuple(impossible),
        data_quality_score=score,
        mock_data_used=mock_data_used,
    )


def unavailable_metric(name: str, source: str) -> ValidatedMetric:
    """Create a standardized unavailable metric."""

    return ValidatedMetric(
        name=name,
        value="Not available from current sources",
        source=source,
        date=datetime.now(UTC).date().isoformat(),
        classification="unavailable",
        warning="Required source is unavailable or not configured.",
    )


def validate_margin_period_alignment(numerator: PeriodMetric, denominator: PeriodMetric) -> PeriodAlignmentResult:
    """Validate that margin numerator and denominator use the same period basis."""

    return validate_matching_periods(numerator, denominator)


def period_validation_warnings(metrics: tuple[PeriodMetric, ...]) -> tuple[str, ...]:
    """Return standardized period warnings for report diagnostics."""

    warnings: list[str] = []
    for metric in metrics:
        if metric.period.period_type == "quarterly":
            warnings.append(f"{metric.name}: quarterly value must not be used in TTM valuation without annualization or TTM build.")
        if metric.period.period_type == "annual":
            warnings.append(f"{metric.name}: annual value must not be mixed with quarterly values.")
        if metric.period.period_type == "quarterly" and metric.period.fiscal_quarter is None:
            warnings.append(f"{metric.name}: missing fiscal quarter.")
        if not metric.period.period_end_date and metric.period.period_type not in {"forward"}:
            warnings.append(f"{metric.name}: missing period end date.")
        if metric.warning:
            warnings.append(f"{metric.name}: {metric.warning}")
    return tuple(dict.fromkeys(warnings))
