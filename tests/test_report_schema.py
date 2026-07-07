"""Tests for required buy-side memo report sections."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.config import AppConfig
from src.connectors.mock_data import get_mock_company
from src.reports import MANDATORY_SECTIONS, build_live_buy_side_memo_input, render_mock_buy_side_memo


class ReportSchemaTests(unittest.TestCase):
    def test_report_contains_all_mandatory_sections(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NVDA"))

        for section in MANDATORY_SECTIONS:
            self.assertIn(f"## {section}", report)

    def test_report_contains_change_table(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NVDA"))

        self.assertIn("## What changed since last review", report)
        self.assertIn("| Area | Previous review | Latest review | Plain-English change |", report)

    def test_markdown_report_contains_risk_opportunity_tracker(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NVDA"))

        self.assertIn("## Risk & Opportunity Tracker", report)
        self.assertIn("### Industry", report)
        self.assertIn("Hyperscaler AI capex guidance", report)
        self.assertIn("Evidence needed:", report)
        self.assertIn("Suggested response:", report)

    def test_report_contains_data_quality_warning_and_source_placeholders(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("AMD"))

        self.assertIn("mock data", report.lower())
        self.assertIn("TODO: SEC filings", report)
        self.assertIn("does not provide buy, sell, or hold advice", report)

    def test_entry_price_framework_is_scenario_based(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NVDA"))

        self.assertIn("Scenario anchors:", report)
        self.assertIn("Bear case", report)
        self.assertIn("Base case", report)
        self.assertIn("Bull case", report)
        self.assertIn("probability-weighted scenario fair value", report)

    def test_report_separates_facts_assumptions_estimates_and_interpretation(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NVDA"))

        self.assertIn("## Evidence Classification", report)
        self.assertIn("| Fact |", report)
        self.assertIn("| Assumption |", report)
        self.assertIn("| Estimate |", report)
        self.assertIn("| Interpretation |", report)

    def test_mock_report_does_not_claim_real_signed_contracts(self) -> None:
        report = render_mock_buy_side_memo(get_mock_company("NVDA"))

        self.assertNotIn("Signed customer contracts receive higher weight", report)
        self.assertNotIn("Confirmed revenue", report)

    def test_live_mode_does_not_silently_use_mock_data(self) -> None:
        market = SimpleNamespace(
            latest_price=None,
            price_timestamp="Unavailable: API key missing",
            source_name="Market data connector",
            source_url="",
            retrieved_at="2026-07-01",
            warning="Unavailable: API key missing",
            market_cap=None,
            moving_average_20=None,
            moving_average_50=None,
            moving_average_100=None,
            moving_average_200=None,
        )
        sec = SimpleNamespace(
            cik="",
            latest_10k=None,
            latest_10q=None,
            latest_8k=None,
            metrics={},
            source_name="SEC EDGAR",
            source_url="https://data.sec.gov/",
            retrieved_at="2026-07-01",
            warning="Unavailable: SEC_USER_AGENT missing",
        )
        macro = (
            SimpleNamespace(
                name="US 10-year treasury yield",
                latest_value=None,
                date="Unavailable: API key missing",
                source="FRED",
                warning="Unavailable: API key missing",
            ),
        )
        ir = SimpleNamespace(sources=(), warning="Unavailable: official IR URL missing")
        industry = ()
        news = ()
        provider_bundle = SimpleNamespace(
            market=market,
            sec=sec,
            financial_metrics={},
            estimates={},
            earnings_calendar={},
            macro=macro,
            ir=ir,
            industry=industry,
            news=news,
            anysearch=news,
            warnings=("Unavailable: API key missing",),
            statuses=(
                SimpleNamespace(
                    provider="FMP",
                    configured="missing",
                    used="not used",
                    availability="unavailable",
                    reason="Missing key",
                    last_successful_retrieval="none",
                ),
            ),
        )

        with patch("src.reports.markdown_report.collect_provider_data", return_value=provider_bundle):
            memo = build_live_buy_side_memo_input("NVDA", AppConfig("", "", "", "", "", "", "", ""))

        self.assertFalse(memo.is_mock)
        self.assertEqual(memo.report_mode, "live")
        self.assertEqual(memo.latest_price, 0.0)
        self.assertIn("Live mode", memo.data_quality)


if __name__ == "__main__":
    unittest.main()
