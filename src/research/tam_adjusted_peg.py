"""TAM-adjusted PEG analysis for growth-stock valuation.

This module uses deterministic mock scoring rules. Inputs are intentionally
simple so the first working agent can explain how TAM, quality, cyclicality,
dilution, and execution risks affect growth-adjusted valuation.

TODO: Calibrate scoring against source-backed peer sets, reported financials,
market-share data, dilution history, cyclicality indicators, and real TAM
research once data connectors are available.
"""

from __future__ import annotations

from dataclasses import dataclass


ATTRACTIVE = "Attractive growth-adjusted valuation"
FAIR = "Fair growth-adjusted valuation"
EXPENSIVE_JUSTIFIED = "Expensive but possibly justified"
EXPENSIVE_WEAK = "Expensive and weakly supported"


@dataclass(frozen=True)
class TamAdjustedPegInput:
    """Inputs for TAM-adjusted PEG analysis.

    Expected EPS growth should be provided as a decimal rate. For example, 25%
    expected growth should be passed as 0.25.
    """

    pe_ratio: float
    expected_eps_growth: float
    tam_score: int
    business_quality_score: int
    cyclicality_score: int
    dilution_risk_score: int
    execution_risk_score: int


@dataclass(frozen=True)
class TamAdjustedPegResult:
    """TAM-adjusted PEG output."""

    traditional_peg: float
    tam_adjusted_peg: float
    quality_adjusted_interpretation: str
    explanation: str


def _validate_score(score: int, label: str) -> None:
    if score < 1 or score > 5:
        raise ValueError(f"{label} must be between 1 and 5.")


def traditional_peg(pe_ratio: float, expected_eps_growth: float) -> float:
    """Calculate traditional PEG using EPS growth in percentage-point form."""

    if pe_ratio < 0:
        raise ValueError("P/E cannot be negative.")
    if expected_eps_growth <= 0:
        raise ValueError("Expected EPS growth must be positive.")
    return pe_ratio / (expected_eps_growth * 100)


def tam_runway_adjustment(tam_score: int) -> float:
    """Return the TAM runway adjustment multiplier.

    Higher TAM scores reduce the PEG because a larger runway can support a
    higher growth multiple. Score 3 is neutral.
    """

    _validate_score(tam_score, "TAM score")
    return 1 - ((tam_score - 3) * 0.08)


def quality_adjustment(business_quality_score: int) -> float:
    """Return the business quality adjustment multiplier.

    Business quality is a compact score that stands in for pricing power, gross
    margin quality, recurring revenue quality, and competitive moat.
    """

    _validate_score(business_quality_score, "Business quality score")
    return 1 - ((business_quality_score - 3) * 0.07)


def risk_penalty_adjustment(
    cyclicality_score: int,
    dilution_risk_score: int,
    execution_risk_score: int,
) -> float:
    """Return the combined penalty multiplier for valuation risks."""

    _validate_score(cyclicality_score, "Cyclicality score")
    _validate_score(dilution_risk_score, "Dilution risk score")
    _validate_score(execution_risk_score, "Execution risk score")

    cyclicality_penalty = (cyclicality_score - 1) * 0.05
    dilution_penalty = (dilution_risk_score - 1) * 0.06
    execution_penalty = (execution_risk_score - 1) * 0.06
    return 1 + cyclicality_penalty + dilution_penalty + execution_penalty


def calculate_tam_adjusted_peg(inputs: TamAdjustedPegInput) -> TamAdjustedPegResult:
    """Calculate TAM-adjusted PEG and classification."""

    peg = traditional_peg(inputs.pe_ratio, inputs.expected_eps_growth)
    tam_multiplier = tam_runway_adjustment(inputs.tam_score)
    quality_multiplier = quality_adjustment(inputs.business_quality_score)
    risk_multiplier = risk_penalty_adjustment(
        inputs.cyclicality_score,
        inputs.dilution_risk_score,
        inputs.execution_risk_score,
    )
    adjusted_peg = peg * tam_multiplier * quality_multiplier * risk_multiplier
    interpretation = classify_tam_adjusted_peg(
        adjusted_peg,
        inputs.business_quality_score,
        inputs.tam_score,
    )

    return TamAdjustedPegResult(
        traditional_peg=peg,
        tam_adjusted_peg=adjusted_peg,
        quality_adjusted_interpretation=interpretation,
        explanation=_plain_english_explanation(
            inputs,
            peg,
            adjusted_peg,
            interpretation,
        ),
    )


def classify_tam_adjusted_peg(
    tam_adjusted_peg_value: float,
    business_quality_score: int,
    tam_score: int,
) -> str:
    """Classify growth-adjusted valuation support."""

    if tam_adjusted_peg_value <= 1.0:
        return ATTRACTIVE
    if tam_adjusted_peg_value <= 1.6:
        return FAIR
    if tam_adjusted_peg_value <= 2.3 and business_quality_score >= 4 and tam_score >= 4:
        return EXPENSIVE_JUSTIFIED
    return EXPENSIVE_WEAK


def _plain_english_explanation(
    inputs: TamAdjustedPegInput,
    peg: float,
    adjusted_peg: float,
    interpretation: str,
) -> str:
    return (
        f"Traditional PEG is {peg:.2f}x. "
        f"After adjusting for TAM runway, business quality, cyclicality, dilution risk, "
        f"and execution risk, TAM-adjusted PEG is {adjusted_peg:.2f}x. "
        f"The valuation classification is: {interpretation}. "
        "Higher TAM and business quality scores reduce the adjusted PEG, while higher "
        "cyclicality, dilution, and execution risk scores increase it."
    )
