"""Mock scenario valuation model.

TODO: Add richer methods for DCF, comparable multiples, historical multiples,
Bayesian growth valuation, TAM-adjusted PEG, and GF-DMA scoring once real
source-backed inputs are available.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioInput:
    """Inputs for a mock EV/EBITDA-based valuation scenario."""

    name: str
    revenue: float
    ebitda_margin: float
    ev_ebitda_multiple: float
    net_debt: float
    shares_outstanding: float
    probability: float


@dataclass(frozen=True)
class ScenarioValuation:
    """Calculated valuation output for one scenario."""

    name: str
    enterprise_value: float
    equity_value: float
    fair_value_per_share: float
    probability: float


@dataclass(frozen=True)
class EntryZones:
    """Entry-zone thresholds derived from probability-weighted fair value."""

    conservative_entry_max: float
    reasonable_accumulation_min: float
    reasonable_accumulation_max: float
    expensive_wait_min: float


def calculate_scenario(input_data: ScenarioInput) -> ScenarioValuation:
    """Calculate one mock valuation scenario from EV/EBITDA inputs."""

    if input_data.shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be positive.")
    if input_data.probability < 0:
        raise ValueError("Scenario probability cannot be negative.")

    ebitda = input_data.revenue * input_data.ebitda_margin
    enterprise_value = ebitda * input_data.ev_ebitda_multiple
    equity_value = enterprise_value - input_data.net_debt
    fair_value_per_share = equity_value / input_data.shares_outstanding

    return ScenarioValuation(
        name=input_data.name,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        fair_value_per_share=fair_value_per_share,
        probability=input_data.probability,
    )


def calculate_scenarios(
    bear: ScenarioInput,
    base: ScenarioInput,
    bull: ScenarioInput,
) -> tuple[ScenarioValuation, ScenarioValuation, ScenarioValuation]:
    """Calculate bear, base, and bull valuation scenarios."""

    return (
        calculate_scenario(bear),
        calculate_scenario(base),
        calculate_scenario(bull),
    )


def probability_weighted_fair_value(scenarios: Iterable[ScenarioValuation]) -> float:
    """Calculate probability-weighted fair value per share."""

    scenario_list = list(scenarios)
    if not scenario_list:
        raise ValueError("At least one scenario is required.")

    total_probability = sum(scenario.probability for scenario in scenario_list)
    if total_probability <= 0:
        raise ValueError("Scenario probabilities must sum to a positive value.")

    weighted_value = sum(
        scenario.fair_value_per_share * scenario.probability
        for scenario in scenario_list
    )
    return weighted_value / total_probability


def calculate_entry_zones(
    fair_value_per_share: float,
    conservative_discount: float = 0.25,
    reasonable_discount: float = 0.05,
) -> EntryZones:
    """Calculate entry zones from fair value.

    Defaults:
    - Conservative entry zone: up to 75% of fair value.
    - Reasonable accumulation zone: 75% to 95% of fair value.
    - Expensive/wait zone: above 95% of fair value.
    """

    if fair_value_per_share <= 0:
        raise ValueError("Fair value per share must be positive.")
    if not 0 <= reasonable_discount < conservative_discount < 1:
        raise ValueError(
            "Discounts must satisfy 0 <= reasonable_discount < "
            "conservative_discount < 1."
        )

    conservative_entry_max = fair_value_per_share * (1 - conservative_discount)
    expensive_wait_min = fair_value_per_share * (1 - reasonable_discount)

    return EntryZones(
        conservative_entry_max=conservative_entry_max,
        reasonable_accumulation_min=conservative_entry_max,
        reasonable_accumulation_max=expensive_wait_min,
        expensive_wait_min=expensive_wait_min,
    )
