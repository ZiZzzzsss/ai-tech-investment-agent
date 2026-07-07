"""AI and semiconductor industry-data connector stubs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


UNAVAILABLE = "Not available from current sources"


@dataclass(frozen=True)
class IndustrySignal:
    indicator_name: str
    latest_signal: str
    source: str
    date: str
    frequency: str
    relevant_companies: tuple[str, ...]
    expected_impact: str
    confidence_level: str


def fetch_industry_signals(ticker: str) -> tuple[IndustrySignal, ...]:
    """Return industry signals when official/recognized sources are configured.

    TODO: Implement SIA, SEMI, WSTS, TSMC monthly revenue, hyperscaler filings,
    HBM/DRAM pricing, advanced packaging, power constraints, and export-control
    source loaders.
    """

    return (
        IndustrySignal(
            indicator_name="AI and semiconductor industry signals",
            latest_signal=UNAVAILABLE,
            source="SIA / SEMI / WSTS / TSMC / hyperscaler filings",
            date=datetime.now(UTC).date().isoformat(),
            frequency="mixed",
            relevant_companies=(ticker.upper(),),
            expected_impact="mixed",
            confidence_level="low",
        ),
    )
