"""Tests for company archetype report customization."""

import re
import unittest

from src.connectors.mock_data import get_mock_company
from src.reports import render_mock_buy_side_memo


class ArchetypeProfileTests(unittest.TestCase):
    def test_nvda_uses_ai_accelerator_leader_profile(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NVDA"))

        self.assertIn("ai_accelerator_leader", report)
        self.assertIn("AI accelerator demand", report)
        self.assertIn("Gross margin durability", report)
        self.assertIn("Hyperscaler capex plans", report)
        self.assertIn("Valuation multiple compression risk", report)

    def test_asml_uses_semicap_equipment_bottleneck_profile(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("ASML"))

        self.assertIn("semicap_equipment_bottleneck", report)
        self.assertIn("backlog quality", report)
        self.assertIn("lithography monopoly-like positioning", report)
        self.assertIn("China and export-control risk", report)
        self.assertIn("Foundry and memory capex cycle", report)

    def test_nbis_uses_speculative_ai_infrastructure_profile(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NBIS"))

        self.assertIn("speculative_ai_infrastructure", report)
        self.assertIn("revenue growth", report)
        self.assertIn("AI cloud demand", report)
        self.assertIn("financing runway", report)
        self.assertIn("Speculative valuation support", report)

    def test_archetypes_create_distinct_gf_dma_outputs(self) -> None:
        nvda = render_mock_buy_side_memo(get_mock_company("NVDA"))
        asml = render_mock_buy_side_memo(get_mock_company("ASML"))
        nbis = render_mock_buy_side_memo(get_mock_company("NBIS"))

        self.assertGreater(_dashboard_gf_dma_score(nvda), _dashboard_gf_dma_score(asml))
        self.assertGreater(_dashboard_gf_dma_score(asml), _dashboard_gf_dma_score(nbis))


def _dashboard_gf_dma_score(report: str) -> float:
    match = re.search(r"\| GF-DMA health score \| ([0-9.]+)/100 \|", report)
    if match is None:
        raise AssertionError("GF-DMA dashboard score not found.")
    return float(match.group(1))


if __name__ == "__main__":
    unittest.main()
