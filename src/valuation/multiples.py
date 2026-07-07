"""Valuation multiple and financial ratio calculations.

TODO: Replace mock inputs with normalized financial statement and market-data
inputs once real connectors are implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.periods import (
    PeriodMetric,
    validate_market_financial_alignment,
    validate_matching_periods,
    validate_ttm_denominator,
)


@dataclass(frozen=True)
class PeriodAwareCalculation:
    """Valuation output with visible period basis and alignment warning."""

    metric_name: str
    value: float | None
    formula: str
    input_values: dict[str, float | None]
    input_periods: dict[str, str]
    output_period_basis: str
    warning: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None and not self.warning


def _require_positive(value: float, label: str) -> None:
    if value <= 0:
        raise ValueError(f"{label} must be positive.")


def enterprise_value(
    market_cap: float,
    total_debt: float,
    cash_and_equivalents: float,
    minority_interest: float = 0.0,
    preferred_equity: float = 0.0,
) -> float:
    """Calculate enterprise value."""

    return (
        market_cap
        + total_debt
        + minority_interest
        + preferred_equity
        - cash_and_equivalents
    )


def ev_to_sales(enterprise_value_amount: float, revenue: float) -> float:
    """Calculate EV/Sales."""

    _require_positive(revenue, "Revenue")
    return enterprise_value_amount / revenue


def ev_to_ebitda(enterprise_value_amount: float, ebitda: float) -> float:
    """Calculate EV/EBITDA."""

    _require_positive(ebitda, "EBITDA")
    return enterprise_value_amount / ebitda


def price_to_earnings(market_cap: float, net_income: float) -> float:
    """Calculate P/E."""

    _require_positive(net_income, "Net income")
    return market_cap / net_income


def price_to_fcf(market_cap: float, free_cash_flow: float) -> float:
    """Calculate P/FCF."""

    _require_positive(free_cash_flow, "Free cash flow")
    return market_cap / free_cash_flow


def revenue_cagr(start_revenue: float, end_revenue: float, years: float) -> float:
    """Calculate revenue compound annual growth rate."""

    _require_positive(start_revenue, "Start revenue")
    _require_positive(end_revenue, "End revenue")
    _require_positive(years, "Years")
    return (end_revenue / start_revenue) ** (1 / years) - 1


def fcf_margin(free_cash_flow: float, revenue: float) -> float:
    """Calculate free-cash-flow margin."""

    _require_positive(revenue, "Revenue")
    return free_cash_flow / revenue


def period_aware_ev_to_sales(enterprise_value_metric: PeriodMetric, revenue_metric: PeriodMetric) -> PeriodAwareCalculation:
    return _period_aware_market_multiple(
        "EV/Sales",
        "EV/Sales = enterprise value / TTM revenue",
        enterprise_value_metric,
        revenue_metric,
        "enterprise_value",
        "revenue",
        ev_to_sales,
    )


def period_aware_ev_to_ebitda(enterprise_value_metric: PeriodMetric, ebitda_metric: PeriodMetric) -> PeriodAwareCalculation:
    return _period_aware_market_multiple(
        "EV/EBITDA",
        "EV/EBITDA = enterprise value / TTM EBITDA",
        enterprise_value_metric,
        ebitda_metric,
        "enterprise_value",
        "ebitda",
        ev_to_ebitda,
    )


def period_aware_price_to_earnings(market_cap_metric: PeriodMetric, net_income_metric: PeriodMetric) -> PeriodAwareCalculation:
    return _period_aware_market_multiple(
        "P/E",
        "P/E = market cap / TTM net income",
        market_cap_metric,
        net_income_metric,
        "market_cap",
        "net_income",
        price_to_earnings,
    )


def period_aware_price_to_fcf(market_cap_metric: PeriodMetric, fcf_metric: PeriodMetric) -> PeriodAwareCalculation:
    return _period_aware_market_multiple(
        "P/FCF",
        "P/FCF = market cap / TTM free cash flow",
        market_cap_metric,
        fcf_metric,
        "market_cap",
        "free_cash_flow",
        price_to_fcf,
    )


def period_aware_price_to_sales(market_cap_metric: PeriodMetric, revenue_metric: PeriodMetric) -> PeriodAwareCalculation:
    return _period_aware_market_multiple(
        "P/S",
        "P/S = market cap / TTM revenue",
        market_cap_metric,
        revenue_metric,
        "market_cap",
        "revenue",
        lambda cap, sales: cap / sales,
    )


def period_aware_margin(
    metric_name: str,
    numerator_metric: PeriodMetric,
    revenue_metric: PeriodMetric,
    numerator_key: str,
) -> PeriodAwareCalculation:
    alignment = validate_matching_periods(numerator_metric, revenue_metric)
    formula = f"{metric_name} = matching-period {numerator_key} / revenue"
    if not alignment.aligned:
        return _period_calc_unavailable(
            metric_name,
            formula,
            {numerator_key: numerator_metric, "revenue": revenue_metric},
            numerator_metric.period.period_type,
            alignment.warning,
        )
    if revenue_metric.value in (None, 0):
        return _period_calc_unavailable(
            metric_name,
            formula,
            {numerator_key: numerator_metric, "revenue": revenue_metric},
            numerator_metric.period.period_type,
            "Unavailable: revenue missing or zero",
        )
    value = float(numerator_metric.value) / float(revenue_metric.value)  # type: ignore[arg-type]
    return PeriodAwareCalculation(
        metric_name=metric_name,
        value=value,
        formula=formula,
        input_values={numerator_key: numerator_metric.value, "revenue": revenue_metric.value},
        input_periods={numerator_key: numerator_metric.period.label, "revenue": revenue_metric.period.label},
        output_period_basis=numerator_metric.period.period_type,
    )


def _period_aware_market_multiple(
    metric_name: str,
    formula: str,
    numerator_metric: PeriodMetric,
    denominator_metric: PeriodMetric,
    numerator_key: str,
    denominator_key: str,
    calculation,
) -> PeriodAwareCalculation:
    alignment = validate_market_financial_alignment(numerator_metric, denominator_metric)
    denominator_alignment = validate_ttm_denominator(denominator_metric, denominator_key)
    warning = alignment.warning or denominator_alignment.warning
    inputs = {numerator_key: numerator_metric, denominator_key: denominator_metric}
    if warning:
        return _period_calc_unavailable(metric_name, formula, inputs, "TTM", warning)
    try:
        value = calculation(float(numerator_metric.value), float(denominator_metric.value))  # type: ignore[arg-type]
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        return _period_calc_unavailable(metric_name, formula, inputs, "TTM", f"Unavailable: {exc}")
    return PeriodAwareCalculation(
        metric_name=metric_name,
        value=value,
        formula=formula,
        input_values={key: metric.value for key, metric in inputs.items()},
        input_periods={key: metric.period.label for key, metric in inputs.items()},
        output_period_basis="TTM",
    )


def _period_calc_unavailable(
    metric_name: str,
    formula: str,
    inputs: dict[str, PeriodMetric],
    output_period_basis: str,
    warning: str,
) -> PeriodAwareCalculation:
    return PeriodAwareCalculation(
        metric_name=metric_name,
        value=None,
        formula=formula,
        input_values={key: metric.value for key, metric in inputs.items()},
        input_periods={key: metric.period.label for key, metric in inputs.items()},
        output_period_basis=output_period_basis,
        warning=warning,
    )
