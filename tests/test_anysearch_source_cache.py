"""Tests for AnySearch skill source-cache workflow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from src.connectors.anysearch_skill import load_source_cache
from src.connectors.mock_data import get_mock_company
from src.data.models import SearchResult
from src.reports.html_report import render_html_memo
from src.reports.markdown_report import build_mock_buy_side_memo_input
from src.research.risk_opportunity_tracker import (
    RiskOpportunityTrackerItem,
    update_trackers_from_search_results,
)


class AnySearchSourceCacheTests(unittest.TestCase):
    def test_search_result_validation(self) -> None:
        result = SearchResult(
            query="NVDA official release",
            title="NVIDIA release",
            source_name="NVIDIA Investor Relations",
            url="https://investor.nvidia.com/",
            published_date="2026-07-01",
            retrieved_at="2026-07-06T00:00:00Z",
            snippet="Official company release.",
            summary="Official company release.",
            source_type="primary_company_source",
            confidence="high",
            relevance_score=0.9,
            ticker="NVDA",
            category="source_discovery",
            status="confirmed",
            reason_for_classification="Official company source.",
        )

        self.assertEqual(result.confidence, "high")
        with self.assertRaises(ValueError):
            replace(result, source_type="unsupported")

    def test_source_cache_reading(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "NVDA.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "query": "NVDA IR",
                                "title": "NVIDIA Investor Relations",
                                "source_name": "NVIDIA IR",
                                "url": "https://investor.nvidia.com/",
                                "published_date": "2026-07-01",
                                "snippet": "official investor relations",
                                "summary": "Official company source.",
                                "relevance_score": 0.95,
                                "ticker": "NVDA",
                                "category": "source_discovery",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            results = load_source_cache("NVDA", temp_dir)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_type, "primary_company_source")
        self.assertEqual(results[0].status, "confirmed")

    def test_tracker_update_from_high_confidence_source(self) -> None:
        tracker = _tracker("nvda_export_controls", "export controls", "pending")
        result = _result(
            title="Official export controls update",
            snippet="Export controls confirmed by official government release.",
            source_type="official_government",
            confidence="high",
            status="confirmed",
            category="regulation",
        )

        updated = update_trackers_from_search_results((tracker,), (result,))

        self.assertEqual(updated[0].status, "validated")
        self.assertEqual(updated[0].confidence, "high")
        self.assertIn("Official export controls update", updated[0].evidence_summary)

    def test_low_confidence_results_stay_pending(self) -> None:
        tracker = _tracker("nvda_hbm_supply", "HBM supply constraints", "pending")
        result = _result(
            title="Rumor about HBM supply",
            snippet="Unconfirmed rumor about HBM supply.",
            source_type="blog",
            confidence="low",
            status="rumor",
            category="industry",
        )

        updated = update_trackers_from_search_results((tracker,), (result,))

        self.assertEqual(updated[0].status, "pending")
        self.assertEqual(updated[0].confidence, "low")

    def test_generic_official_source_does_not_validate_macro_tracker(self) -> None:
        tracker = RiskOpportunityTrackerItem(
            id="nvda_us10y",
            ticker="NVDA",
            category="macro",
            event_or_indicator="US 10-year treasury yield",
            why_it_matters="Rates can pressure valuation multiples.",
            status="monitoring",
            impact_if_validated="negative",
            importance="high",
            frequency="daily",
            validation_rule="Validate through FRED or Treasury data.",
            suggested_research_response="review entry zone",
            next_check_date="Daily close",
            source_priority=("FRED", "Treasury"),
            source_url="TODO",
            confidence="medium",
        )
        result = _result(
            title="NVIDIA Announces Financial Results",
            snippet="Official NVIDIA earnings release with quarterly financial results.",
            source_type="primary_company_source",
            confidence="high",
            status="confirmed",
            category="recent_news",
        )

        updated = update_trackers_from_search_results((tracker,), (result,))

        self.assertEqual(updated[0].status, "monitoring")
        self.assertEqual(updated[0].evidence_summary, "")

    def test_official_earnings_release_can_validate_matching_company_metric(self) -> None:
        tracker = RiskOpportunityTrackerItem(
            id="nvda_datacenter_revenue_growth",
            ticker="NVDA",
            category="company-specific",
            event_or_indicator="Data-center revenue growth",
            why_it_matters="Data-center revenue is the core AI accelerator demand signal.",
            status="monitoring",
            impact_if_validated="positive",
            importance="high",
            frequency="quarterly",
            validation_rule="Validate from NVIDIA earnings release segment disclosures.",
            suggested_research_response="increase thesis confidence",
            next_check_date="Next NVIDIA earnings release",
            source_priority=("company earnings releases",),
            source_url="TODO",
            confidence="medium",
        )
        result = _result(
            title="NVIDIA Announces Financial Results",
            snippet="Official NVIDIA earnings release reports data center revenue growth.",
            source_type="primary_company_source",
            confidence="high",
            status="confirmed",
            category="recent_news",
        )

        updated = update_trackers_from_search_results((tracker,), (result,))

        self.assertEqual(updated[0].status, "validated")
        self.assertEqual(updated[0].confidence, "high")

    def test_anysearch_results_appear_in_html(self) -> None:
        company = get_mock_company("NVDA")
        result = _result(
            title="NVIDIA Investor Relations",
            snippet="Official source.",
            source_type="primary_company_source",
            confidence="high",
            status="confirmed",
            category="source_discovery",
        )
        memo = replace(
            build_mock_buy_side_memo_input(company),
            source_discovery_results=(result,),
            anysearch_query_log=("NVDA IR -> NVIDIA IR: confirmed (high, primary_company_source)",),
        )

        html = render_html_memo(memo)

        self.assertIn("Official sources discovered", html)
        self.assertIn("NVIDIA Investor Relations", html)
        self.assertIn("Primary Company Source", html)

    def test_anysearch_cache_is_not_financial_or_market_data(self) -> None:
        with TemporaryDirectory() as temp_dir:
            Path(temp_dir, "NVDA.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "query": "NVDA price",
                                "title": "Price article",
                                "source_name": "General News",
                                "url": "https://news.example.com/nvda-price",
                                "snippet": "Mentions a price.",
                                "summary": "This must not become market data.",
                                "relevance_score": 0.8,
                                "ticker": "NVDA",
                                "category": "recent_news",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            results = load_source_cache("NVDA", temp_dir)

        self.assertEqual(results[0].category, "recent_news")
        self.assertFalse(hasattr(results[0], "latest_price"))
        self.assertFalse(hasattr(results[0], "market_cap"))


def _tracker(item_id: str, event: str, status: str) -> RiskOpportunityTrackerItem:
    return RiskOpportunityTrackerItem(
        id=item_id,
        ticker="NVDA",
        category="regulation" if "export" in event else "industry",
        event_or_indicator=event,
        why_it_matters="Thesis-impacting signal.",
        status=status,
        impact_if_validated="negative",
        importance="high",
        frequency="event-driven",
        validation_rule="Validate from official source.",
        suggested_research_response="wait for confirmation",
        next_check_date="Next release",
        source_priority=("official sources",),
        source_url="TODO",
        confidence="medium",
    )


def _result(
    title: str,
    snippet: str,
    source_type: str,
    confidence: str,
    status: str,
    category: str,
) -> SearchResult:
    return SearchResult(
        query="NVDA tracker update",
        title=title,
        source_name="Source",
        url="https://source.example.com/update",
        published_date="2026-07-01",
        retrieved_at="2026-07-06T00:00:00Z",
        snippet=snippet,
        summary=snippet,
        source_type=source_type,
        confidence=confidence,
        relevance_score=0.95,
        ticker="NVDA",
        category=category,
        status=status,
        reason_for_classification="Test source classification.",
    )


if __name__ == "__main__":
    unittest.main()
