"""Research journal helpers for post-event learning loops."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_JOURNAL_PATH = Path("outputs/research_journal.md")

JOURNAL_HEADER = """# Research Journal

This journal records post-event reviews for company research memos. Use it after
earnings, major product announcements, regulatory events, financing updates, or
other thesis-relevant developments.

Purpose:

- Compare the agent's prior view against actual outcomes.
- Separate assumptions from results.
- Identify recurring blind spots in valuation, growth, risk, and timing work.
- Improve future memo prompts, evidence weighting, and monitoring indicators.

## Entries
"""


@dataclass(frozen=True)
class ResearchJournalEntry:
    """Structured record of a post-event research review."""

    ticker: str
    agent_view: str
    key_assumptions: Sequence[str]
    expected_catalyst: str
    actual_result: str
    got_right: Sequence[str]
    got_wrong: Sequence[str]
    lesson_for_future_analysis: str
    event_date: date = field(default_factory=date.today)

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("ticker is required")
        if not self.agent_view.strip():
            raise ValueError("agent_view is required")
        if not self.actual_result.strip():
            raise ValueError("actual_result is required")
        if not self.lesson_for_future_analysis.strip():
            raise ValueError("lesson_for_future_analysis is required")


def ensure_research_journal(path: Path | str = DEFAULT_JOURNAL_PATH) -> Path:
    """Create the journal with an explanatory header if it does not exist."""

    journal_path = Path(path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    if not journal_path.exists():
        journal_path.write_text(JOURNAL_HEADER.rstrip() + "\n", encoding="utf-8")
    return journal_path


def render_journal_entry(entry: ResearchJournalEntry) -> str:
    """Render one journal entry as Markdown."""

    ticker = entry.ticker.strip().upper()
    return "\n".join(
        [
            "",
            f"### {entry.event_date.isoformat()} - {ticker}",
            "",
            f"- **Date:** {entry.event_date.isoformat()}",
            f"- **Ticker:** {ticker}",
            f"- **Agent view:** {entry.agent_view.strip()}",
            "- **Key assumptions:**",
            _render_bullets(entry.key_assumptions),
            f"- **Expected catalyst:** {entry.expected_catalyst.strip()}",
            f"- **Actual result:** {entry.actual_result.strip()}",
            "- **What the agent got right:**",
            _render_bullets(entry.got_right),
            "- **What the agent got wrong:**",
            _render_bullets(entry.got_wrong),
            f"- **Lesson for future analysis:** {entry.lesson_for_future_analysis.strip()}",
            "",
        ]
    )


def update_journal_after_event(
    entry: ResearchJournalEntry,
    path: Path | str = DEFAULT_JOURNAL_PATH,
) -> Path:
    """Append a post-earnings or major-event review to the research journal."""

    journal_path = ensure_research_journal(path)
    with journal_path.open("a", encoding="utf-8") as journal:
        journal.write(render_journal_entry(entry))
    return journal_path


def create_journal_entry(
    *,
    ticker: str,
    agent_view: str,
    key_assumptions: Iterable[str],
    expected_catalyst: str,
    actual_result: str,
    got_right: Iterable[str],
    got_wrong: Iterable[str],
    lesson_for_future_analysis: str,
    event_date: date | None = None,
) -> ResearchJournalEntry:
    """Convenience factory for creating a validated journal entry."""

    return ResearchJournalEntry(
        ticker=ticker,
        agent_view=agent_view,
        key_assumptions=tuple(key_assumptions),
        expected_catalyst=expected_catalyst,
        actual_result=actual_result,
        got_right=tuple(got_right),
        got_wrong=tuple(got_wrong),
        lesson_for_future_analysis=lesson_for_future_analysis,
        event_date=event_date or date.today(),
    )


def _render_bullets(items: Sequence[str]) -> str:
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return "  - Not recorded."
    return "\n".join(f"  - {item}" for item in cleaned)
