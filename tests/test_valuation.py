"""Tests for mock valuation calculations."""

import unittest

from src.connectors.mock_data import GfDmaHealthView, Scenario
from src.valuation import gf_dma_average_score, scenario_weighted_value, tam_adjusted_peg


class ValuationCalculationTests(unittest.TestCase):
    def test_scenario_weighted_value_normalizes_probabilities(self) -> None:
        scenarios = (
            Scenario("Bear", 1.0, 10.0, 8.0, 50.0, 2.0, "Mock"),
            Scenario("Bull", 2.0, 20.0, 12.0, 100.0, 2.0, "Mock"),
        )

        self.assertEqual(scenario_weighted_value(scenarios), 75.0)

    def test_tam_adjusted_peg_applies_discount(self) -> None:
        self.assertEqual(tam_adjusted_peg(2.0, 0.25), 1.5)

    def test_gf_dma_average_score(self) -> None:
        scorecard = GfDmaHealthView(
            growth=8,
            financial_quality=9,
            demand_momentum=7,
            moat_durability=8,
            ai_execution=6,
            trend="Stable",
            confidence="Mock",
        )

        self.assertEqual(gf_dma_average_score(scorecard), 7.6)


if __name__ == "__main__":
    unittest.main()
