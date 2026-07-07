"""Deterministic GF-DMA math tests."""

from __future__ import annotations

import unittest

from src.research.gf_dma_health import (
    GfDmaHealthInput,
    calculate_gf_dma_health,
    divergence_score,
    dma_trend_score,
    is_overextended,
)
from src.validation.formula_registry import calculate_formula


class GfDmaMathTests(unittest.TestCase):
    def test_moving_average_formula(self) -> None:
        self.assertEqual(calculate_formula("moving_average_n", {"closing_prices": (10, 20, 30, 40, 50), "n": 3}), 40)

    def test_divergence_formula(self) -> None:
        self.assertEqual(calculate_formula("price_dma_divergence", {"current_price": 60, "moving_average": 40}), 0.5)

    def test_overextension_flag(self) -> None:
        inputs = GfDmaHealthInput(0.20, 0.20, 0.20, 0.0, 150, 138, 128, 116, 100, 0.20, 0.30)

        self.assertTrue(is_overextended(inputs))

    def test_trend_health_score(self) -> None:
        inputs = GfDmaHealthInput(0.20, 0.20, 0.20, 0.05, 112, 108, 103, 98, 94, 0.10, 0.03)
        result = calculate_gf_dma_health(inputs)

        self.assertGreaterEqual(dma_trend_score(inputs), 65)
        self.assertGreaterEqual(divergence_score(inputs), 55)
        self.assertGreater(result.overall_gf_dma_health_score, 70)

    def test_missing_prices_make_gf_dma_unavailable_by_validation(self) -> None:
        with self.assertRaises(ValueError):
            calculate_gf_dma_health(GfDmaHealthInput(0.1, 0.1, 0.1, 0.0, 0, 1, 1, 1, 1, 0, 0))


if __name__ == "__main__":
    unittest.main()
