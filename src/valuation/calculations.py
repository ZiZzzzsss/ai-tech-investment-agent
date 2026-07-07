"""Deterministic valuation calculations for mock reports.

TODO: Add real valuation models that consume normalized filing, market-data,
and company-guidance inputs from connector modules.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.connectors.mock_data import GfDmaHealthView, Scenario


def scenario_weighted_value(scenarios: Iterable[Scenario]) -> float:
    """Calculate probability-weighted implied value per share."""

    scenario_list = list(scenarios)
    if not scenario_list:
        raise ValueError("At least one scenario is required.")

    total_probability = sum(scenario.probability for scenario in scenario_list)
    if total_probability <= 0:
        raise ValueError("Scenario probabilities must sum to a positive value.")

    weighted_value = sum(
        scenario.implied_value_per_share * scenario.probability
        for scenario in scenario_list
    )
    return weighted_value / total_probability


def tam_adjusted_peg(conventional_peg: float, tam_discount: float) -> float:
    """Apply a simple mock TAM discount to a conventional PEG ratio."""

    if conventional_peg < 0:
        raise ValueError("Conventional PEG cannot be negative.")
    if not 0 <= tam_discount < 1:
        raise ValueError("TAM discount must be greater than or equal to 0 and less than 1.")
    return conventional_peg * (1 - tam_discount)


def gf_dma_average_score(scorecard: GfDmaHealthView) -> float:
    """Return the simple average GF-DMA health score."""

    scores = (
        scorecard.growth,
        scorecard.financial_quality,
        scorecard.demand_momentum,
        scorecard.moat_durability,
        scorecard.ai_execution,
    )
    for score in scores:
        if score < 0 or score > 10:
            raise ValueError("GF-DMA scores must be between 0 and 10.")
    return sum(scores) / len(scores)
