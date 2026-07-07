"""Bayesian-style intrinsic growth regime estimator.

This module uses mock, deterministic evidence weights only. It is designed to
separate fundamental evidence from market-price momentum while the project is
still running on placeholder data.

TODO: Calibrate priors, likelihoods, and evidence confidence using source-backed
historical data, filings, earnings releases, contract disclosures, RPO/backlog
data, estimate revisions, and official industry or macro datasets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GrowthHypothesis(str, Enum):
    """Intrinsic growth regime hypotheses."""

    H0 = "contraction"
    H1 = "mature slow growth"
    H2 = "steady growth"
    H3 = "high-cycle growth"
    H4 = "structural breakout"
    H5 = "platform expansion"


@dataclass(frozen=True)
class BayesianGrowthInput:
    """Inputs for Bayesian-style intrinsic growth estimation.

    Percent inputs should be provided as decimal rates. For example, 25% should
    be passed as 0.25.
    """

    revenue_growth: float
    gross_margin_trend: float
    operating_margin_trend: float
    free_cash_flow_trend: float
    backlog_or_rpo_growth: float
    signed_customer_contracts: int
    vague_partnerships: int = 0
    rumor_intensity: float = 0.0
    hyperscaler_capex_exposure: float = 0.0
    estimate_revisions: float = 0.0
    ai_market_exposure: float = 0.0
    stock_price_performance: float = 0.0
    fundamental_performance: float = 0.0
    market_implied_growth: float = 0.0
    valuation_premium: float = 0.0


@dataclass(frozen=True)
class BayesianGrowthResult:
    """Bayesian-style growth estimation output."""

    prior_probabilities: dict[GrowthHypothesis, float]
    updated_probabilities: dict[GrowthHypothesis, float]
    most_likely_regime: GrowthHypothesis
    intrinsic_growth_estimate: float
    market_implied_growth: float
    market_implied_comparison: str
    fomo_risk_score: float
    explanation: str


DEFAULT_PRIORS: dict[GrowthHypothesis, float] = {
    GrowthHypothesis.H0: 0.10,
    GrowthHypothesis.H1: 0.20,
    GrowthHypothesis.H2: 0.30,
    GrowthHypothesis.H3: 0.22,
    GrowthHypothesis.H4: 0.13,
    GrowthHypothesis.H5: 0.05,
}


REGIME_GROWTH_ESTIMATES: dict[GrowthHypothesis, float] = {
    GrowthHypothesis.H0: -0.05,
    GrowthHypothesis.H1: 0.04,
    GrowthHypothesis.H2: 0.10,
    GrowthHypothesis.H3: 0.18,
    GrowthHypothesis.H4: 0.28,
    GrowthHypothesis.H5: 0.38,
}


def _normalize(probabilities: dict[GrowthHypothesis, float]) -> dict[GrowthHypothesis, float]:
    total = sum(probabilities.values())
    if total <= 0:
        raise ValueError("Probability total must be positive.")
    return {hypothesis: value / total for hypothesis, value in probabilities.items()}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _tilt_high_growth(
    likelihoods: dict[GrowthHypothesis, float],
    strength: float,
    high_growth_bias: float,
) -> None:
    """Apply a smooth tilt toward higher or lower growth regimes."""

    weights = {
        GrowthHypothesis.H0: -1.00,
        GrowthHypothesis.H1: -0.60,
        GrowthHypothesis.H2: -0.15,
        GrowthHypothesis.H3: 0.35,
        GrowthHypothesis.H4: 0.75,
        GrowthHypothesis.H5: 1.00,
    }
    for hypothesis, weight in weights.items():
        likelihoods[hypothesis] *= max(0.05, 1 + strength * high_growth_bias * weight)


def _apply_fundamental_evidence(
    likelihoods: dict[GrowthHypothesis, float],
    inputs: BayesianGrowthInput,
) -> None:
    revenue_signal = _clamp(inputs.revenue_growth / 0.30, -1.0, 1.5)
    _tilt_high_growth(likelihoods, strength=0.55, high_growth_bias=revenue_signal)

    margin_signal = _clamp(
        (
            inputs.gross_margin_trend
            + inputs.operating_margin_trend
            + inputs.free_cash_flow_trend
        )
        / 0.15,
        -1.0,
        1.0,
    )
    _tilt_high_growth(likelihoods, strength=0.25, high_growth_bias=margin_signal)

    backlog_signal = _clamp(inputs.backlog_or_rpo_growth / 0.35, -1.0, 1.3)
    _tilt_high_growth(likelihoods, strength=0.35, high_growth_bias=backlog_signal)

    revision_signal = _clamp(inputs.estimate_revisions / 0.20, -1.0, 1.0)
    _tilt_high_growth(likelihoods, strength=0.30, high_growth_bias=revision_signal)


def _apply_contract_and_market_evidence(
    likelihoods: dict[GrowthHypothesis, float],
    inputs: BayesianGrowthInput,
) -> None:
    contract_signal = _clamp(inputs.signed_customer_contracts / 5.0, 0.0, 1.2)
    _tilt_high_growth(likelihoods, strength=0.55, high_growth_bias=contract_signal)

    partnership_signal = _clamp(inputs.vague_partnerships / 10.0, 0.0, 0.3)
    _tilt_high_growth(likelihoods, strength=0.10, high_growth_bias=partnership_signal)

    rumor_signal = _clamp(inputs.rumor_intensity, 0.0, 1.0)
    _tilt_high_growth(likelihoods, strength=0.04, high_growth_bias=rumor_signal)

    ai_signal = _clamp(inputs.ai_market_exposure, 0.0, 1.0)
    hyperscaler_signal = _clamp(inputs.hyperscaler_capex_exposure, 0.0, 1.0)
    _tilt_high_growth(likelihoods, strength=0.22, high_growth_bias=ai_signal)
    _tilt_high_growth(likelihoods, strength=0.18, high_growth_bias=hyperscaler_signal)


def _fomo_risk_score(inputs: BayesianGrowthInput) -> float:
    price_fundamental_gap = inputs.stock_price_performance - inputs.fundamental_performance
    price_without_revisions = max(0.0, inputs.stock_price_performance) * max(
        0.0,
        -inputs.estimate_revisions,
    )

    score = 0.0
    score += _clamp(price_fundamental_gap / 0.60, 0.0, 1.0) * 65.0
    score += _clamp(price_without_revisions / 0.10, 0.0, 1.0) * 20.0
    score += _clamp(inputs.rumor_intensity, 0.0, 1.0) * 15.0
    score += _clamp(inputs.valuation_premium / 1.5, 0.0, 1.0) * 25.0
    if inputs.market_implied_growth > inputs.fundamental_performance and inputs.estimate_revisions <= 0:
        score += _clamp((inputs.market_implied_growth - inputs.fundamental_performance) / 0.20, 0.0, 1.0) * 20.0
    return round(_clamp(score, 0.0, 100.0), 1)


def _intrinsic_growth_estimate(
    updated_probabilities: dict[GrowthHypothesis, float],
) -> float:
    return sum(
        updated_probabilities[hypothesis] * REGIME_GROWTH_ESTIMATES[hypothesis]
        for hypothesis in GrowthHypothesis
    )


def _market_implied_comparison(intrinsic_growth: float, market_implied_growth: float) -> str:
    gap = market_implied_growth - intrinsic_growth
    if gap > 0.05:
        return "Market-implied growth is above the Bayesian intrinsic estimate."
    if gap < -0.05:
        return "Market-implied growth is below the Bayesian intrinsic estimate."
    return "Market-implied growth is broadly aligned with the Bayesian intrinsic estimate."


def _plain_english_explanation(
    inputs: BayesianGrowthInput,
    result_regime: GrowthHypothesis,
    fomo_risk_score: float,
) -> str:
    evidence_terms: list[str] = []
    if inputs.revenue_growth != 0:
        evidence_terms.append("revenue growth")
    if (
        inputs.gross_margin_trend != 0
        or inputs.operating_margin_trend != 0
        or inputs.free_cash_flow_trend != 0
    ):
        evidence_terms.append("margin and free-cash-flow trends")
    if inputs.backlog_or_rpo_growth != 0:
        evidence_terms.append("backlog/RPO growth")
    if inputs.signed_customer_contracts > 0:
        evidence_terms.append("signed customer contracts")
    if inputs.estimate_revisions != 0:
        evidence_terms.append("estimate revisions")
    if inputs.ai_market_exposure > 0:
        evidence_terms.append("AI market exposure")
    if inputs.hyperscaler_capex_exposure > 0:
        evidence_terms.append("hyperscaler capex exposure")

    evidence_text = (
        ", ".join(evidence_terms)
        if evidence_terms
        else "the provided model inputs"
    )
    explanations = [
        f"Most likely regime is {result_regime.value}.",
        f"Bayesian-style updates are driven by {evidence_text}.",
    ]

    if inputs.signed_customer_contracts > 0:
        explanations.append(
            "Signed customer contracts receive higher weight than vague partnerships because they are stronger evidence of future demand."
        )
    if inputs.vague_partnerships > 0 or inputs.rumor_intensity > 0:
        explanations.append(
            "Vague partnerships and rumors receive low weight and do not materially lift intrinsic growth on their own."
        )
    if inputs.stock_price_performance > inputs.fundamental_performance:
        explanations.append(
            "Stock-price momentum by itself does not raise intrinsic growth probability; when price outruns fundamentals, FOMO risk increases instead."
        )
    if inputs.valuation_premium > 0 or (
        inputs.market_implied_growth > inputs.fundamental_performance
        and inputs.estimate_revisions <= 0
    ):
        explanations.append(
            "FOMO risk also reflects valuation premium and market-implied growth that is not yet supported by structured estimate revisions."
        )
    explanations.append(f"Current FOMO risk score is {fomo_risk_score:.1f}/100.")
    return " ".join(explanations)


def estimate_intrinsic_growth(
    inputs: BayesianGrowthInput,
    priors: dict[GrowthHypothesis, float] | None = None,
) -> BayesianGrowthResult:
    """Estimate a 3-5 year intrinsic growth profile with Bayesian-style updates."""

    prior_probabilities = _normalize(priors or DEFAULT_PRIORS)
    likelihoods = {hypothesis: 1.0 for hypothesis in GrowthHypothesis}

    _apply_fundamental_evidence(likelihoods, inputs)
    _apply_contract_and_market_evidence(likelihoods, inputs)

    unnormalized_posteriors = {
        hypothesis: prior_probabilities[hypothesis] * likelihoods[hypothesis]
        for hypothesis in GrowthHypothesis
    }
    updated_probabilities = _normalize(unnormalized_posteriors)
    most_likely_regime = max(
        updated_probabilities,
        key=lambda hypothesis: updated_probabilities[hypothesis],
    )
    intrinsic_growth = _intrinsic_growth_estimate(updated_probabilities)
    fomo_score = _fomo_risk_score(inputs)

    return BayesianGrowthResult(
        prior_probabilities=prior_probabilities,
        updated_probabilities=updated_probabilities,
        most_likely_regime=most_likely_regime,
        intrinsic_growth_estimate=intrinsic_growth,
        market_implied_growth=inputs.market_implied_growth,
        market_implied_comparison=_market_implied_comparison(
            intrinsic_growth,
            inputs.market_implied_growth,
        ),
        fomo_risk_score=fomo_score,
        explanation=_plain_english_explanation(inputs, most_likely_regime, fomo_score),
    )
