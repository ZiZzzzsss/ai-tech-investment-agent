"""Tests for evidence classification and scoring layers."""

from __future__ import annotations

import unittest

from src.data.models import SearchResult
from src.research.evidence_layers import (
    build_growth_trend_evidence,
    build_scoring_rubric,
    calculate_fcf_trend,
    calculate_margin_trend,
    calculate_revenue_growth_trend,
    extract_filing_evidence,
    hyperscaler_capex_evidence_from_source_cache,
)


class EvidenceLayerTests(unittest.TestCase):
    def test_revenue_growth_trend_from_quarterly_data(self) -> None:
        self.assertAlmostEqual(calculate_revenue_growth_trend((100, 120, 150)), 0.50)

    def test_gross_margin_trend_calculation(self) -> None:
        self.assertAlmostEqual(calculate_margin_trend((100, 200), (50, 130)), 0.15)

    def test_fcf_trend_calculation(self) -> None:
        self.assertAlmostEqual(calculate_fcf_trend((100, 180), (20, 30)), 0.875)

    def test_rpo_backlog_keyword_extraction_from_filing_text(self) -> None:
        text = "Remaining performance obligations increased, and purchase obligations include long-term supply commitments."
        evidence = extract_filing_evidence(text, "10-Q")

        names = {item.name for item in evidence}
        self.assertIn("remaining performance obligations", names)
        self.assertIn("purchase obligations", names)

    def test_hyperscaler_capex_evidence_from_source_cache(self) -> None:
        result = _search_result(
            title="Microsoft AI infrastructure capex update",
            summary="Microsoft discusses AI infrastructure capital expenditure for cloud capacity.",
            source_type="sec_filing",
            confidence="high",
        )

        evidence = hyperscaler_capex_evidence_from_source_cache((result,))

        self.assertEqual(evidence[0].name, "Hyperscaler capex evidence")
        self.assertEqual(evidence[0].confidence, "high")

    def test_qualitative_score_generation_with_evidence(self) -> None:
        trend = build_growth_trend_evidence((100, 140), (60, 90), (40, 65), (50, 80), (10, 15))
        filing = extract_filing_evidence("AI infrastructure platform supply constraints and software services revenue.")

        scores = build_scoring_rubric("NVDA", trend, filing, ())

        score_map = {score.name: score for score in scores}
        self.assertGreaterEqual(score_map["TAM/SAM runway score"].score, 4)
        self.assertGreaterEqual(score_map["Moat score"].score, 4)

    def test_low_confidence_scoring_when_evidence_is_incomplete(self) -> None:
        trend = build_growth_trend_evidence((), (), (), (), ())
        scores = build_scoring_rubric("AMD", trend, (), ())

        self.assertTrue(any(score.confidence == "low" for score in scores))
        self.assertTrue(any(score.warning for score in scores))

    def test_anysearch_result_is_not_financial_number_source(self) -> None:
        result = _search_result(title="NVDA price and valuation rumor", summary="Blog says price target changed.", source_type="blog", confidence="low")
        evidence = hyperscaler_capex_evidence_from_source_cache((result,))

        self.assertEqual(evidence, ())


def _search_result(
    title: str,
    summary: str,
    source_type: str,
    confidence: str,
) -> SearchResult:
    return SearchResult(
        query="test",
        title=title,
        source_name="Test source",
        url="https://example.com",
        published_date="2026-07-01",
        retrieved_at="2026-07-07T00:00:00Z",
        snippet=summary,
        summary=summary,
        source_type=source_type,
        confidence=confidence,
        relevance_score=0.8,
        ticker="NVDA",
        category="industry",
        status="confirmed" if confidence == "high" else "rumor",
        reason_for_classification="test fixture",
    )


if __name__ == "__main__":
    unittest.main()
