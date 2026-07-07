"""News and catalyst monitoring helpers."""

from __future__ import annotations

from pathlib import Path

from src.connectors.anysearch_skill import SearchResult, load_source_cache
from src.connectors.news_data import fetch_recent_news


def monitor_recent_catalysts(ticker: str, anysearch_api_key: str = ""):
    """Fetch classified recent news for catalyst monitoring."""

    return fetch_recent_news(ticker, anysearch_api_key)


def catalysts_from_source_cache(
    ticker: str,
    cache_dir: Path | str = "outputs/source_cache",
) -> tuple[SearchResult, ...]:
    """Return source-cache rows relevant to catalysts, news, or regulation."""

    allowed_categories = {
        "recent_news",
        "catalyst",
        "catalysts",
        "regulatory_update",
        "regulation",
        "risk_tracker",
        "source_discovery",
    }
    return tuple(
        result
        for result in load_source_cache(ticker, cache_dir)
        if result.category in allowed_categories and result.status != "irrelevant"
    )


__all__ = [
    "SearchResult",
    "catalysts_from_source_cache",
    "fetch_recent_news",
    "monitor_recent_catalysts",
]
