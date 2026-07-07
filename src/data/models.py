"""Shared data models for provider-backed research data.

This module is the canonical home for normalized source-backed metric shapes.
Existing connectors may still expose compatibility aliases while imports are
gradually migrated here.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.periods import FiscalPeriod, normalize_period_label, point_in_time_period


ALLOWED_DATA_TYPES = frozenset(
    {"actual", "estimated", "model_generated", "unavailable", "fallback"}
)
ALLOWED_DATA_CONFIDENCE = frozenset({"high", "medium", "low"})

ALLOWED_SEARCH_SOURCE_TYPES = frozenset(
    {
        "primary_company_source",
        "official_regulator",
        "official_government",
        "sec_filing",
        "industry_body",
        "financial_news",
        "general_news",
        "blog",
        "social",
        "unknown",
    }
)
ALLOWED_SEARCH_CONFIDENCE = frozenset({"high", "medium", "low"})
ALLOWED_SEARCH_STATUS = frozenset(
    {"confirmed", "pending", "rumor", "opinion", "conflicting", "irrelevant"}
)


@dataclass(frozen=True)
class SourceMetric:
    """One normalized metric with source and confidence metadata."""

    value: float | str | None
    source_name: str
    source_url: str
    provider: str
    retrieved_at: str
    fiscal_period: str = ""
    period: FiscalPeriod | None = None
    data_type: str = "actual"
    confidence: str = "medium"
    note: str = ""


# Backward-compatible name used by current FMP/EODHD connector mappers.
ProviderMetric = SourceMetric


@dataclass(frozen=True)
class DataPoint:
    """One source-labeled value in a CompanyResearchDataset."""

    value: float | int | str | None
    source_name: str
    provider: str
    source_url: str
    retrieved_at: str
    as_of_date: str = ""
    fiscal_period: str = ""
    period: FiscalPeriod | None = None
    data_type: str = "actual"
    confidence: str = "medium"
    warning: str = ""

    def __post_init__(self) -> None:
        if self.data_type not in ALLOWED_DATA_TYPES:
            raise ValueError(f"Unsupported data_type: {self.data_type}")
        if self.confidence not in ALLOWED_DATA_CONFIDENCE:
            raise ValueError(f"Unsupported confidence: {self.confidence}")
        if self.period is None:
            period = (
                point_in_time_period(self.as_of_date, self.source_name)
                if self.as_of_date and not self.fiscal_period
                else normalize_period_label(
                    self.fiscal_period,
                    provider=self.source_name,
                    as_of_date=self.as_of_date,
                )
            )
            object.__setattr__(self, "period", period)


@dataclass(frozen=True)
class CompanyResearchDataset:
    """Clean source-backed dataset consumed by valuation and report layers."""

    ticker: str
    company_name: str
    market_data: dict[str, DataPoint]
    financials: dict[str, DataPoint]
    valuation: dict[str, DataPoint]
    macro: dict[str, DataPoint]
    news: tuple["SearchResult", ...]
    tracker: tuple[object, ...]
    provider_status: tuple[object, ...]
    warnings: tuple[str, ...]
    data_quality_score: float


@dataclass(frozen=True)
class SearchResult:
    """Normalized discovery/news result from the Codex AnySearch workflow.

    SearchResult is intentionally not a financial data model. It may support
    source discovery, catalysts, regulatory updates, and tracker evidence, but
    must not be used as an input for prices, OHLCV, market cap, financial
    statements, valuation multiples, or macro time series.
    """

    query: str
    title: str
    source_name: str
    url: str
    published_date: str
    retrieved_at: str
    snippet: str
    summary: str
    source_type: str
    confidence: str
    relevance_score: float
    ticker: str
    category: str
    status: str
    reason_for_classification: str

    def __post_init__(self) -> None:
        if self.source_type not in ALLOWED_SEARCH_SOURCE_TYPES:
            raise ValueError(f"Unsupported source_type: {self.source_type}")
        if self.confidence not in ALLOWED_SEARCH_CONFIDENCE:
            raise ValueError(f"Unsupported confidence: {self.confidence}")
        if self.status not in ALLOWED_SEARCH_STATUS:
            raise ValueError(f"Unsupported status: {self.status}")
        if not 0 <= float(self.relevance_score) <= 1:
            raise ValueError("relevance_score must be between 0 and 1")

    @property
    def full_text_summary(self) -> str:
        """Backward-compatible alias used by older report code."""

        return self.summary


@dataclass(frozen=True)
class EvidenceItem:
    """Classified evidence used by research models and report diagnostics."""

    name: str
    data_layer: str
    value: str
    source_name: str
    source_url: str = ""
    explanation: str = ""
    confidence: str = "low"
    warning: str = ""


@dataclass(frozen=True)
class ScoredAssumption:
    """Transparent 1-5 qualitative score with evidence and confidence."""

    name: str
    score: int
    evidence: str
    explanation: str
    confidence: str = "low"
    warning: str = ""


# Backward-compatible name used by older AnySearch connector imports.
AnySearchResult = SearchResult


__all__ = [
    "ALLOWED_DATA_CONFIDENCE",
    "ALLOWED_DATA_TYPES",
    "ALLOWED_SEARCH_CONFIDENCE",
    "ALLOWED_SEARCH_SOURCE_TYPES",
    "ALLOWED_SEARCH_STATUS",
    "AnySearchResult",
    "CompanyResearchDataset",
    "DataPoint",
    "EvidenceItem",
    "FiscalPeriod",
    "ProviderMetric",
    "ScoredAssumption",
    "SearchResult",
    "SourceMetric",
]
