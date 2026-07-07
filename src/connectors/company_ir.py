"""Company investor-relations source connector.

TODO: Add permitted retrieval of official IR pages, earnings releases,
presentations, annual reports, quarterly reports, and 8-K exhibits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


UNAVAILABLE = "Not available from current sources"


@dataclass(frozen=True)
class CompanyIrSource:
    title: str
    url: str
    source_type: str
    date: str
    confidence: str


@dataclass(frozen=True)
class CompanyIrResult:
    ticker: str
    sources: tuple[CompanyIrSource, ...]
    confirmed_guidance: str
    backlog_or_rpo_commentary: str
    product_or_customer_announcements: str
    management_commentary: str
    retrieved_at: str
    warning: str = ""


def fetch_company_ir_sources(
    ticker: str,
    official_urls: tuple[str, ...] = (),
) -> CompanyIrResult:
    """List configured official IR sources for a ticker."""

    sources = tuple(
        CompanyIrSource(
            title=f"{ticker.upper()} official investor relations",
            url=url,
            source_type="primary_company_source",
            date="",
            confidence="medium",
        )
        for url in official_urls
    )
    warning = "" if sources else "Official IR URLs are not configured; company IR data is unavailable."
    return CompanyIrResult(
        ticker=ticker.upper(),
        sources=sources,
        confirmed_guidance=UNAVAILABLE,
        backlog_or_rpo_commentary=UNAVAILABLE,
        product_or_customer_announcements=UNAVAILABLE,
        management_commentary=UNAVAILABLE,
        retrieved_at=datetime.now(UTC).isoformat(),
        warning=warning,
    )
