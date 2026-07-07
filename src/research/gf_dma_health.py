"""GF-DMA health index for trend health and entry discipline.

GF-DMA combines Growth/Fundamentals with daily moving-average trend health.
It does not generate intrinsic value. It is only a timing, trend-health, and
entry-discipline framework for mock reports.

TODO: Calibrate thresholds using source-backed historical fundamentals,
estimate revision data, price histories, sector relative-strength data, and
valuation multiple histories once real data connectors are available.
"""

from __future__ import annotations

from dataclasses import dataclass


HEALTHY_SUPPORTED = "Healthy trend supported by fundamentals"
STRONG_EXTENDED = "Strong company but technically extended"
SPECULATIVE_MOMENTUM = "Weak fundamentals with speculative momentum"
DETERIORATING = "Deteriorating trend and fundamentals"


@dataclass(frozen=True)
class GfDmaHealthInput:
    """Inputs for GF-DMA health scoring.

    Growth, estimate revision, relative strength, and valuation expansion
    inputs should be decimal rates. For example, 20% should be passed as 0.20.
    """

    revenue_growth: float
    eps_growth: float
    fcf_growth: float
    estimate_revision_trend: float
    current_price: float
    dma_20: float
    dma_50: float
    dma_100: float
    dma_200: float
    relative_strength_vs_sector: float
    valuation_multiple_expansion: float


@dataclass(frozen=True)
class GfDmaHealthResult:
    """GF-DMA health index output."""

    fundamental_growth_score: float
    dma_trend_score: float
    divergence_score: float
    escape_ratio: float
    estimate_revision_score: float
    overall_gf_dma_health_score: float
    interpretation: str
    overextension_risk: bool
    explanation: str


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(value, upper))


def _validate_prices(inputs: GfDmaHealthInput) -> None:
    prices = (
        inputs.current_price,
        inputs.dma_20,
        inputs.dma_50,
        inputs.dma_100,
        inputs.dma_200,
    )
    if any(price <= 0 for price in prices):
        raise ValueError("Current price and moving averages must be positive.")


def fundamental_growth_score(
    revenue_growth: float,
    eps_growth: float,
    fcf_growth: float,
) -> float:
    """Score source of growth from revenue, EPS, and FCF growth."""

    average_growth = (revenue_growth + eps_growth + fcf_growth) / 3
    return round(_clamp(50 + average_growth * 180), 1)


def estimate_revision_score(estimate_revision_trend: float) -> float:
    """Score estimate revision trend."""

    return round(_clamp(50 + estimate_revision_trend * 250), 1)


def dma_trend_score(inputs: GfDmaHealthInput) -> float:
    """Score moving-average stack and price position."""

    _validate_prices(inputs)
    score = 0.0
    score += 25.0 if inputs.current_price > inputs.dma_20 else 0.0
    score += 20.0 if inputs.dma_20 > inputs.dma_50 else 0.0
    score += 20.0 if inputs.dma_50 > inputs.dma_100 else 0.0
    score += 20.0 if inputs.dma_100 > inputs.dma_200 else 0.0
    score += 15.0 if inputs.relative_strength_vs_sector > 0 else 0.0
    return round(score, 1)


def escape_ratio(inputs: GfDmaHealthInput) -> float:
    """Measure price extension versus the 200-day moving average."""

    _validate_prices(inputs)
    return inputs.current_price / inputs.dma_200


def divergence_score(inputs: GfDmaHealthInput) -> float:
    """Score whether price momentum is supported by fundamentals and revisions.

    Higher is healthier. Large price extension, multiple expansion, and weak
    revisions reduce the score.
    """

    ratio = escape_ratio(inputs)
    overextension_penalty = max(0.0, ratio - 1.15) * 120
    multiple_penalty = max(0.0, inputs.valuation_multiple_expansion) * 80
    weak_revision_penalty = max(0.0, -inputs.estimate_revision_trend) * 180
    support_bonus = max(0.0, inputs.estimate_revision_trend) * 120

    score = 80 + support_bonus - overextension_penalty - multiple_penalty - weak_revision_penalty
    return round(_clamp(score), 1)


def is_overextended(inputs: GfDmaHealthInput) -> bool:
    """Flag price extension without estimate revision support."""

    return (
        escape_ratio(inputs) >= 1.25
        and inputs.current_price / inputs.dma_50 >= 1.12
        and inputs.estimate_revision_trend <= 0.02
    )


def calculate_gf_dma_health(inputs: GfDmaHealthInput) -> GfDmaHealthResult:
    """Calculate GF-DMA health index."""

    _validate_prices(inputs)
    fundamental_score = fundamental_growth_score(
        inputs.revenue_growth,
        inputs.eps_growth,
        inputs.fcf_growth,
    )
    trend_score = dma_trend_score(inputs)
    divergence = divergence_score(inputs)
    revision_score = estimate_revision_score(inputs.estimate_revision_trend)
    ratio = escape_ratio(inputs)
    overextended = is_overextended(inputs)

    overall_score = round(
        _clamp(
            fundamental_score * 0.30
            + trend_score * 0.25
            + divergence * 0.20
            + revision_score * 0.20
            + _clamp(inputs.relative_strength_vs_sector * 200 + 50) * 0.05
        ),
        1,
    )
    interpretation = interpret_gf_dma_health(
        fundamental_score,
        trend_score,
        divergence,
        revision_score,
        overextended,
    )

    return GfDmaHealthResult(
        fundamental_growth_score=fundamental_score,
        dma_trend_score=trend_score,
        divergence_score=divergence,
        escape_ratio=round(ratio, 3),
        estimate_revision_score=revision_score,
        overall_gf_dma_health_score=overall_score,
        interpretation=interpretation,
        overextension_risk=overextended,
        explanation=_plain_english_explanation(overall_score, interpretation, overextended),
    )


def interpret_gf_dma_health(
    fundamental_score: float,
    trend_score: float,
    divergence: float,
    revision_score: float,
    overextended: bool,
) -> str:
    """Map GF-DMA component scores to a plain-English interpretation."""

    if fundamental_score < 45 and trend_score < 45 and revision_score < 45:
        return DETERIORATING
    if fundamental_score < 45 and trend_score >= 65:
        return SPECULATIVE_MOMENTUM
    if overextended or (fundamental_score >= 65 and trend_score >= 70 and divergence < 55):
        return STRONG_EXTENDED
    if fundamental_score >= 75 and trend_score >= 45 and revision_score >= 45 and divergence >= 55:
        return HEALTHY_SUPPORTED
    if fundamental_score >= 60 and trend_score >= 65 and revision_score >= 55 and divergence >= 55:
        return HEALTHY_SUPPORTED
    return DETERIORATING


def _plain_english_explanation(
    overall_score: float,
    interpretation: str,
    overextended: bool,
) -> str:
    risk_note = (
        " Price is far above key moving averages without enough estimate revision support, so overextension risk is flagged."
        if overextended
        else ""
    )
    return (
        f"Overall GF-DMA health score is {overall_score:.1f}/100. "
        f"Interpretation: {interpretation}. "
        "This index evaluates timing, trend health, and entry discipline only; it does not estimate intrinsic value."
        f"{risk_note}"
    )
