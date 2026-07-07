"""AnySearch skill cache connector.

Python report generation cannot call Codex skills directly as an in-process API.
The supported workflow is:

1. Codex uses the installed AnySearch skill during an interactive research task.
2. Codex saves normalized results to ``outputs/source_cache/{TICKER}.json``.
3. ``run_report.py --use-source-cache`` reads that cache for discovery, news,
   catalysts, regulatory updates, and Risk & Opportunity Tracker evidence.

This module must not be used for structured prices, OHLCV, market cap,
financial statements, valuation multiples, or macro time series.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json

from src.data.models import AnySearchResult, SearchResult


DEFAULT_SOURCE_CACHE_DIR = Path("outputs/source_cache")


def search_anysearch(
    query: str,
    api_key: str = "",
    ticker: str = "",
    category: str = "source_discovery",
) -> tuple[SearchResult, ...]:
    """Return an explicit unavailable result for direct Python calls.

    The installed AnySearch capability is a Codex skill, not a project Python
    library. Keeping this function non-networked prevents accidental use of
    AnySearch as a shadow financial-data provider.
    """

    _ = api_key
    retrieved_at = datetime.now(UTC).isoformat()
    return (
        SearchResult(
            query=query,
            title="AnySearch cache not loaded",
            source_name="AnySearch Codex skill",
            url="",
            published_date="",
            retrieved_at=retrieved_at,
            snippet=(
                "Python cannot call the Codex AnySearch skill directly. Run Codex "
                "source discovery and save outputs/source_cache/{TICKER}.json, "
                "then rerun with --use-source-cache."
            ),
            summary="No source-cache result was available to this report run.",
            source_type="unknown",
            confidence="low",
            relevance_score=0.0,
            ticker=ticker.upper(),
            category=category,
            status="pending",
            reason_for_classification="Direct AnySearch skill calls are outside the project Python runtime.",
        ),
    )


def load_source_cache(
    ticker: str,
    cache_dir: Path | str = DEFAULT_SOURCE_CACHE_DIR,
) -> tuple[SearchResult, ...]:
    """Load normalized AnySearch results from a local source cache."""

    cache_path = Path(cache_dir) / f"{ticker.upper()}.json"
    if not cache_path.exists():
        return ()
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    rows = _extract_result_rows(payload)
    return tuple(normalize_search_result(row, ticker=ticker) for row in rows)


def save_source_cache(
    ticker: str,
    results: tuple[SearchResult, ...],
    cache_dir: Path | str = DEFAULT_SOURCE_CACHE_DIR,
) -> Path:
    """Save normalized results to the local source cache."""

    cache_path = Path(cache_dir) / f"{ticker.upper()}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ticker": ticker.upper(), "results": [result.__dict__ for result in results]}
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return cache_path


def normalize_search_result(row: dict[str, Any], ticker: str = "") -> SearchResult:
    """Normalize a raw AnySearch-like row into the standard SearchResult model."""

    url = str(row.get("url", ""))
    source_name = str(row.get("source_name") or row.get("source") or "")
    snippet = str(row.get("snippet", ""))
    title = str(row.get("title", ""))
    source_type, confidence, reason = classify_source(url, source_name, snippet, title)
    status = _classify_status(row, source_type, confidence, snippet, title)
    retrieved_at = str(row.get("retrieved_at") or datetime.now(UTC).isoformat())
    return SearchResult(
        query=str(row.get("query", "")),
        title=title,
        source_name=source_name or _source_name_from_url(url),
        url=url,
        published_date=str(row.get("published_date", "")),
        retrieved_at=retrieved_at,
        snippet=snippet,
        summary=str(row.get("summary") or row.get("full_text_summary") or ""),
        source_type=str(row.get("source_type") or source_type),
        confidence=str(row.get("confidence") or confidence),
        relevance_score=_normalize_relevance(row.get("relevance_score", 0.0)),
        ticker=str(row.get("ticker") or ticker).upper(),
        category=str(row.get("category", "source_discovery")),
        status=str(row.get("status") or status),
        reason_for_classification=str(row.get("reason_for_classification") or reason),
    )


def classify_source(
    url: str,
    source_name: str = "",
    snippet: str = "",
    title: str = "",
) -> tuple[str, str, str]:
    """Classify AnySearch-derived source quality."""

    lowered = f"{url} {source_name} {snippet} {title}".lower()
    if "sec.gov" in lowered:
        return "sec_filing", "high", "SEC filing or SEC-hosted source."
    if any(token in lowered for token in ("investor.", "/investor", "ir.", "ir.")):
        return "primary_company_source", "high", "Official company investor-relations source."
    if ".gov" in lowered or "federal reserve" in lowered or "treasury" in lowered:
        return "official_government", "high", "Official government source."
    if any(token in lowered for token in ("nasaa", "sec ", "regulator", "department of commerce")):
        return "official_regulator", "high", "Official regulator source."
    if any(token in lowered for token in ("semiconductors.org", "semi.org", "wsts", "sia ", "tsmc.com")):
        return "industry_body", "high", "Industry-recognized or official industry source."
    if any(token in lowered for token in ("reuters", "bloomberg", "financial times", "wall street journal", "cnbc")):
        return "financial_news", "medium", "Reputable financial news; use as secondary support."
    if any(token in lowered for token in ("reddit", "x.com", "twitter", "social")):
        return "social", "low", "Social source; do not treat as confirmed fact."
    if any(token in lowered for token in ("blog", "substack", "rumor", "reportedly")):
        return "blog", "low", "Blog or rumor-like source; keep low confidence."
    if url:
        return "general_news", "medium", "General web source; needs primary-source confirmation."
    return "unknown", "low", "Source type is not established."


def _classify_status(
    row: dict[str, Any],
    source_type: str,
    confidence: str,
    snippet: str,
    title: str,
) -> str:
    raw_status = str(row.get("status", "")).strip().lower()
    if raw_status:
        return {
            "validated": "confirmed",
            "monitoring": "pending",
            "escalated": "pending",
            "invalidated": "irrelevant",
        }.get(raw_status, raw_status)
    lowered = f"{snippet} {title}".lower()
    if any(token in lowered for token in ("rumor", "reportedly", "unconfirmed")) or confidence == "low":
        return "rumor" if source_type in {"blog", "social", "unknown"} else "pending"
    if confidence == "high" and source_type in {
        "primary_company_source",
        "official_regulator",
        "official_government",
        "sec_filing",
        "industry_body",
    }:
        return "confirmed"
    if confidence == "medium":
        return "pending"
    return "pending"


def _extract_result_rows(payload: object) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, list):
        return tuple(row for row in payload if isinstance(row, dict))
    if not isinstance(payload, dict):
        return ()
    for key in ("results", "search_results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return tuple(row for row in value if isinstance(row, dict))
    return ()


def _source_name_from_url(url: str) -> str:
    if not url:
        return "Unknown source"
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0]


def _normalize_relevance(value: object) -> float:
    try:
        score = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score = score / 100 if score <= 100 else 1.0
    return max(0.0, min(1.0, score))


__all__ = [
    "AnySearchResult",
    "DEFAULT_SOURCE_CACHE_DIR",
    "SearchResult",
    "classify_source",
    "load_source_cache",
    "normalize_search_result",
    "save_source_cache",
    "search_anysearch",
]
