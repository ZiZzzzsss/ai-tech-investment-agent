"""Tests for Bayesian-style intrinsic growth estimation."""

import unittest

from src.research import BayesianGrowthInput, GrowthHypothesis, estimate_intrinsic_growth


HIGH_GROWTH_REGIMES = (
    GrowthHypothesis.H3,
    GrowthHypothesis.H4,
    GrowthHypothesis.H5,
)


def high_growth_probability(result) -> float:
    return sum(result.updated_probabilities[hypothesis] for hypothesis in HIGH_GROWTH_REGIMES)


class BayesianGrowthTests(unittest.TestCase):
    def test_confirmed_revenue_evidence_increases_higher_growth_probabilities(self) -> None:
        weak_evidence = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.02,
                gross_margin_trend=0.00,
                operating_margin_trend=0.00,
                free_cash_flow_trend=0.00,
                backlog_or_rpo_growth=0.00,
                signed_customer_contracts=0,
                estimate_revisions=0.00,
                ai_market_exposure=0.20,
                market_implied_growth=0.08,
            )
        )
        confirmed_evidence = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.32,
                gross_margin_trend=0.03,
                operating_margin_trend=0.04,
                free_cash_flow_trend=0.03,
                backlog_or_rpo_growth=0.40,
                signed_customer_contracts=4,
                estimate_revisions=0.12,
                ai_market_exposure=0.85,
                hyperscaler_capex_exposure=0.70,
                market_implied_growth=0.18,
            )
        )

        self.assertGreater(
            high_growth_probability(confirmed_evidence),
            high_growth_probability(weak_evidence),
        )
        self.assertIn(
            confirmed_evidence.most_likely_regime,
            (GrowthHypothesis.H3, GrowthHypothesis.H4),
        )

    def test_rumor_only_evidence_does_not_materially_increase_intrinsic_growth(self) -> None:
        baseline = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.05,
                gross_margin_trend=0.00,
                operating_margin_trend=0.00,
                free_cash_flow_trend=0.00,
                backlog_or_rpo_growth=0.00,
                signed_customer_contracts=0,
                market_implied_growth=0.08,
            )
        )
        rumor_only = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.05,
                gross_margin_trend=0.00,
                operating_margin_trend=0.00,
                free_cash_flow_trend=0.00,
                backlog_or_rpo_growth=0.00,
                signed_customer_contracts=0,
                vague_partnerships=5,
                rumor_intensity=1.0,
                market_implied_growth=0.08,
            )
        )

        increase = rumor_only.intrinsic_growth_estimate - baseline.intrinsic_growth_estimate
        self.assertLess(increase, 0.01)

    def test_price_increase_without_fundamental_improvement_increases_fomo_risk(self) -> None:
        baseline = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.06,
                gross_margin_trend=0.00,
                operating_margin_trend=0.00,
                free_cash_flow_trend=0.00,
                backlog_or_rpo_growth=0.00,
                signed_customer_contracts=0,
                estimate_revisions=0.00,
                stock_price_performance=0.02,
                fundamental_performance=0.02,
                market_implied_growth=0.08,
            )
        )
        price_only = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.06,
                gross_margin_trend=0.00,
                operating_margin_trend=0.00,
                free_cash_flow_trend=0.00,
                backlog_or_rpo_growth=0.00,
                signed_customer_contracts=0,
                estimate_revisions=0.00,
                stock_price_performance=0.70,
                fundamental_performance=0.03,
                market_implied_growth=0.16,
            )
        )

        self.assertGreater(price_only.fomo_risk_score, baseline.fomo_risk_score)
        self.assertAlmostEqual(
            price_only.intrinsic_growth_estimate,
            baseline.intrinsic_growth_estimate,
            places=7,
        )

    def test_valuation_premium_without_revisions_increases_fomo_risk(self) -> None:
        baseline = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.20,
                gross_margin_trend=0.02,
                operating_margin_trend=0.02,
                free_cash_flow_trend=0.00,
                backlog_or_rpo_growth=0.00,
                signed_customer_contracts=0,
                estimate_revisions=0.00,
                market_implied_growth=0.20,
                fundamental_performance=0.20,
                valuation_premium=0.0,
            )
        )
        premium_without_revisions = estimate_intrinsic_growth(
            BayesianGrowthInput(
                revenue_growth=0.20,
                gross_margin_trend=0.02,
                operating_margin_trend=0.02,
                free_cash_flow_trend=0.00,
                backlog_or_rpo_growth=0.00,
                signed_customer_contracts=0,
                estimate_revisions=0.00,
                market_implied_growth=0.38,
                fundamental_performance=0.20,
                valuation_premium=1.2,
            )
        )

        self.assertGreater(premium_without_revisions.fomo_risk_score, baseline.fomo_risk_score)
        self.assertGreater(premium_without_revisions.market_implied_growth, 0)


if __name__ == "__main__":
    unittest.main()
