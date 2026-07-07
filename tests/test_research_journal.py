"""Tests for the research journal learning loop."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.research.research_journal import (
    ResearchJournalEntry,
    ensure_research_journal,
    render_journal_entry,
    update_journal_after_event,
)


class ResearchJournalTests(unittest.TestCase):
    def test_ensure_research_journal_creates_file_with_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = ensure_research_journal(Path(tmpdir) / "research_journal.md")
            content = path.read_text(encoding="utf-8")

        self.assertIn("# Research Journal", content)
        self.assertIn("## Entries", content)
        self.assertIn("Compare the agent's prior view", content)

    def test_render_journal_entry_tracks_required_review_fields(self) -> None:
        entry = ResearchJournalEntry(
            event_date=date(2026, 7, 5),
            ticker="nvda",
            agent_view="Base case expected AI demand to remain strong but valuation risk elevated.",
            key_assumptions=("Hyperscaler capex remains resilient.", "Margins stay above cycle average."),
            expected_catalyst="Earnings release and data center revenue update.",
            actual_result="Revenue beat assumptions while forward commentary stayed supply constrained.",
            got_right=("Data center demand remained the dominant driver.",),
            got_wrong=("Underestimated gross margin durability.",),
            lesson_for_future_analysis="Give signed supply and backlog evidence more weight than broad cycle fears.",
        )

        rendered = render_journal_entry(entry)

        self.assertIn("### 2026-07-05 - NVDA", rendered)
        self.assertIn("**Agent view:**", rendered)
        self.assertIn("**Key assumptions:**", rendered)
        self.assertIn("**Expected catalyst:**", rendered)
        self.assertIn("**Actual result:**", rendered)
        self.assertIn("**What the agent got right:**", rendered)
        self.assertIn("**What the agent got wrong:**", rendered)
        self.assertIn("**Lesson for future analysis:**", rendered)

    def test_update_journal_after_event_appends_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "research_journal.md"
            entry = ResearchJournalEntry(
                event_date=date(2026, 7, 5),
                ticker="ASML",
                agent_view="Base case depended on backlog conversion and EUV demand.",
                key_assumptions=("Backlog remains supportive.",),
                expected_catalyst="Quarterly order update.",
                actual_result="Orders improved but export-control risk remained elevated.",
                got_right=("Backlog was the right monitoring variable.",),
                got_wrong=("China restriction sensitivity needed more explicit downside framing.",),
                lesson_for_future_analysis="Separate lithography monopoly quality from capex-cycle timing risk.",
            )

            update_journal_after_event(entry, path)
            content = path.read_text(encoding="utf-8")

        self.assertIn("# Research Journal", content)
        self.assertIn("### 2026-07-05 - ASML", content)
        self.assertIn("Separate lithography monopoly quality", content)


if __name__ == "__main__":
    unittest.main()
