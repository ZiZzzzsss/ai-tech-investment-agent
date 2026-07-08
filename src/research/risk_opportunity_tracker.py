"""Risk and opportunity tracker loading utilities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from src.data.models import SearchResult


DEFAULT_TRACKER_PATH = Path("trackers/risk_opportunity_tracker.yaml")
ALLOWED_STATUSES = frozenset(
    {"pending", "validated", "invalidated", "monitoring", "escalated"}
)
ALLOWED_IMPACTS = frozenset({"positive", "negative", "mixed", "neutral"})
ALLOWED_IMPORTANCE = frozenset({"high", "medium", "low"})
CATEGORY_ORDER = (
    "macro",
    "market index",
    "industry",
    "company-specific",
    "regulation",
    "valuation",
    "technical",
)
IMPORTANCE_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class RiskOpportunityTrackerItem:
    """Structured monitoring item for a company memo."""

    id: str
    ticker: str
    category: str
    event_or_indicator: str
    why_it_matters: str
    status: str
    impact_if_validated: str
    importance: str
    frequency: str
    validation_rule: str
    suggested_research_response: str
    next_check_date: str
    source_priority: tuple[str, ...]
    source_url: str
    confidence: str
    last_checked: str = ""
    evidence_summary: str = ""

    @property
    def next_check(self) -> str:
        """Backward-compatible alias for older report code/tests."""

        return self.next_check_date


def load_risk_opportunity_trackers(
    ticker: str,
    path: Path | str = DEFAULT_TRACKER_PATH,
) -> tuple[RiskOpportunityTrackerItem, ...]:
    """Load tracker entries for a ticker from the repository YAML file.

    TODO: Replace this minimal parser with a validated YAML schema if this file
    grows beyond simple scalar fields and one-level lists.
    """

    tracker_path = Path(path)
    if not tracker_path.exists():
        return ()
    parsed = _parse_tracker_yaml(tracker_path.read_text(encoding="utf-8"))
    items = parsed.get(ticker.strip().upper(), ())
    return sort_tracker_items(tuple(_item_from_mapping(item) for item in items))


def validate_tracker_items(items: tuple[RiskOpportunityTrackerItem, ...]) -> None:
    """Validate allowed tracker enum fields."""

    for item in items:
        if item.status not in ALLOWED_STATUSES:
            raise ValueError(f"{item.id} has unsupported status: {item.status}")
        if item.impact_if_validated not in ALLOWED_IMPACTS:
            raise ValueError(
                f"{item.id} has unsupported impact: {item.impact_if_validated}"
            )
        if item.importance not in ALLOWED_IMPORTANCE:
            raise ValueError(f"{item.id} has unsupported importance: {item.importance}")


def sort_tracker_items(
    items: tuple[RiskOpportunityTrackerItem, ...],
) -> tuple[RiskOpportunityTrackerItem, ...]:
    """Sort by category order, then importance, with escalated items first."""

    return tuple(
        sorted(
            items,
            key=lambda item: (
                0 if item.status == "escalated" else 1,
                _category_rank(item.category),
                IMPORTANCE_RANK.get(item.importance, 99),
                item.event_or_indicator.lower(),
            ),
        )
    )


def group_tracker_items_by_category(
    items: tuple[RiskOpportunityTrackerItem, ...],
) -> tuple[tuple[str, tuple[RiskOpportunityTrackerItem, ...]], ...]:
    """Group sorted tracker items by report category."""

    grouped: dict[str, list[RiskOpportunityTrackerItem]] = {}
    for item in sort_tracker_items(items):
        grouped.setdefault(item.category, []).append(item)

    return tuple(
        (category, tuple(grouped[category]))
        for category in sorted(grouped, key=_category_rank)
    )


def update_trackers_from_search_results(
    items: tuple[RiskOpportunityTrackerItem, ...],
    results: tuple[SearchResult, ...],
) -> tuple[RiskOpportunityTrackerItem, ...]:
    """Apply AnySearch cache evidence to tracker rows.

    High-confidence official or primary sources may validate a matching tracker
    item. Low-confidence, rumor, opinion, or secondary-only items keep the
    tracker pending/monitoring and only update the evidence note.
    """

    updated: list[RiskOpportunityTrackerItem] = []
    for item in items:
        match = _best_result_for_tracker(item, results)
        if match is None:
            updated.append(item)
            continue
        source_priority = item.source_priority
        if match.source_name and match.source_name not in source_priority:
            source_priority = source_priority + (match.source_name,)
        next_status = item.status
        next_confidence = item.confidence
        if _can_validate_tracker(match):
            next_status = "validated"
            next_confidence = "high"
        elif item.status == "validated":
            next_status = "validated"
        elif match.confidence == "low" or match.status in {"rumor", "opinion"}:
            next_status = "pending" if item.status in {"pending", "monitoring"} else item.status
            next_confidence = "low"
        updated.append(
            replace(
                item,
                status=next_status,
                confidence=next_confidence,
                source_priority=source_priority,
                source_url=match.url or item.source_url,
                last_checked=match.retrieved_at,
                evidence_summary=_tracker_evidence_summary(match),
            )
        )
    return sort_tracker_items(tuple(updated))


def _parse_tracker_yaml(text: str) -> dict[str, tuple[dict[str, object], ...]]:
    trackers: dict[str, list[dict[str, object]]] = {}
    current_ticker = ""
    current_item: dict[str, object] | None = None
    current_list_key = ""

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip().lstrip("\ufeff")

        if indent == 0 and line.endswith(":"):
            current_ticker = line[:-1].strip().upper()
            trackers.setdefault(current_ticker, [])
            current_item = None
            current_list_key = ""
            continue

        if indent == 2 and line.startswith("- "):
            current_item = {}
            trackers.setdefault(current_ticker, []).append(current_item)
            current_list_key = ""
            key, value = _split_key_value(line[2:])
            current_item[key] = value
            continue

        if current_item is None:
            continue

        if indent == 4:
            key, value = _split_key_value(line)
            if value == "":
                current_item[key] = []
                current_list_key = key
            else:
                current_item[key] = value
                current_list_key = ""
            continue

        if indent == 6 and line.startswith("- ") and current_list_key:
            values = current_item.setdefault(current_list_key, [])
            if isinstance(values, list):
                values.append(line[2:].strip())

    return {ticker: tuple(items) for ticker, items in trackers.items()}


def _split_key_value(line: str) -> tuple[str, str]:
    key, separator, value = line.partition(":")
    if not separator:
        return key.strip(), ""
    return key.strip(), value.strip()


def _item_from_mapping(values: dict[str, object]) -> RiskOpportunityTrackerItem:
    source_priority = values.get("source_priority", ())
    if isinstance(source_priority, list):
        sources = tuple(str(item) for item in source_priority)
    else:
        sources = ()

    item = RiskOpportunityTrackerItem(
        id=_scalar(values, "id"),
        ticker=_scalar(values, "ticker"),
        category=_scalar(values, "category"),
        event_or_indicator=_scalar(values, "event_or_indicator"),
        why_it_matters=_scalar(values, "why_it_matters"),
        status=_scalar(values, "status", "monitoring"),
        impact_if_validated=_scalar(values, "impact_if_validated", "neutral"),
        importance=_scalar(values, "importance", "medium"),
        frequency=_scalar(values, "frequency", "event-driven"),
        validation_rule=_scalar(values, "validation_rule"),
        suggested_research_response=_scalar(values, "suggested_research_response"),
        next_check_date=_scalar(values, "next_check_date")
        or _scalar(values, "next_check", "Next scheduled review"),
        source_priority=sources,
        source_url=_scalar(values, "source_url", "TODO"),
        confidence=_scalar(values, "confidence", "medium"),
        last_checked=_scalar(values, "last_checked"),
        evidence_summary=_scalar(values, "evidence_summary", "No source-backed update recorded."),
    )
    validate_tracker_items((item,))
    return item


def _scalar(values: dict[str, object], key: str, default: str = "") -> str:
    value = values.get(key, default)
    if isinstance(value, list):
        return default
    return str(value).strip().strip('"').strip("'")


def _category_rank(category: str) -> int:
    normalized = category.strip().lower()
    try:
        return CATEGORY_ORDER.index(normalized)
    except ValueError:
        return len(CATEGORY_ORDER)


def _best_result_for_tracker(
    item: RiskOpportunityTrackerItem,
    results: tuple[SearchResult, ...],
) -> SearchResult | None:
    scored: list[tuple[float, SearchResult]] = []
    item_text = f"{item.event_or_indicator} {item.category} {item.validation_rule}".lower()
    for result in results:
        if result.ticker and result.ticker != item.ticker.upper():
            continue
        result_text = _result_text(result)
        if not _result_matches_tracker_topic(item, result_text):
            continue
        score = 0.0
        for token in _keywords(item_text):
            if token in result_text:
                score += 0.15
        if item.category.lower() in result.category.lower() or result.category.lower() in item.category.lower():
            score += 0.25
        score += result.relevance_score * 0.25
        if score >= 0.35:
            scored.append((score, result))
    if not scored:
        return None
    return sorted(scored, key=lambda row: row[0], reverse=True)[0][1]


def _result_matches_tracker_topic(
    item: RiskOpportunityTrackerItem,
    result_text: str,
) -> bool:
    """Require tracker-specific evidence before applying AnySearch updates.

    AnySearch cache entries are discovery evidence, not universal validation.
    A broad NVIDIA earnings-release result should not validate macro rates,
    market-index, technical, or hyperscaler-capex tracker rows unless it
    contains the specific topic evidence required by that row.
    """

    item_text = f"{item.id} {item.event_or_indicator} {item.validation_rule}".lower()
    required_groups = _required_topic_groups(item_text)
    if not required_groups:
        return True
    return all(_contains_any(result_text, group) for group in required_groups)


def _required_topic_groups(item_text: str) -> tuple[tuple[str, ...], ...]:
    if "treasury" in item_text or "10-year" in item_text or "10 year" in item_text:
        return (("treasury", "10-year", "10 year", "yield", "fred"),)
    if "sox" in item_text or "semiconductor index" in item_text:
        return (("sox", "semiconductor index", "market index"),)
    if "moving average" in item_text or "dma" in item_text or "50-day" in item_text:
        return (("moving average", "dma", "50-day", "50 day", "200-day", "200 day"),)
    if "export" in item_text or "restriction" in item_text:
        return (("export", "control", "controls", "restriction", "commerce", "bis", "china"),)
    if "hyperscaler" in item_text or "capex" in item_text:
        return (
            ("capex", "capital expenditure", "capital expenditures"),
            ("hyperscaler", "hyperscalers", "microsoft", "msft", "amazon", "amzn", "google", "googl", "meta", "oracle", "orcl"),
        )
    if "hbm" in item_text or "advanced packaging" in item_text:
        return (("hbm", "high bandwidth memory", "advanced packaging", "cowos", "supply constraint", "supply constraints"),)
    if "data-center" in item_text or "data center" in item_text or "datacenter" in item_text:
        return (
            ("data-center", "data center", "datacenter"),
            ("revenue", "sales", "segment"),
        )
    if "gross margin" in item_text:
        return (("gross margin", "margin"),)
    if "estimate revision" in item_text or "analyst" in item_text:
        return (("estimate", "estimates", "revision", "revisions", "consensus", "analyst", "guidance"),)
    if "next earnings" in item_text:
        return (("earnings date", "earnings calendar", "next earnings", "scheduled", "will report"),)
    return ()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _result_text(result: SearchResult) -> str:
    return (
        f"{result.query} {result.title} {result.source_name} {result.snippet} "
        f"{result.summary} {result.category} {result.reason_for_classification}"
    ).lower()


def _can_validate_tracker(result: SearchResult) -> bool:
    official_types = {
        "primary_company_source",
        "official_regulator",
        "official_government",
        "sec_filing",
        "industry_body",
    }
    return (
        result.confidence == "high"
        and result.status == "confirmed"
        and result.source_type in official_types
    )


def _tracker_evidence_summary(result: SearchResult) -> str:
    return (
        f"{result.title or 'Source result'} ({result.source_type}, "
        f"{result.confidence} confidence, {result.status}). "
        f"{result.summary or result.snippet}"
    ).strip()


def _keywords(text: str) -> tuple[str, ...]:
    stopwords = {
        "and",
        "the",
        "from",
        "with",
        "that",
        "this",
        "should",
        "source",
        "validated",
        "validate",
        "official",
    }
    return tuple(
        token
        for token in text.replace("/", " ").replace("-", " ").split()
        if len(token) >= 4 and token not in stopwords
    )
