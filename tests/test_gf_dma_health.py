"""Tests for GF-DMA health index."""

import unittest

from src.research import (
    DETERIORATING,
    HEALTHY_SUPPORTED,
    SPECULATIVE_MOMENTUM,
    STRONG_EXTENDED,
    GfDmaHealthInput,
    calculate_gf_dma_health,
)


class GfDmaHealthTests(unittest.TestCase):
    def test_healthy_trend_case(self) -> None:
        result = calculate_gf_dma_health(
            GfDmaHealthInput(
                revenue_growth=0.22,
                eps_growth=0.26,
                fcf_growth=0.24,
                estimate_revision_trend=0.08,
                current_price=112.0,
                dma_20=108.0,
                dma_50=103.0,
                dma_100=98.0,
                dma_200=94.0,
                relative_strength_vs_sector=0.10,
                valuation_multiple_expansion=0.03,
            )
        )

        self.assertEqual(result.interpretation, HEALTHY_SUPPORTED)
        self.assertFalse(result.overextension_risk)
        self.assertGreaterEqual(result.overall_gf_dma_health_score, 70.0)

    def test_overextended_price_case(self) -> None:
        result = calculate_gf_dma_health(
            GfDmaHealthInput(
                revenue_growth=0.24,
                eps_growth=0.25,
                fcf_growth=0.22,
                estimate_revision_trend=0.00,
                current_price=150.0,
                dma_20=138.0,
                dma_50=128.0,
                dma_100=116.0,
                dma_200=100.0,
                relative_strength_vs_sector=0.25,
                valuation_multiple_expansion=0.35,
            )
        )

        self.assertEqual(result.interpretation, STRONG_EXTENDED)
        self.assertTrue(result.overextension_risk)
        self.assertGreater(result.escape_ratio, 1.25)

    def test_weak_fundamentals_with_strong_price_momentum(self) -> None:
        result = calculate_gf_dma_health(
            GfDmaHealthInput(
                revenue_growth=-0.05,
                eps_growth=-0.12,
                fcf_growth=-0.08,
                estimate_revision_trend=-0.02,
                current_price=130.0,
                dma_20=122.0,
                dma_50=115.0,
                dma_100=108.0,
                dma_200=101.0,
                relative_strength_vs_sector=0.18,
                valuation_multiple_expansion=0.40,
            )
        )

        self.assertEqual(result.interpretation, SPECULATIVE_MOMENTUM)
        self.assertLess(result.fundamental_growth_score, 45.0)
        self.assertGreaterEqual(result.dma_trend_score, 65.0)

    def test_trend_breakdown_case(self) -> None:
        result = calculate_gf_dma_health(
            GfDmaHealthInput(
                revenue_growth=-0.03,
                eps_growth=-0.10,
                fcf_growth=-0.06,
                estimate_revision_trend=-0.08,
                current_price=82.0,
                dma_20=88.0,
                dma_50=94.0,
                dma_100=101.0,
                dma_200=110.0,
                relative_strength_vs_sector=-0.12,
                valuation_multiple_expansion=-0.10,
            )
        )

        self.assertEqual(result.interpretation, DETERIORATING)
        self.assertLess(result.dma_trend_score, 45.0)
        self.assertLess(result.estimate_revision_score, 45.0)

    def test_strong_fundamentals_with_mixed_dma_is_not_deteriorating(self) -> None:
        result = calculate_gf_dma_health(
            GfDmaHealthInput(
                revenue_growth=0.60,
                eps_growth=0.40,
                fcf_growth=-0.20,
                estimate_revision_trend=0.00,
                current_price=195.0,
                dma_20=202.0,
                dma_50=209.0,
                dma_100=197.0,
                dma_200=191.0,
                relative_strength_vs_sector=0.02,
                valuation_multiple_expansion=0.15,
            )
        )

        self.assertEqual(result.interpretation, HEALTHY_SUPPORTED)
        self.assertFalse(result.overextension_risk)


if __name__ == "__main__":
    unittest.main()
