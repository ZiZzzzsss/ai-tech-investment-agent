"""Tests for TAM-adjusted PEG analysis."""

import unittest

from src.research import (
    TamAdjustedPegInput,
    calculate_tam_adjusted_peg,
    quality_adjustment,
    risk_penalty_adjustment,
    tam_runway_adjustment,
    traditional_peg,
)


class TamAdjustedPegTests(unittest.TestCase):
    def test_traditional_peg_calculation(self) -> None:
        self.assertEqual(traditional_peg(pe_ratio=30.0, expected_eps_growth=0.20), 1.5)

    def test_tam_adjustment_reduces_peg_for_large_tam_runway(self) -> None:
        neutral_adjustment = tam_runway_adjustment(3)
        strong_tam_adjustment = tam_runway_adjustment(5)

        self.assertEqual(neutral_adjustment, 1.0)
        self.assertLess(strong_tam_adjustment, neutral_adjustment)

    def test_quality_adjustment_reduces_peg_for_high_quality_business(self) -> None:
        neutral_quality = quality_adjustment(3)
        high_quality = quality_adjustment(5)

        self.assertEqual(neutral_quality, 1.0)
        self.assertLess(high_quality, neutral_quality)

    def test_penalty_for_dilution_and_cyclicality(self) -> None:
        low_risk_penalty = risk_penalty_adjustment(
            cyclicality_score=1,
            dilution_risk_score=1,
            execution_risk_score=1,
        )
        high_risk_penalty = risk_penalty_adjustment(
            cyclicality_score=5,
            dilution_risk_score=5,
            execution_risk_score=3,
        )

        self.assertEqual(low_risk_penalty, 1.0)
        self.assertGreater(high_risk_penalty, low_risk_penalty)

    def test_full_tam_adjusted_peg_penalizes_risk(self) -> None:
        low_risk = calculate_tam_adjusted_peg(
            TamAdjustedPegInput(
                pe_ratio=40.0,
                expected_eps_growth=0.25,
                tam_score=4,
                business_quality_score=4,
                cyclicality_score=1,
                dilution_risk_score=1,
                execution_risk_score=1,
            )
        )
        high_risk = calculate_tam_adjusted_peg(
            TamAdjustedPegInput(
                pe_ratio=40.0,
                expected_eps_growth=0.25,
                tam_score=4,
                business_quality_score=4,
                cyclicality_score=5,
                dilution_risk_score=5,
                execution_risk_score=5,
            )
        )

        self.assertGreater(high_risk.tam_adjusted_peg, low_risk.tam_adjusted_peg)
        self.assertEqual(low_risk.traditional_peg, high_risk.traditional_peg)


if __name__ == "__main__":
    unittest.main()
