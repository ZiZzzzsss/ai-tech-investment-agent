"""Tests for static HTML report generation."""

import tempfile
import unittest
from pathlib import Path

from src.connectors.mock_data import get_mock_company
from src.reports import (
    HTML_MANDATORY_SECTIONS,
    build_mock_buy_side_memo_input,
    render_html_memo,
    render_index,
)
from src.reports.html_report import _slug


class HtmlReportTests(unittest.TestCase):
    def test_html_file_is_generated(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "local_site" / "company_memos" / "NVDA.html"
            output_path.parent.mkdir(parents=True)
            output_path.write_text(html, encoding="utf-8")

            self.assertTrue(output_path.exists())
            self.assertIn("<!doctype html>", output_path.read_text(encoding="utf-8"))

    def test_html_mandatory_sections_exist(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        for section in HTML_MANDATORY_SECTIONS:
            self.assertIn(f'id="{_slug(section)}"', html)

    def test_sources_section_exists(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("ASML")))

        self.assertIn('id="sources"', html)
        self.assertIn("TODO: SEC filings", html)

    def test_data_source_status_section_exists(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn('id="data-source-status"', html)
        self.assertIn("Data Source Status", html)
        self.assertIn("Mock data", html)
        self.assertIn("source-available", html)
        self.assertIn("source-used", html)

    def test_risk_opportunity_tracker_cards_exist(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn('id="risk-and-opportunity-tracker"', html)
        self.assertIn("Risk &amp; Opportunity Tracker", html)
        self.assertIn("Industry", html)
        self.assertIn("Company-Specific", html)
        self.assertIn("Hyperscaler AI capex guidance", html)
        self.assertIn("Export controls on AI chips", html)
        self.assertIn("High Importance", html)
        self.assertIn("status-monitoring", html)
        self.assertIn("status-pending", html)
        self.assertIn("impact-positive", html)
        self.assertIn("impact-negative", html)
        self.assertIn("Next MSFT / AMZN / GOOGL / META earnings", html)

    def test_escalated_tracker_item_appears_in_dashboard(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NBIS")))

        self.assertIn("Escalated Tracker Item", html)
        self.assertIn("Financing capacity for AI cloud expansion", html)
        self.assertIn("status-escalated", html)

    def test_no_unsupported_buy_sell_language(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NBIS")))
        lowered = html.lower()

        self.assertNotIn("recommend buy", lowered)
        self.assertNotIn("recommend sell", lowered)
        self.assertNotIn("should buy", lowered)
        self.assertNotIn("should sell", lowered)

    def test_no_external_tracking_scripts(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))
        lowered = html.lower()

        self.assertNotIn("google-analytics", lowered)
        self.assertNotIn("gtag(", lowered)
        self.assertNotIn("facebook.net", lowered)
        self.assertNotIn('script src="http', lowered)
        self.assertNotIn("analytics", lowered)
        self.assertIn('script src="../assets/app.js"', lowered)

    def test_no_external_css_links(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))
        lowered = html.lower()

        self.assertNotIn('link rel="stylesheet" href="http', lowered)
        self.assertNotIn("fonts.googleapis", lowered)
        self.assertIn('link rel="stylesheet" href="../assets/styles.css"', lowered)

    def test_index_links_to_generated_memo(self) -> None:
        html = render_index((("NVDA", "NVIDIA Corporation", "NVDA.html"),))

        self.assertIn('href="company_memos/NVDA.html"', html)
        self.assertNotIn("{filename}", html)


if __name__ == "__main__":
    unittest.main()
