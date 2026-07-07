"""Source-discovery helpers for official releases and primary-source lookup."""

from __future__ import annotations

from pathlib import Path

from src.connectors.anysearch_skill import (
    SearchResult,
    classify_source,
    load_source_cache,
    search_anysearch,
)


def discover_official_sources(ticker: str, api_key: str = "") -> tuple[SearchResult, ...]:
    """Discover official company and filing sources without using them as financial truth."""

    return search_anysearch(
        query=f"{ticker.upper()} official investor relations SEC filing earnings release",
        api_key=api_key,
        ticker=ticker,
        category="official_source_discovery",
    )


def official_sources_from_cache(
    ticker: str,
    cache_dir: Path | str = "outputs/source_cache",
) -> tuple[SearchResult, ...]:
    """Return high-confidence official or primary sources from the local cache."""

    official_types = {
        "primary_company_source",
        "official_regulator",
        "official_government",
        "sec_filing",
        "industry_body",
    }
    return tuple(
        result
        for result in load_source_cache(ticker, cache_dir)
        if result.source_type in official_types and result.confidence == "high"
    )


__all__ = [
    "SearchResult",
    "classify_source",
    "discover_official_sources",
    "official_sources_from_cache",
    "search_anysearch",
]
