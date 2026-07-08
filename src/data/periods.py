"""Fiscal-period normalization, TTM calculation, and alignment checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable


ALLOWED_PERIOD_TYPES = frozenset({"quarterly", "annual", "ttm", "forward", "point_in_time"})


@dataclass(frozen=True)
class FiscalPeriod:
    """Normalized fiscal-period metadata attached to source-backed values."""

    period_type: str
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    period_start_date: str = ""
    period_end_date: str = ""
    filing_date: str = ""
    source_name: str = ""
    source_period_label: str = ""
    currency: str = "USD"
    confidence: str = "medium"
    warning: str = ""

    def __post_init__(self) -> None:
        if self.period_type not in ALLOWED_PERIOD_TYPES:
            raise ValueError(f"Unsupported period_type: {self.period_type}")
        if self.period_type == "quarterly" and self.fiscal_quarter not in {1, 2, 3, 4}:
            raise ValueError("quarterly periods require fiscal_quarter 1-4")

    @property
    def label(self) -> str:
        if self.source_period_label:
            return self.source_period_label
        if self.period_type == "quarterly" and self.fiscal_year and self.fiscal_quarter:
            return f"FY{self.fiscal_year} Q{self.fiscal_quarter}"
        if self.period_type == "annual" and self.fiscal_year:
            return f"FY{self.fiscal_year}"
        if self.period_type == "ttm":
            return "TTM"
        if self.period_type == "forward":
            return "Forward"
        return self.period_end_date or "Point in time"


@dataclass(frozen=True)
class PeriodMetric:
    """One numeric value with fiscal-period basis and source lineage."""

    name: str
    value: float | None
    period: FiscalPeriod
    source_name: str
    source_url: str = ""
    source_lineage: tuple[str, ...] = ()
    formula: str = ""
    warning: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None and not self.warning.lower().startswith("unavailable")


@dataclass(frozen=True)
class PeriodAlignmentResult:
    aligned: bool
    warning: str = ""


def point_in_time_period(as_of_date: str = "", source_name: str = "", currency: str = "USD") -> FiscalPeriod:
    return FiscalPeriod(
        period_type="point_in_time",
        period_end_date=as_of_date,
        source_name=source_name,
        source_period_label=as_of_date or "Point in time",
        currency=currency,
        confidence="high" if as_of_date else "medium",
        warning="" if as_of_date else "missing period end date",
    )


def normalize_period_label(
    raw_label: str = "",
    provider: str = "",
    as_of_date: str = "",
    currency: str = "USD",
    filing_date: str = "",
) -> FiscalPeriod:
    """Normalize common provider period labels into a FiscalPeriod."""

    label = (raw_label or as_of_date or "").strip()
    upper = label.upper()
    fiscal_year = _extract_year(upper)
    fiscal_quarter = _extract_quarter(upper)
    if "TTM" in upper or "TRAILING" in upper:
        period_type = "ttm"
    elif "FORWARD" in upper or "NTM" in upper:
        period_type = "forward"
    elif fiscal_quarter is not None or ("Q" in upper and fiscal_year is not None):
        period_type = "quarterly"
    elif "FY" in upper or fiscal_year is not None:
        period_type = "annual"
    elif as_of_date:
        period_type = "point_in_time"
    else:
        period_type = "point_in_time"
    warning = ""
    if period_type == "quarterly" and fiscal_quarter is None:
        warning = "missing fiscal quarter"
    if not (as_of_date or label):
        warning = "missing period end date"
    return FiscalPeriod(
        period_type=period_type,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        period_end_date=as_of_date if _looks_like_date(as_of_date) else (label if _looks_like_date(label) else ""),
        filing_date=filing_date,
        source_name=provider,
        source_period_label=label,
        currency=currency,
        confidence="medium" if warning else "high",
        warning=warning,
    )


def fiscal_period_from_sec_row(row: dict[str, object], source_name: str = "SEC EDGAR", currency: str = "USD") -> FiscalPeriod:
    fp = str(row.get("fp", "") or "").upper()
    frame = str(row.get("frame", "") or "").upper()
    period_end = str(row.get("period", "") or row.get("end", "") or "")
    filed = str(row.get("filed", "") or "")
    fiscal_quarter = _extract_quarter(fp) or _extract_quarter(frame)
    fiscal_year = _extract_year(frame) or _extract_year(period_end)
    if fp == "FY" or "FY" in frame:
        period_type = "annual"
    elif fiscal_quarter is not None:
        period_type = "quarterly"
    else:
        period_type = "point_in_time"
    warning = ""
    if period_type == "quarterly" and fiscal_quarter is None:
        warning = "missing fiscal quarter"
    if not period_end:
        warning = "missing period end date"
    return FiscalPeriod(
        period_type=period_type,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        period_end_date=period_end,
        filing_date=filed,
        source_name=source_name,
        source_period_label=frame or fp or period_end,
        currency=currency,
        confidence="medium" if warning else "high",
        warning=warning,
    )


def period_metric_from_sec_row(metric_name: str, row: dict[str, object], currency: str = "USD") -> PeriodMetric:
    value = _number(row.get("value"))
    period = fiscal_period_from_sec_row(row, currency=currency)
    return PeriodMetric(
        name=metric_name,
        value=value,
        period=period,
        source_name=str(row.get("source", "SEC EDGAR company facts")),
        source_lineage=(period.label,),
        warning=period.warning,
    )


def calculate_ttm_metric(metric_name: str, quarterly_metrics: Iterable[PeriodMetric]) -> PeriodMetric:
    """Calculate TTM as the sum of the latest four comparable fiscal quarters."""

    quarters = _latest_four_comparable_quarters(tuple(quarterly_metrics))
    if len(quarters) < 4:
        return _unavailable_ttm(metric_name, "fewer than four quarters available for TTM", quarters)
    currency_warnings = _currency_warning(quarters)
    if currency_warnings:
        return _unavailable_ttm(metric_name, currency_warnings, quarters)
    values = [metric.value for metric in quarters]
    if any(value is None for value in values):
        return _unavailable_ttm(metric_name, "missing quarterly value in TTM source lineage", quarters)
    if metric_name.lower() in {"capital_expenditure", "capex", "ttm_capex"}:
        total = sum(abs(float(value)) for value in values if value is not None)
        formula = "TTM capex = sum(abs(last four quarterly capex values))"
    else:
        total = sum(float(value) for value in values if value is not None)
        formula = "TTM = sum(last four comparable fiscal quarters)"
    latest = quarters[-1]
    earliest = quarters[0]
    period = FiscalPeriod(
        period_type="ttm",
        fiscal_year=latest.period.fiscal_year,
        fiscal_quarter=latest.period.fiscal_quarter,
        period_start_date=earliest.period.period_start_date,
        period_end_date=latest.period.period_end_date,
        filing_date=latest.period.filing_date,
        source_name=latest.period.source_name,
        source_period_label=f"{earliest.period.label}-{latest.period.label}",
        currency=latest.period.currency,
        confidence="high",
    )
    return PeriodMetric(
        name=f"ttm_{metric_name.removeprefix('ttm_')}",
        value=total,
        period=period,
        source_name=_combined_source(quarters),
        source_lineage=tuple(metric.period.label for metric in quarters),
        formula=formula,
    )


def calculate_ttm_free_cash_flow(operating_cash_flow_ttm: PeriodMetric, capex_ttm: PeriodMetric) -> PeriodMetric:
    alignment = validate_matching_periods(operating_cash_flow_ttm, capex_ttm)
    if not alignment.aligned:
        return PeriodMetric(
            name="ttm_free_cash_flow",
            value=None,
            period=operating_cash_flow_ttm.period,
            source_name=operating_cash_flow_ttm.source_name,
            source_lineage=operating_cash_flow_ttm.source_lineage + capex_ttm.source_lineage,
            formula="TTM FCF = TTM operating cash flow - TTM capex",
            warning=alignment.warning,
        )
    if operating_cash_flow_ttm.value is None or capex_ttm.value is None:
        warning = "Unavailable: operating cash flow or capex TTM missing"
        value = None
    else:
        warning = ""
        value = float(operating_cash_flow_ttm.value) - abs(float(capex_ttm.value))
    return PeriodMetric(
        name="ttm_free_cash_flow",
        value=value,
        period=operating_cash_flow_ttm.period,
        source_name=operating_cash_flow_ttm.source_name,
        source_lineage=operating_cash_flow_ttm.source_lineage + capex_ttm.source_lineage,
        formula="TTM FCF = TTM operating cash flow - TTM capex",
        warning=warning,
    )


def validate_ttm_denominator(metric: PeriodMetric, metric_name: str) -> PeriodAlignmentResult:
    if metric.value is None:
        return PeriodAlignmentResult(False, f"Unavailable: {metric_name} missing")
    if metric.period.period_type != "ttm":
        return PeriodAlignmentResult(
            False,
            f"Unavailable: {metric_name} must be TTM for valuation multiple; got {metric.period.period_type}",
        )
    return PeriodAlignmentResult(True)


def validate_matching_periods(numerator: PeriodMetric, denominator: PeriodMetric) -> PeriodAlignmentResult:
    if numerator.value is None or denominator.value is None:
        return PeriodAlignmentResult(False, "Unavailable: missing numerator or denominator")
    if numerator.period.currency != denominator.period.currency:
        return PeriodAlignmentResult(False, "Unavailable: mismatched currency")
    if numerator.period.period_type != denominator.period.period_type:
        return PeriodAlignmentResult(
            False,
            f"Unavailable: period mismatch ({numerator.period.period_type} vs {denominator.period.period_type})",
        )
    if numerator.period.period_end_date and denominator.period.period_end_date and numerator.period.period_end_date != denominator.period.period_end_date:
        return PeriodAlignmentResult(False, "Unavailable: mismatched fiscal period")
    return PeriodAlignmentResult(True)


def validate_market_financial_alignment(market_metric: PeriodMetric, financial_metric: PeriodMetric) -> PeriodAlignmentResult:
    if market_metric.period.period_type != "point_in_time":
        return PeriodAlignmentResult(False, "Unavailable: market cap must be point-in-time")
    if financial_metric.period.period_type != "ttm":
        return PeriodAlignmentResult(
            False,
            f"Unavailable: financial denominator must be TTM; got {financial_metric.period.period_type}",
        )
    if market_metric.period.currency != financial_metric.period.currency:
        return PeriodAlignmentResult(False, "Unavailable: mismatched currency")
    return PeriodAlignmentResult(True)


def period_warnings(metrics: Iterable[PeriodMetric]) -> tuple[str, ...]:
    warnings: list[str] = []
    for metric in metrics:
        if metric.period.warning:
            warnings.append(f"{metric.name}: {metric.period.warning}")
        if metric.warning:
            warnings.append(f"{metric.name}: {metric.warning}")
    return tuple(warnings)


def _latest_four_comparable_quarters(metrics: tuple[PeriodMetric, ...]) -> tuple[PeriodMetric, ...]:
    quarters = [*_deduplicated_quarters(metrics), *_derived_fourth_quarters(metrics)]
    quarters = sorted(quarters, key=lambda metric: metric.period.period_end_date)
    if len(quarters) < 4:
        return tuple(quarters)
    latest_four = tuple(quarters[-4:])
    quarter_keys = {(metric.period.period_end_date, metric.period.fiscal_quarter) for metric in latest_four}
    return latest_four if len(quarter_keys) == 4 else ()


def _deduplicated_quarters(metrics: tuple[PeriodMetric, ...]) -> tuple[PeriodMetric, ...]:
    by_period: dict[tuple[str, int], PeriodMetric] = {}
    for metric in metrics:
        if (
            metric.period.period_type != "quarterly"
            or metric.period.fiscal_quarter not in {1, 2, 3, 4}
            or not metric.period.period_end_date
        ):
            continue
        key = (metric.period.period_end_date, metric.period.fiscal_quarter)
        current = by_period.get(key)
        if current is None or _quarter_quality(metric) > _quarter_quality(current):
            by_period[key] = metric
    return tuple(sorted(by_period.values(), key=lambda metric: metric.period.period_end_date))


def _derived_fourth_quarters(metrics: tuple[PeriodMetric, ...]) -> tuple[PeriodMetric, ...]:
    quarters = _deduplicated_quarters(metrics)
    annuals = sorted(
        (
            metric
            for metric in metrics
            if metric.period.period_type == "annual"
            and metric.value is not None
            and metric.period.period_end_date
        ),
        key=lambda metric: metric.period.period_end_date,
    )
    derived: list[PeriodMetric] = []
    existing_q4_dates = {metric.period.period_end_date for metric in quarters if metric.period.fiscal_quarter == 4}
    for annual in annuals:
        if annual.period.period_end_date in existing_q4_dates:
            continue
        prior = [
            metric
            for metric in quarters
            if metric.value is not None
            and metric.period.fiscal_quarter in {1, 2, 3}
            and metric.period.period_end_date < annual.period.period_end_date
        ]
        latest_by_quarter: dict[int, PeriodMetric] = {}
        for metric in prior:
            quarter = int(metric.period.fiscal_quarter or 0)
            current = latest_by_quarter.get(quarter)
            if current is None or metric.period.period_end_date > current.period.period_end_date:
                latest_by_quarter[quarter] = metric
        if set(latest_by_quarter) != {1, 2, 3}:
            continue
        first_three = tuple(latest_by_quarter[quarter] for quarter in (1, 2, 3))
        derived_value = float(annual.value) - sum(float(metric.value) for metric in first_three if metric.value is not None)
        if derived_value < 0:
            continue
        period = FiscalPeriod(
            period_type="quarterly",
            fiscal_year=annual.period.fiscal_year,
            fiscal_quarter=4,
            period_end_date=annual.period.period_end_date,
            filing_date=annual.period.filing_date,
            source_name=annual.period.source_name,
            source_period_label=f"{annual.period.label} derived Q4",
            currency=annual.period.currency,
            confidence="medium",
            warning="",
        )
        derived.append(
            PeriodMetric(
                name=annual.name,
                value=derived_value,
                period=period,
                source_name=annual.source_name,
                source_url=annual.source_url,
                source_lineage=tuple(metric.period.label for metric in first_three) + (annual.period.label,),
                formula="Derived Q4 = annual value - Q1 - Q2 - Q3",
            )
        )
    return tuple(derived)


def _quarter_quality(metric: PeriodMetric) -> int:
    label = metric.period.source_period_label.upper()
    score = 0
    if metric.period.fiscal_year is not None:
        score += 1
    if "CY" in label or "FY" in label:
        score += 2
    if metric.source_lineage:
        score += 1
    return score


def _unavailable_ttm(metric_name: str, warning: str, quarters: tuple[PeriodMetric, ...]) -> PeriodMetric:
    period = FiscalPeriod(
        period_type="ttm",
        source_period_label="TTM unavailable",
        confidence="low",
        warning=warning,
    )
    return PeriodMetric(
        name=f"ttm_{metric_name.removeprefix('ttm_')}",
        value=None,
        period=period,
        source_name=_combined_source(quarters) if quarters else "Not available from current sources",
        source_lineage=tuple(metric.period.label for metric in quarters),
        formula="TTM = sum(last four comparable fiscal quarters)",
        warning=f"Unavailable: {warning}",
    )


def _combined_source(metrics: tuple[PeriodMetric, ...]) -> str:
    sources = sorted({metric.source_name for metric in metrics if metric.source_name})
    return ", ".join(sources) if sources else "Not available from current sources"


def _currency_warning(metrics: tuple[PeriodMetric, ...]) -> str:
    currencies = {metric.period.currency for metric in metrics}
    return "mismatched currency" if len(currencies) > 1 else ""


def _extract_quarter(label: str) -> int | None:
    for quarter in (1, 2, 3, 4):
        if f"Q{quarter}" in label:
            return quarter
    return None


def _extract_year(label: str) -> int | None:
    digits = "".join(character if character.isdigit() else " " for character in label).split()
    for token in digits:
        if len(token) == 4 and token.startswith(("19", "20")):
            return int(token)
    return None


def _looks_like_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


__all__ = [
    "ALLOWED_PERIOD_TYPES",
    "FiscalPeriod",
    "PeriodAlignmentResult",
    "PeriodMetric",
    "calculate_ttm_free_cash_flow",
    "calculate_ttm_metric",
    "fiscal_period_from_sec_row",
    "normalize_period_label",
    "period_metric_from_sec_row",
    "period_warnings",
    "point_in_time_period",
    "validate_market_financial_alignment",
    "validate_matching_periods",
    "validate_ttm_denominator",
]
