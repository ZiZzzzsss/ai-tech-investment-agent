"""Evidence-layer classification and qualitative scoring helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

from src.data.models import EvidenceItem, ScoredAssumption, SearchResult


STRUCTURED = "structured data"
FILING_EXTRACTED = "filing-extracted data"
SEARCH_DISCOVERED = "search-discovered evidence"
MODEL_SCORED = "model-scored assumption"


@dataclass(frozen=True)
class GrowthTrendEvidence:
    revenue_growth_trend: float | None
    gross_margin_trend: float | None
    operating_margin_trend: float | None
    free_cash_flow_trend: float | None
    evidence_items: tuple[EvidenceItem, ...]


FILING_KEYWORDS = {
    "remaining performance obligations": ("remaining performance obligations", "rpo"),
    "backlog": ("backlog", "order backlog"),
    "purchase obligations": ("purchase obligations", "purchase commitments"),
    "customer commitments": ("customer commitment", "customer commitments", "long-term supply"),
    "customer concentration": ("customer concentration", "major customer", "significant customer"),
    "segment revenue": ("segment revenue", "reportable segment"),
    "software/services revenue": ("software", "services revenue", "subscription"),
    "risk factors": ("risk factors",),
    "supply constraints": ("supply constraint", "capacity constraint", "advanced packaging", "hbm"),
    "export controls": ("export control", "export controls", "license requirement"),
    "product transition risks": ("product transition", "architecture transition", "new product ramp"),
}


def calculate_revenue_growth_trend(quarterly_revenue: Iterable[float]) -> float | None:
    values = _clean_series(quarterly_revenue)
    if len(values) < 2 or values[0] == 0:
        return None
    return values[-1] / values[0] - 1


def calculate_margin_trend(revenue: Iterable[float], numerator: Iterable[float]) -> float | None:
    revenue_values = _clean_series(revenue)
    numerator_values = _clean_series(numerator)
    pairs = [(rev, num) for rev, num in zip(revenue_values, numerator_values) if rev]
    if len(pairs) < 2:
        return None
    first_margin = pairs[0][1] / pairs[0][0]
    latest_margin = pairs[-1][1] / pairs[-1][0]
    return latest_margin - first_margin


def calculate_fcf_trend(operating_cash_flow: Iterable[float], capex: Iterable[float]) -> float | None:
    cfo_values = _clean_series(operating_cash_flow)
    capex_values = _clean_series(capex)
    fcf_values = [cfo - abs(capital_spend) for cfo, capital_spend in zip(cfo_values, capex_values)]
    if len(fcf_values) < 2 or fcf_values[0] == 0:
        return None
    return fcf_values[-1] / abs(fcf_values[0]) - 1


def build_growth_trend_evidence(
    quarterly_revenue: Iterable[float],
    gross_profit: Iterable[float],
    operating_income: Iterable[float],
    operating_cash_flow: Iterable[float],
    capex: Iterable[float],
    source_name: str = "SEC EDGAR company facts",
) -> GrowthTrendEvidence:
    revenue = tuple(_clean_series(quarterly_revenue))
    gross = tuple(_clean_series(gross_profit))
    operating = tuple(_clean_series(operating_income))
    cfo = tuple(_clean_series(operating_cash_flow))
    capex_values = tuple(_clean_series(capex))
    revenue_growth = calculate_revenue_growth_trend(revenue)
    gross_margin = calculate_margin_trend(revenue, gross)
    operating_margin = calculate_margin_trend(revenue, operating)
    fcf_trend = calculate_fcf_trend(cfo, capex_values)
    items = (
        _trend_item("Revenue growth trend", revenue_growth, "latest quarter / earliest available quarter - 1", source_name),
        _trend_item("Gross margin trend", gross_margin, "latest gross margin - earliest available gross margin", source_name),
        _trend_item("Operating margin trend", operating_margin, "latest operating margin - earliest available operating margin", source_name),
        _trend_item("FCF trend", fcf_trend, "latest FCF / earliest available FCF - 1, where FCF = CFO - capex", source_name),
    )
    return GrowthTrendEvidence(revenue_growth, gross_margin, operating_margin, fcf_trend, items)


def extract_filing_evidence(text: str, source_name: str = "SEC/company filing", source_url: str = "") -> tuple[EvidenceItem, ...]:
    lowered = text.lower()
    items: list[EvidenceItem] = []
    for name, keywords in FILING_KEYWORDS.items():
        matches = [keyword for keyword in keywords if keyword in lowered]
        if not matches:
            continue
        summary = _keyword_snippet(text, matches[0])
        items.append(
            EvidenceItem(
                name=name,
                data_layer=FILING_EXTRACTED,
                value="found",
                source_name=source_name,
                source_url=source_url,
                explanation=summary,
                confidence="medium",
            )
        )
    return tuple(items)


def hyperscaler_capex_evidence_from_source_cache(results: Iterable[SearchResult]) -> tuple[EvidenceItem, ...]:
    hyperscalers = ("MSFT", "Microsoft", "AMZN", "Amazon", "GOOGL", "Google", "META", "ORCL", "Oracle")
    items = []
    for result in results:
        text = " ".join((result.title, result.summary, result.snippet, result.source_name))
        if not any(name.lower() in text.lower() for name in hyperscalers):
            continue
        if "capex" not in text.lower() and "capital expenditure" not in text.lower() and "ai infrastructure" not in text.lower():
            continue
        confidence = "high" if result.source_type in {"primary_company_source", "sec_filing"} else result.confidence
        items.append(
            EvidenceItem(
                name="Hyperscaler capex evidence",
                data_layer=SEARCH_DISCOVERED,
                value=result.status,
                source_name=result.source_name,
                source_url=result.url,
                explanation=result.summary or result.snippet,
                confidence=confidence,
                warning="" if confidence != "low" else "Low-confidence search result; do not update valuation without primary-source confirmation.",
            )
        )
    return tuple(items)


def build_search_evidence(results: Iterable[SearchResult]) -> tuple[EvidenceItem, ...]:
    items = []
    for result in results:
        if result.status == "irrelevant":
            continue
        items.append(
            EvidenceItem(
                name=result.category or "source discovery",
                data_layer=SEARCH_DISCOVERED,
                value=result.status,
                source_name=result.source_name,
                source_url=result.url,
                explanation=result.summary or result.snippet or result.reason_for_classification,
                confidence=result.confidence,
                warning="" if result.confidence != "low" else "Low-confidence result; keep pending until primary-source evidence is found.",
            )
        )
    return tuple(items)


def build_scoring_rubric(
    ticker: str,
    trend_evidence: GrowthTrendEvidence,
    filing_evidence: tuple[EvidenceItem, ...],
    search_evidence: tuple[EvidenceItem, ...],
    market_cap: float | None = None,
    shares_outstanding: float | None = None,
) -> tuple[ScoredAssumption, ...]:
    evidence_text = _combined_evidence_text(filing_evidence, search_evidence)
    revenue_growth = trend_evidence.revenue_growth_trend
    gross_margin_trend = trend_evidence.gross_margin_trend
    operating_margin_trend = trend_evidence.operating_margin_trend

    return (
        _score("TAM/SAM runway score", _tam_score(evidence_text, ticker), evidence_text, "Scores addressable runway from AI infrastructure, hyperscaler, and platform evidence."),
        _score("Business quality score", _quality_score(revenue_growth, gross_margin_trend, operating_margin_trend, evidence_text), evidence_text, "Scores margin quality, profitability, growth consistency, balance-sheet context, and moat evidence."),
        _score("Pricing power score", _pricing_power_score(gross_margin_trend, evidence_text), evidence_text, "Scores pricing power from gross-margin trend and management/product-mix evidence."),
        _score("Gross-margin durability score", _gross_margin_durability_score(gross_margin_trend, evidence_text), evidence_text, "Scores whether gross margins appear sustainable through supply, mix, and competition."),
        _score("Recurring/software revenue quality score", _recurring_revenue_score(evidence_text), evidence_text, "Scores software/services or subscription mix when segment evidence exists."),
        _score("Cyclicality score", _cyclicality_score(evidence_text), evidence_text, "Higher score means more cyclical exposure and therefore a larger valuation penalty."),
        _score("Customer concentration risk score", _customer_concentration_score(evidence_text), evidence_text, "Higher score means greater customer concentration uncertainty or disclosed dependence."),
        _score("Dilution risk score", _dilution_score(shares_outstanding, market_cap, ticker), evidence_text, "Higher score means greater dilution or financing-risk concern."),
        _score("Execution risk score", _execution_score(evidence_text, ticker), evidence_text, "Scores product ramps, supply constraints, financing needs, and delivery complexity."),
        _score("Moat score", _moat_score(evidence_text, ticker), evidence_text, "Scores competitive durability from ecosystem, switching costs, technology leadership, and supply position."),
    )


def model_eps_growth_assumption(
    analyst_eps_growth: float | None,
    revenue_growth: float | None,
    intrinsic_growth: float,
) -> EvidenceItem:
    if analyst_eps_growth and analyst_eps_growth > 0:
        return EvidenceItem(
            "Forward EPS growth",
            STRUCTURED,
            f"{analyst_eps_growth:.1%}",
            "Structured estimate provider",
            explanation="Forward EPS growth supplied by configured estimate connector.",
            confidence="medium",
        )
    assumption = max(0.01, min(0.35, revenue_growth if revenue_growth is not None else intrinsic_growth))
    return EvidenceItem(
        "Forward EPS growth",
        MODEL_SCORED,
        f"{assumption:.1%}",
        "Model assumption from available historical growth and Bayesian intrinsic-growth estimate",
        explanation="No structured estimate revision source is configured; this is an explicit model-generated assumption, not a sourced consensus estimate.",
        confidence="low",
        warning="Low confidence until FMP or another structured estimates provider supplies forward EPS growth.",
    )


def _trend_item(name: str, value: float | None, formula: str, source_name: str) -> EvidenceItem:
    if value is None:
        return EvidenceItem(
            name,
            STRUCTURED,
            "insufficient history",
            source_name,
            explanation=formula,
            confidence="low",
            warning="Needs at least two comparable quarterly observations.",
        )
    return EvidenceItem(name, STRUCTURED, f"{value:.1%}", source_name, explanation=formula, confidence="medium")


def _clean_series(values: Iterable[float]) -> list[float]:
    cleaned = []
    for value in values:
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            continue
    return cleaned


def _keyword_snippet(text: str, keyword: str) -> str:
    match = re.search(re.escape(keyword), text, flags=re.IGNORECASE)
    if not match:
        return f"Keyword found: {keyword}"
    start = max(0, match.start() - 80)
    end = min(len(text), match.end() + 140)
    return " ".join(text[start:end].split())


def _combined_evidence_text(filing_evidence: tuple[EvidenceItem, ...], search_evidence: tuple[EvidenceItem, ...]) -> str:
    text = " ".join(item.explanation + " " + item.name for item in filing_evidence + search_evidence)
    return text or "Evidence incomplete"


def _score(name: str, score: int, evidence: str, explanation: str) -> ScoredAssumption:
    confidence = "medium" if evidence != "Evidence incomplete" else "low"
    return ScoredAssumption(
        name=name,
        score=max(1, min(5, score)),
        evidence=evidence[:360],
        explanation=explanation,
        confidence=confidence,
        warning="" if confidence != "low" else "Evidence incomplete; score is a conservative placeholder.",
    )


def _tam_score(evidence: str, ticker: str) -> int:
    lowered = evidence.lower()
    if ticker.upper() == "NVDA" or "ai infrastructure" in lowered or "hyperscaler" in lowered or "ai factory" in lowered:
        return 5
    if "semiconductor" in lowered or "cloud" in lowered:
        return 4
    return 3


def _quality_score(revenue_growth: float | None, gross_margin_trend: float | None, operating_margin_trend: float | None, evidence: str) -> int:
    score = 3
    if revenue_growth is not None and revenue_growth > 0.15:
        score += 1
    if (gross_margin_trend or 0) >= 0 and (operating_margin_trend or 0) >= 0:
        score += 1
    if "Evidence incomplete" in evidence:
        score -= 1
    return score


def _pricing_power_score(gross_margin_trend: float | None, evidence: str) -> int:
    score = 3
    if gross_margin_trend is not None and gross_margin_trend >= 0:
        score += 1
    if "pricing" in evidence.lower() or "margin" in evidence.lower():
        score += 1
    return score


def _gross_margin_durability_score(gross_margin_trend: float | None, evidence: str) -> int:
    score = 3
    if gross_margin_trend is not None and gross_margin_trend >= -0.02:
        score += 1
    if "supply" in evidence.lower() or "product mix" in evidence.lower():
        score += 1
    return score


def _recurring_revenue_score(evidence: str) -> int:
    lowered = evidence.lower()
    if "subscription" in lowered or "software/services" in lowered or "software" in lowered:
        return 4
    return 2


def _cyclicality_score(evidence: str) -> int:
    lowered = evidence.lower()
    if "cycle" in lowered or "semiconductor" in lowered or "supply constraint" in lowered:
        return 4
    return 3


def _customer_concentration_score(evidence: str) -> int:
    lowered = evidence.lower()
    if "customer concentration" in lowered or "major customer" in lowered:
        return 4
    if "hyperscaler" in lowered:
        return 3
    return 2


def _dilution_score(shares_outstanding: float | None, market_cap: float | None, ticker: str) -> int:
    if ticker.upper() in {"NBIS"}:
        return 5
    if shares_outstanding and market_cap:
        return 2
    return 3


def _execution_score(evidence: str, ticker: str) -> int:
    lowered = evidence.lower()
    if ticker.upper() in {"NBIS"}:
        return 5
    if "supply constraint" in lowered or "product transition" in lowered or "advanced packaging" in lowered:
        return 4
    return 3


def _moat_score(evidence: str, ticker: str) -> int:
    lowered = evidence.lower()
    if ticker.upper() == "NVDA" or "ecosystem" in lowered or "platform" in lowered or "cuda" in lowered:
        return 5
    if "moat" in lowered or "monopoly" in lowered:
        return 4
    return 3
