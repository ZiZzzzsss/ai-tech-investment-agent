"""Valuation helpers for the research-agent prototype."""

from src.valuation.calculations import (
    gf_dma_average_score,
    scenario_weighted_value,
    tam_adjusted_peg,
)
from src.valuation.multiples import (
    enterprise_value,
    ev_to_ebitda,
    ev_to_sales,
    fcf_margin,
    period_aware_ev_to_ebitda,
    period_aware_ev_to_sales,
    period_aware_margin,
    period_aware_price_to_earnings,
    period_aware_price_to_fcf,
    period_aware_price_to_sales,
    price_to_earnings,
    price_to_fcf,
    revenue_cagr,
)
from src.valuation.scenario_model import (
    EntryZones,
    ScenarioInput,
    ScenarioValuation,
    calculate_entry_zones,
    calculate_scenario,
    calculate_scenarios,
    probability_weighted_fair_value,
)

__all__ = [
    "EntryZones",
    "ScenarioInput",
    "ScenarioValuation",
    "calculate_entry_zones",
    "calculate_scenario",
    "calculate_scenarios",
    "enterprise_value",
    "ev_to_ebitda",
    "ev_to_sales",
    "fcf_margin",
    "gf_dma_average_score",
    "period_aware_ev_to_ebitda",
    "period_aware_ev_to_sales",
    "period_aware_margin",
    "period_aware_price_to_earnings",
    "period_aware_price_to_fcf",
    "period_aware_price_to_sales",
    "price_to_earnings",
    "price_to_fcf",
    "probability_weighted_fair_value",
    "revenue_cagr",
    "scenario_weighted_value",
    "tam_adjusted_peg",
]
