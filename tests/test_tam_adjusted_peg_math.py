"""Deterministic TAM-adjusted PEG math tests."""

from __future__ import annotations

import unittest

from src.data.models import EvidenceItem
from src.research.evidence_layers import MODEL_SCORED, model_eps_growth_assumption
from src.research.tam_adjusted_peg import (
    TamAdjustedPegInput,
    calculate_tam_adjusted_peg,
    quality_adjustment,
    risk_penalty_adjustment,
    tam_runway_adjustment,
    traditional_peg,
)


class TamAdjustedPegMathTests(unittest.TestCase):
    def test_traditional_peg_uses_growth_percentage_points(self) -> None:
        self.assertEqual(traditional_peg(20, 0.25), 0.8)

    def test_tam_and_quality_adjustments_reduce_peg_for_high_scores(self) -> None:
        self.assertLess(tam_runway_adjustment(5), 1.0)
        self.assertLess(quality_adjustment(5), 1.0)

    def test_risk_penalties_increase_peg(self) -> None:
        self.assertGreater(risk_penalty_adjustment(5, 5, 5), risk_penalty_adjustment(1, 1, 1))

    def test_full_model_penalizes_execution_and_dilution(self) -> None:
        clean = calculate_tam_adjusted_peg(TamAdjustedPegInput(20, 0.25, 5, 5, 1, 1, 1))
        risky = calculate_tam_adjusted_peg(TamAdjustedPegInput(20, 0.25, 5, 5, 5, 5, 5))

        self.assertGreater(risky.tam_adjusted_peg, clean.tam_adjusted_peg)

    def test_unavailable_forward_eps_growth_is_labeled_model_assumption(self) -> None:
        assumption = model_eps_growth_assumption(None, None, 0.18)

        self.assertIsInstance(assumption, EvidenceItem)
        self.assertEqual(assumption.data_layer, MODEL_SCORED)
        self.assertEqual(assumption.confidence, "low")
        self.assertIn("Low confidence", assumption.warning)


if __name__ == "__main__":
    unittest.main()
