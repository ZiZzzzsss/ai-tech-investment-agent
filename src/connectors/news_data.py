"""Secondary news connector.

News is allowed for catalysts, source discovery, and secondary context only.
It must not be the sole source for financial statement figures or valuation
inputs.
"""

from __future__ import annotations

from src.connectors.anysearch_skill import SearchResult, search_anysearch


def fetch_recent_news(
    ticker: str,
    anysearch_api_key: str = "",
) -> tuple[SearchResult, ...]:
    """Fetch recent news through AnySearch with source classification."""

    return search_anysearch(
        query=f"{ticker.upper()} recent company developments official release primary source",
        api_key=anysearch_api_key,
        ticker=ticker,
        category="recent_news",
    )
