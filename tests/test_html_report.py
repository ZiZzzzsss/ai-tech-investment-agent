"""Tests for static HTML report generation."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.connectors.mock_data import get_mock_company
from src.reports import (
    HTML_MANDATORY_SECTIONS,
    build_mock_buy_side_memo_input,
    render_html_memo,
    render_index,
)
from src.reports.html_report import _slug
from src.reports.markdown_report import PeriodBasisRow


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
        self.assertIn("Risks &amp; Opportunities", html)
        self.assertIn("Risks to Watch", html)
        self.assertIn("Opportunities to Validate", html)
        self.assertIn("Mixed / Neutral Monitoring", html)
        self.assertIn("Hyperscaler AI capex guidance", html)
        self.assertIn("Export controls on AI chips", html)
        self.assertIn("High Importance", html)
        self.assertIn("status-monitoring", html)
        self.assertIn("status-pending", html)
        self.assertIn("impact-positive", html)
        self.assertIn("impact-negative", html)
        self.assertIn("Next MSFT / AMZN / GOOGL / META earnings", html)

    def test_tracker_cards_prioritize_current_status_and_insight(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn("tracker-current-grid", html)
        self.assertIn("Current status", html)
        self.assertIn("Signal readout", html)
        self.assertIn("Validation rules, source basis, and schedule", html)
        self.assertLess(html.index("Current status"), html.index("Validation rules, source basis, and schedule"))

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

    def test_decision_hierarchy_sections_exist(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        for section_id in (
            "hero",
            "executive-verdict",
            "key-metrics",
            "financial-quality",
            "valuation",
            "growth-drivers",
            "entry-framework",
            "risk-and-opportunity-tracker",
            "audit-appendix",
        ):
            self.assertIn(f'id="{section_id}"', html)
        self.assertNotIn('id="watchlist"', html)
        self.assertNotIn(">Watchlist<", html)
        self.assertNotIn('id="risks"', html)
        self.assertNotIn('id="scenario-analysis"', html)
        self.assertNotIn("Scenario analysis", html)
        self.assertNotIn('id="catalysts-and-risks"', html)
        self.assertNotIn("Catalysts and risks", html)

    def test_query_log_is_after_main_investment_sections(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertGreater(html.index('id="anysearch-query-log"'), html.index('id="risk-and-opportunity-tracker"'))
        self.assertGreater(html.index('id="data-source-status"'), html.index('id="risk-and-opportunity-tracker"'))

    def test_growth_and_tracker_use_readable_horizontal_layouts(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn("growth-driver-list", html)
        self.assertIn("tracker-split-group", html)
        self.assertIn("Signal readout", html)
        self.assertIn("Validation rules, source basis, and schedule", html)
        self.assertNotIn("This is the single home for thesis risks", html)
        self.assertIn("Read-through:", html)
        self.assertIn("Open question:", html)

    def test_key_metrics_use_plain_so_what_language(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn("<b>So what:</b>", html)
        self.assertNotIn("<b>Decision impact:</b>", html)
        self.assertIn("quality-summary-panel", html)
        self.assertIn("quality-summary-strip", html)
        self.assertNotIn("quality-summary-card", html)
        self.assertIn("Profit conversion", html)
        self.assertIn("Cash-flow caveat", html)

    def test_executive_verdict_uses_investment_insight_language(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn("verdict-insight-panel", html)
        self.assertIn("Core read", html)
        self.assertIn("Valuation tension", html)
        self.assertIn("Risk/opportunity watch", html)
        self.assertIn("latest price", html.lower())
        self.assertNotIn("Decision-ready for analyst review", html)

    def test_optional_fmp_unavailable_metrics_are_hidden(self) -> None:
        original = build_mock_buy_side_memo_input(get_mock_company("NVDA"))
        multiples = dict(original.valuation_multiples)
        multiples["Analyst EPS growth"] = "Unavailable: source does not provide this field"
        multiples["Earnings date"] = "Unavailable: source does not provide this field"
        multiples["EV/EBITDA"] = "Unavailable: ebitda missing"
        memo = replace(
            original,
            valuation_multiples=multiples,
            low_confidence_warnings=(
                "Forward EPS growth: Low confidence until FMP or another structured estimates provider supplies forward EPS growth.",
            ),
        )
        html = render_html_memo(memo)

        self.assertNotIn("Analyst EPS growth", html)
        self.assertNotIn("Earnings date", html)
        self.assertNotIn("Forward EPS growth", html)
        self.assertNotIn("structured estimates provider supplies forward EPS growth", html)
        self.assertNotIn("TAM-Adjusted PEG Assumption Table", html)
        self.assertIn("EV/EBITDA", html)
        self.assertIn("Unavailable: ebitda missing", html)

    def test_scoring_rubric_explains_how_to_read_scores(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn("Scoring Rubric Table", html)
        self.assertIn("How to read these scores", html)
        self.assertIn("turns qualitative AI-stock questions into a structured checklist", html)

    def test_model_sections_explain_how_to_use_each_method(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        self.assertIn("Why this model stack matters", html)
        self.assertIn("Use it as a thesis-confidence map", html)
        self.assertIn("What TAM-adjusted PEG checks", html)
        self.assertIn("How to use GF-DMA", html)
        self.assertIn("evidence-card-list", html)
        self.assertNotIn("<th>Evidence</th>", html)

    def test_tracker_current_status_precedes_signal_badge(self) -> None:
        html = render_html_memo(build_mock_buy_side_memo_input(get_mock_company("NVDA")))

        panel = html[html.index("tracker-current-panel tracker-current-primary") :][:600]
        self.assertLess(panel.index("Current status"), panel.index("Monitoring"))

    def test_unavailable_valuation_blocks_entry_bands(self) -> None:
        memo = replace(
            build_mock_buy_side_memo_input(get_mock_company("NVDA")),
            fair_value_per_share=0.0,
        )
        html = render_html_memo(memo)

        self.assertIn("Entry framework unavailable until valuation inputs pass audit", html)
        self.assertIn("Not decision-ready", html)
        self.assertNotIn("Expensive / wait", html)

    def test_mixed_period_warning_blocks_valuation_readiness(self) -> None:
        memo = replace(
            build_mock_buy_side_memo_input(get_mock_company("NVDA")),
            period_basis_rows=(
                PeriodBasisRow(
                    "Revenue",
                    "TTM",
                    "Mixed sources",
                    "Annual revenue only",
                    "Unavailable: revenue must be TTM for valuation multiple; got annual",
                ),
            ),
        )
        html = render_html_memo(memo)

        self.assertIn("Financial periods are inconsistent", html)
        self.assertIn("not valuation-ready", html)

    def test_decision_quality_score_is_reduced_when_valuation_is_missing(self) -> None:
        memo = replace(
            build_mock_buy_side_memo_input(get_mock_company("NVDA")),
            data_quality_score=100.0,
            fair_value_per_share=0.0,
        )
        html = render_html_memo(memo)

        self.assertIn("Decision-useful quality score", html)
        self.assertNotIn("Decision-Useful Quality</span><strong>100.0/100", html)

    def test_fallback_data_lowers_displayed_confidence(self) -> None:
        original = build_mock_buy_side_memo_input(get_mock_company("NVDA"))
        snapshot = dict(original.financial_snapshot)
        snapshot["Free cash flow"] = "1000000000 | Source: yfinance fallback | Period: TTM"
        memo = replace(original, financial_snapshot=snapshot, data_quality_score=100.0)
        html = render_html_memo(memo)

        self.assertIn("Medium", html)
        self.assertIn("fallback", html.lower())


if __name__ == "__main__":
    unittest.main()
