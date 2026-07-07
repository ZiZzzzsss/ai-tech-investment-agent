"""Deterministic Bayesian growth math tests."""

from __future__ import annotations

import unittest

from src.research import BayesianGrowthInput, GrowthHypothesis, estimate_intrinsic_growth


class BayesianGrowthMathTests(unittest.TestCase):
    def test_probabilities_sum_to_one(self) -> None:
        result = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.20,
                gross_margin_trend=0.02,
                operating_margin_trend=0.02,
                free_cash_flow_trend=0.01,
                backlog_or_rpo_growth=0.10,
                signed_customer_contracts=1,
            )
        )

        self.assertAlmostEqual(sum(result.updated_probabilities.values()), 1.0)

    def test_positive_evidence_increases_high_growth_hypotheses(self) -> None:
        baseline = estimate_intrinsic_growth(
            BayesianGrowthInput(0.02, 0, 0, 0, 0, 0)
        )
        positive = estimate_intrinsic_growth(
            BayesianGrowthInput(0.35, 0.05, 0.05, 0.04, 0.30, 3, ai_market_exposure=0.80)
        )

        high_growth = (GrowthHypothesis.H3, GrowthHypothesis.H4, GrowthHypothesis.H5)
        self.assertGreater(
            sum(positive.updated_probabilities[item] for item in high_growth),
            sum(baseline.updated_probabilities[item] for item in high_growth),
        )

    def test_price_momentum_increases_fomo_not_intrinsic_growth(self) -> None:
        baseline = estimate_intrinsic_growth(BayesianGrowthInput(0.08, 0, 0, 0, 0, 0))
        price_only = estimate_intrinsic_growth(
            BayesianGrowthInput(
                0.08,
                0,
                0,
                0,
                0,
                0,
                stock_price_performance=0.60,
                fundamental_performance=0.05,
                market_implied_growth=0.30,
                valuation_premium=1.0,
            )
        )

        self.assertAlmostEqual(price_only.intrinsic_growth_estimate, baseline.intrinsic_growth_estimate)
        self.assertGreater(price_only.fomo_risk_score, baseline.fomo_risk_score)

    def test_rumor_has_low_weight(self) -> None:
        baseline = estimate_intrinsic_growth(BayesianGrowthInput(0.05, 0, 0, 0, 0, 0))
        rumor = estimate_intrinsic_growth(
            BayesianGrowthInput(0.05, 0, 0, 0, 0, 0, vague_partnerships=8, rumor_intensity=1.0)
        )

        self.assertLess(rumor.intrinsic_growth_estimate - baseline.intrinsic_growth_estimate, 0.015)


if __name__ == "__main__":
    unittest.main()
