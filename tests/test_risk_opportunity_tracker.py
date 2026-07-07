"""Tests for risk and opportunity tracker loading."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.research.risk_opportunity_tracker import load_risk_opportunity_trackers
from src.research.risk_opportunity_tracker import validate_tracker_items


class RiskOpportunityTrackerTests(unittest.TestCase):
    def test_loads_tracker_items_for_ticker(self) -> None:
        yaml_text = """NVDA:
  - id: nvda_test
    ticker: NVDA
    category: industry
    event_or_indicator: Hyperscaler AI capex guidance
    why_it_matters: Demand sensitivity.
    status: monitoring
    impact_if_validated: positive
    importance: high
    frequency: quarterly
    next_check_date: Next earnings
    validation_rule: Confirm with filings.
    suggested_research_response: Raise confidence if evidence is confirmed.
    source_priority:
      - company earnings releases
      - SEC filings
    source_url: TODO
    confidence: medium
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tracker.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            items = load_risk_opportunity_trackers("nvda", path)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, "nvda_test")
        self.assertEqual(items[0].status, "monitoring")
        self.assertEqual(items[0].impact_if_validated, "positive")
        self.assertEqual(items[0].next_check_date, "Next earnings")
        self.assertEqual(items[0].source_priority, ("company earnings releases", "SEC filings"))

    def test_missing_tracker_file_returns_empty_tuple(self) -> None:
        items = load_risk_opportunity_trackers("NVDA", Path("missing_tracker.yaml"))

        self.assertEqual(items, ())

    def test_invalid_status_is_rejected(self) -> None:
        yaml_text = """NVDA:
  - id: nvda_bad
    ticker: NVDA
    category: industry
    event_or_indicator: Bad status
    why_it_matters: Validation test.
    status: watching
    impact_if_validated: positive
    importance: high
    frequency: quarterly
    next_check_date: Next release
    validation_rule: Confirm with filings.
    suggested_research_response: Wait for confirmation.
    source_priority:
      - SEC filings
    source_url: TODO
    confidence: medium
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tracker.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            with self.assertRaises(ValueError):
                load_risk_opportunity_trackers("NVDA", path)

    def test_invalid_impact_is_rejected(self) -> None:
        yaml_text = """NVDA:
  - id: nvda_bad_impact
    ticker: NVDA
    category: industry
    event_or_indicator: Bad impact
    why_it_matters: Validation test.
    status: monitoring
    impact_if_validated: excellent
    importance: high
    frequency: quarterly
    next_check_date: Next release
    validation_rule: Confirm with filings.
    suggested_research_response: Wait for confirmation.
    source_priority:
      - SEC filings
    source_url: TODO
    confidence: medium
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tracker.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            with self.assertRaises(ValueError):
                load_risk_opportunity_trackers("NVDA", path)

    def test_invalid_importance_is_rejected(self) -> None:
        yaml_text = """NVDA:
  - id: nvda_bad_importance
    ticker: NVDA
    category: industry
    event_or_indicator: Bad importance
    why_it_matters: Validation test.
    status: monitoring
    impact_if_validated: positive
    importance: urgent
    frequency: quarterly
    next_check_date: Next release
    validation_rule: Confirm with filings.
    suggested_research_response: Wait for confirmation.
    source_priority:
      - SEC filings
    source_url: TODO
    confidence: medium
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tracker.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            with self.assertRaises(ValueError):
                load_risk_opportunity_trackers("NVDA", path)

    def test_repository_tracker_values_are_valid(self) -> None:
        items = (
            load_risk_opportunity_trackers("NVDA")
            + load_risk_opportunity_trackers("AMD")
            + load_risk_opportunity_trackers("NBIS")
        )

        validate_tracker_items(items)

    def test_high_importance_items_sort_before_low_importance_in_category(self) -> None:
        yaml_text = """NVDA:
  - id: nvda_low
    ticker: NVDA
    category: industry
    event_or_indicator: Low signal
    why_it_matters: Validation test.
    status: monitoring
    impact_if_validated: neutral
    importance: low
    frequency: quarterly
    next_check_date: Next release
    validation_rule: Confirm with filings.
    suggested_research_response: Monitor next release.
    source_priority:
      - SEC filings
    source_url: TODO
    confidence: medium
  - id: nvda_high
    ticker: NVDA
    category: industry
    event_or_indicator: High signal
    why_it_matters: Validation test.
    status: monitoring
    impact_if_validated: positive
    importance: high
    frequency: quarterly
    next_check_date: Next release
    validation_rule: Confirm with filings.
    suggested_research_response: Monitor next release.
    source_priority:
      - SEC filings
    source_url: TODO
    confidence: medium
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tracker.yaml"
            path.write_text(yaml_text, encoding="utf-8")

            items = load_risk_opportunity_trackers("NVDA", path)

        self.assertEqual(items[0].id, "nvda_high")


if __name__ == "__main__":
    unittest.main()
