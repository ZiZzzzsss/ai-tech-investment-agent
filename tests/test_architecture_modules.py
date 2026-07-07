"""Architecture smoke tests for the public module layout."""

from __future__ import annotations

import importlib
import unittest


REQUESTED_MODULES = (
    "src.config",
    "src.data.models",
    "src.data.data_hub",
    "src.data.provider_status",
    "src.data.validation",
    "src.data.source_registry",
    "src.connectors.fmp",
    "src.connectors.sec_edgar",
    "src.connectors.fred",
    "src.connectors.company_ir",
    "src.connectors.anysearch_skill",
    "src.research.source_discovery",
    "src.research.news_catalyst_monitor",
    "src.research.risk_opportunity_tracker",
    "src.research.bayesian_growth",
    "src.research.tam_adjusted_peg",
    "src.research.gf_dma_health",
    "src.valuation.multiples",
    "src.valuation.scenarios",
    "src.valuation.entry_zones",
    "src.reports.html_report",
    "src.reports.markdown_report",
)


class ArchitectureModuleTests(unittest.TestCase):
    def test_requested_architecture_modules_are_importable(self):
        for module_name in REQUESTED_MODULES:
            self.assertIsNotNone(importlib.import_module(module_name))

    def test_provider_metric_uses_canonical_data_model(self):
        from src.connectors.fmp import ProviderMetric as FmpProviderMetric
        from src.data.models import ProviderMetric

        self.assertIs(FmpProviderMetric, ProviderMetric)

    def test_provider_status_uses_canonical_data_model(self):
        from src.data.provider_router import ProviderStatus as RouterProviderStatus
        from src.data.provider_status import ProviderStatus

        self.assertIs(RouterProviderStatus, ProviderStatus)


if __name__ == "__main__":
    unittest.main()
