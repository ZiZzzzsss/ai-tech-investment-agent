"""Static HTML report renderer for buy-side memos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from src.reports.markdown_report import BuySideMemoInput
from src.reports.report_schema import validate_report_compliance
from src.research import RiskOpportunityTrackerItem


HTML_MANDATORY_SECTIONS = (
    "Hero",
    "Executive verdict",
    "Key metrics",
    "Financial quality",
    "Valuation",
    "Growth drivers",
    "Entry framework",
    "Risk & Opportunity Tracker",
    "Model detail",
    "Audit appendix",
)


@dataclass(frozen=True)
class DecisionProfile:
    """Top-level decision-readiness view derived from sourced report inputs."""

    decision_ready_status: str
    investment_posture: str
    verdict: str
    verdict_reason: str
    what_would_change: str
    basis: str
    business_quality_view: str
    growth_view: str
    valuation_view: str
    timing_view: str
    data_confidence_view: str
    one_sentence_conclusion: str
    decision_quality_score: float


def render_html_memo(inputs: BuySideMemoInput) -> str:
    """Render a polished static HTML memo."""

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    decision = _decision_profile(inputs)
    template = _load_template("memo.html.j2")
    dashboard = _render_dashboard(inputs, generated_at, decision)
    sections = _render_sections(inputs, decision)
    toc = _render_toc()

    html = _render_template(
        template,
        {
            "title": f"{inputs.company_name} ({inputs.ticker})",
            "company_name": inputs.company_name,
            "ticker": inputs.ticker,
            "generated_at": generated_at,
            "latest_price": _money_or_unavailable(_mock_price(inputs)),
            "investment_posture": decision.investment_posture,
            "one_sentence_conclusion": decision.one_sentence_conclusion,
            "decision_ready_status": decision.decision_ready_status.replace("_", " ").title(),
            "data_freshness_badge": "Mock data" if inputs.report_mode == "mock" else "Live source check",
            "confidence_badge": decision.data_confidence_view,
            "toc": toc,
            "dashboard": dashboard,
            "sections": sections,
        },
    )
    validation = validate_report_compliance(
        report_text=_strip_markup_for_validation(html),
        claims=inputs.evidence_claims,
        report_is_mock=inputs.is_mock,
    )
    if not validation.is_valid:
        raise ValueError("HTML report compliance validation failed: " + "; ".join(validation.errors))
    return html


def render_index(memos: tuple[tuple[str, str, str], ...]) -> str:
    """Render a static index page for generated company memos."""

    cards = "\n".join(
        (
            f'<a class="index-card" href="company_memos/{filename}">'
            f"<span>{escape(ticker)}</span>"
            f"<strong>{escape(company_name)}</strong>"
            "</a>"
        )
        for ticker, company_name, filename in sorted(memos)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Investment Research Memos</title>
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body>
  <main class="index-shell">
    <p class="eyebrow">AI technology research</p>
    <h1>Company memos</h1>
    <p class="lede">Static mock research pages for workflow testing. These pages do not provide buy, sell, or hold advice.</p>
    <section class="index-grid" aria-label="Company memo links">
      {cards or '<p>No HTML memos generated yet.</p>'}
    </section>
  </main>
</body>
</html>
"""


def _decision_profile(inputs: BuySideMemoInput) -> DecisionProfile:
    valuation_ready = _valuation_ready(inputs)
    blockers = _valuation_blockers(inputs)
    mixed_period = _has_mixed_period_warning(inputs)
    price_available = inputs.latest_price > 0 or _safe_float(inputs.valuation_multiples.get("Latest price", "")) is not None
    financial_available = any(_safe_float(_split_metric_value(value)[0]) is not None for value in inputs.financial_snapshot.values())
    fallback_used = _fallback_used(inputs)

    if valuation_ready and inputs.calculation_audit_passed and not mixed_period:
        decision_ready_status = "decision_ready"
        valuation_view = "valuation-ready"
        verdict = _executive_verdict_headline(inputs, valuation_view)
        posture = "Research posture: valuation-ready"
        reason = "Price, source-backed financial denominators, period checks, scenarios, and calculation audit are available."
    elif price_available and financial_available:
        decision_ready_status = "partially_ready"
        valuation_view = "not valuation-ready"
        verdict = _executive_verdict_headline(inputs, valuation_view)
        posture = "Research only / wait for reconciled valuation"
        reason = "Business and timing signals are useful, but valuation is blocked by missing or period-incompatible inputs."
    else:
        decision_ready_status = "not_decision_ready"
        valuation_view = "not valuation-ready"
        verdict = _executive_verdict_headline(inputs, valuation_view)
        posture = "Research only"
        reason = "Core price, financial, or valuation inputs are missing from current sources."

    business_quality = _business_quality_view(inputs)
    growth_view = _growth_view(inputs)
    timing_view = _timing_view(inputs)
    data_confidence = _data_confidence_view(inputs, valuation_ready, mixed_period, fallback_used)
    quality_score = _decision_quality_score(inputs, valuation_ready, mixed_period, fallback_used, blockers)
    what_would_change = _what_would_change_decision(inputs, blockers)
    basis_parts = []
    if valuation_ready:
        basis_parts.append("valuation")
    if inputs.bayesian_growth.intrinsic_growth_estimate:
        basis_parts.append("growth")
    if inputs.gf_dma_health.overall_gf_dma_health_score:
        basis_parts.append("technicals/timing")
    if blockers:
        basis_parts.append("incomplete data")
    basis = ", ".join(basis_parts) if basis_parts else "incomplete data"
    one_sentence = (
        f"{inputs.ticker} is {decision_ready_status.replace('_', ' ')}: {business_quality.lower()}, "
        f"{growth_view.lower()}, valuation {valuation_view}, and timing {timing_view.lower()}."
    )
    return DecisionProfile(
        decision_ready_status=decision_ready_status,
        investment_posture=posture,
        verdict=verdict,
        verdict_reason=reason,
        what_would_change=what_would_change,
        basis=basis,
        business_quality_view=business_quality,
        growth_view=growth_view,
        valuation_view=valuation_view,
        timing_view=timing_view,
        data_confidence_view=data_confidence,
        one_sentence_conclusion=one_sentence,
        decision_quality_score=quality_score,
    )


def _executive_verdict_headline(inputs: BuySideMemoInput, valuation_view: str) -> str:
    """Create an insight-first headline instead of a process-readiness label."""

    if valuation_view != "valuation-ready":
        return "Strong signals, but valuation evidence is incomplete"
    entry_zone = _entry_zone_label(inputs).lower()
    if "expensive" in entry_zone:
        return "Strong AI franchise, price already asks for durability"
    if "reasonable" in entry_zone:
        return "Strong AI franchise near the working valuation range"
    if "conservative" in entry_zone:
        return "Strong AI franchise inside the conservative valuation range"
    return "Strong AI franchise with valuation now testable"


def _valuation_ready(inputs: BuySideMemoInput) -> bool:
    required = ("P/E", "P/FCF", "EV/Sales")
    return (
        inputs.fair_value_per_share > 0
        and inputs.calculation_audit_passed
        and not _blocking_period_warnings(inputs)
        and any(_is_available_text(inputs.valuation_multiples.get(metric, "")) for metric in required)
    )


def _valuation_blockers(inputs: BuySideMemoInput) -> tuple[str, ...]:
    blockers: list[str] = []
    if inputs.fair_value_per_share <= 0:
        blockers.append("Scenario fair value is unavailable.")
    if not any(_is_available_text(inputs.valuation_multiples.get(metric, "")) for metric in ("P/E", "P/FCF", "EV/Sales")):
        missing = [
            f"{metric}: {inputs.valuation_multiples.get(metric, 'Unavailable from current sources')}"
            for metric in ("P/E", "P/FCF", "EV/Sales")
            if not _is_available_text(inputs.valuation_multiples.get(metric, ""))
        ]
        blockers.append("No primary valuation multiple is available (" + "; ".join(missing[:3]) + ").")
    blockers.extend(_blocking_period_warnings(inputs)[:4])
    if not inputs.calculation_audit_passed:
        blockers.append("Calculation audit failed.")
    return tuple(dict.fromkeys(blockers))


def _is_available_text(value: object) -> bool:
    text = str(value)
    return bool(text) and "Unavailable:" not in text and "Not available from current sources" not in text


def _has_mixed_period_warning(inputs: BuySideMemoInput) -> bool:
    return bool(_blocking_period_warnings(inputs))


def _blocking_period_warnings(inputs: BuySideMemoInput) -> tuple[str, ...]:
    essential_metrics = {"Revenue", "Net Income", "EV/Sales", "P/E", "P/S"}
    warnings: list[str] = []
    for row in inputs.period_basis_rows:
        warning = row.warning.lower()
        if row.metric not in essential_metrics:
            continue
        if not warning or warning == "none":
            continue
        if any(phrase in warning for phrase in ("mismatch", "mixed", "must be ttm", "got annual", "got quarterly")):
            warnings.append(f"{row.metric}: {row.warning}")
    return tuple(dict.fromkeys(warnings))


def _has_any_period_warning(inputs: BuySideMemoInput) -> bool:
    warning_text = " ".join(row.warning.lower() for row in inputs.period_basis_rows)
    return any(
        phrase in warning_text
        for phrase in ("mismatch", "mixed", "must be ttm", "got annual", "got quarterly", "fewer than four quarters")
    )


def _fallback_used(inputs: BuySideMemoInput) -> bool:
    text = " ".join(str(value).lower() for value in (*inputs.financial_snapshot.values(), *inputs.valuation_multiples.values()))
    if "fallback" in text:
        return True
    return any(getattr(item, "availability", "") == "fallback" or "fallback" in getattr(item, "reason", "").lower() for item in inputs.data_source_status)


def _business_quality_view(inputs: BuySideMemoInput) -> str:
    gross_margin = _safe_float(inputs.valuation_multiples.get("Gross margin", "").replace("%", ""))
    operating_margin = _safe_float(inputs.valuation_multiples.get("Operating margin", "").replace("%", ""))
    if gross_margin is not None and operating_margin is not None:
        if gross_margin >= 50 and operating_margin >= 30:
            return "Business quality: strong"
        if gross_margin >= 35 and operating_margin >= 15:
            return "Business quality: solid"
    if any(score.score >= 4 for score in inputs.scoring_rubric if "quality" in score.name.lower() or "moat" in score.name.lower()):
        return "Business quality: strong but evidence-scored"
    return "Business quality: incomplete"


def _growth_view(inputs: BuySideMemoInput) -> str:
    growth = inputs.bayesian_growth.intrinsic_growth_estimate
    if growth >= 0.18:
        return "Growth: strong but needs source confirmation"
    if growth >= 0.10:
        return "Growth: constructive"
    if growth > 0:
        return "Growth: modest"
    return "Growth: unavailable"


def _timing_view(inputs: BuySideMemoInput) -> str:
    score = inputs.gf_dma_health.overall_gf_dma_health_score
    if score >= 75:
        return "healthy trend"
    if score >= 60:
        return "neutral to slightly weak"
    if score > 0:
        return "weak or extended"
    return "unavailable"


def _data_confidence_view(inputs: BuySideMemoInput, valuation_ready: bool, mixed_period: bool, fallback_used: bool) -> str:
    if not valuation_ready or mixed_period:
        return "Low to medium"
    if fallback_used:
        return "Medium"
    lowered = inputs.confidence_level.lower()
    if "high" in lowered:
        return "High"
    if "medium" in lowered:
        return "Medium"
    return "Low"


def _decision_quality_score(
    inputs: BuySideMemoInput,
    valuation_ready: bool,
    mixed_period: bool,
    fallback_used: bool,
    blockers: tuple[str, ...],
) -> float:
    score = min(inputs.data_quality_score, 100.0)
    if not valuation_ready:
        score -= 25
    if mixed_period:
        score -= 20
    if fallback_used:
        score -= 10
    score -= min(20, len(blockers) * 3)
    if inputs.report_mode == "mock":
        score -= 15
    return max(0.0, score)


def _what_would_change_decision(inputs: BuySideMemoInput, blockers: tuple[str, ...]) -> str:
    if not blockers and _valuation_ready(inputs):
        return "Fresh primary-source evidence that changes revenue, margin, FCF, or risk assumptions."
    needed = "; ".join(blockers[:3]) if blockers else "source-backed valuation inputs"
    return f"Resolve valuation blockers ({needed}) and rerun the calculation audit."


def _render_dashboard(inputs: BuySideMemoInput, generated_at: str, decision: DecisionProfile) -> str:
    template = _load_template("dashboard.html.j2")
    cards = [
        _metric_card("Decision Ready Status", decision.decision_ready_status.replace("_", " ").title(), "Top-level readiness gate"),
        _metric_card("Valuation View", decision.valuation_view, _valuation_card_note(inputs)),
        _metric_card("Growth View", decision.growth_view, inputs.bayesian_growth.most_likely_regime.value),
        _metric_card("Timing View", decision.timing_view, "GF-DMA and moving-average context"),
        _metric_card("AI Growth Score", _pct(inputs.bayesian_growth.intrinsic_growth_estimate), inputs.bayesian_growth.most_likely_regime.value),
        _metric_card("Risk Level", _risk_level(inputs), "Tracker and GF-DMA context"),
        _metric_card("Entry Framework", _entry_zone_label(inputs), "Scenario-based discipline"),
        _metric_card("Decision-Useful Quality", f"{decision.decision_quality_score:.1f}/100", decision.data_confidence_view),
        _metric_card("Calculation Audit", _calculation_audit_label(inputs), "Formula registry fixtures"),
    ]
    cards.extend(_escalated_tracker_cards(inputs.risk_opportunity_trackers))
    return _render_template(
        template,
        {
            "company_name": escape(inputs.company_name),
            "ticker": escape(inputs.ticker),
            "archetype": escape(_display_archetype(inputs.archetype_name)),
            "price": _money_or_unavailable(_mock_price(inputs)),
            "confidence": escape(decision.data_confidence_view),
            "generated_at": escape(generated_at),
            "verdict": escape(decision.verdict),
            "verdict_reason": escape(decision.verdict_reason),
            "what_would_change": escape(decision.what_would_change),
            "basis": escape(decision.basis),
            "verdict_insights": _executive_verdict_insights(inputs, decision),
            "summary": _executive_summary_panel(inputs, decision),
            "cards": "\n".join(cards),
        },
    )


def _render_sections(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    sections = [
        _section("key-metrics", "Key metrics", _key_metric_cards(inputs, decision)),
        _section(
            "financial-quality",
            "Financial quality",
            _financial_quality_summary(inputs, decision)
            + _financial_snapshot_cards(inputs)
            + _valuation_multiple_cards(inputs),
        ),
        _section("valuation", "Valuation", _valuation_section(inputs, decision)),
        _section("growth-drivers", "Growth drivers", _growth_drivers_section(inputs)),
        _section("entry-framework", "Entry framework", _entry_framework_section(inputs, decision)),
        _section("risk-and-opportunity-tracker", "Risks & Opportunities", _risk_opportunity_tracker_cards(inputs)),
        _section("model-detail", "Model detail", _model_detail_section(inputs)),
        _section("audit-appendix", "Audit appendix", _audit_appendix(inputs, decision)),
    ]
    return "\n".join(sections)


def _section(section_id: str, title: str, body: str) -> str:
    return f'<section id="{section_id}" class="section-card"><h2>{escape(title)}</h2>{body}</section>'


def _render_toc() -> str:
    links = "\n".join(
        f'<a href="#{_slug(title)}">{escape(_toc_label(title))}</a>'
        for title in HTML_MANDATORY_SECTIONS
    )
    return f'<nav class="toc" aria-label="Table of contents">{links}</nav>'


def _toc_label(title: str) -> str:
    if title == "Risk & Opportunity Tracker":
        return "Risks & Opportunities"
    return title


def _metric_card(label: str, value: str, note: str) -> str:
    return f'<article class="metric-card"><span>{escape(label)}</span><strong>{escape(value)}</strong><small>{escape(note)}</small></article>'


def _executive_verdict_insights(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    """Render the decision box as investor insights rather than process status."""

    rows = (
        ("Core read", _core_read_sentence(inputs, decision)),
        ("Valuation tension", _valuation_tension_sentence(inputs)),
        ("What can change the view", _next_view_change_sentence(inputs, decision)),
        ("Risk/opportunity watch", _risk_opportunity_sentence(inputs)),
    )
    body = "".join(
        (
            '<div class="verdict-insight-item">'
            f"<span>{escape(label)}</span>"
            f"<p>{escape(text)}</p>"
            "</div>"
        )
        for label, text in rows
    )
    return (
        '<div class="verdict-insight-panel">'
        f"{body}"
        f'<p class="verdict-insight-footnote"><strong>Conclusion basis:</strong> {escape(decision.basis)}. '
        "This is a research read, not a transaction instruction.</p>"
        "</div>"
    )


def _core_read_sentence(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    revenue = _safe_float(_split_metric_value(inputs.financial_snapshot.get("Revenue", ""))[0])
    gross_margin = _safe_float(inputs.valuation_multiples.get("Gross margin", "").replace("%", ""))
    operating_margin = _safe_float(inputs.valuation_multiples.get("Operating margin", "").replace("%", ""))
    parts = []
    if revenue is not None:
        parts.append(f"revenue base is {_compact_money(revenue)}")
    if gross_margin is not None:
        parts.append(f"gross margin is {gross_margin:.1f}%")
    if operating_margin is not None:
        parts.append(f"operating margin is {operating_margin:.1f}%")
    if parts:
        return (
            f"{decision.business_quality_view.replace('Business quality: ', '').title()} business-quality read: "
            + ", ".join(parts)
            + ". The main question is whether these economics persist as AI infrastructure demand cycles."
        )
    return f"{decision.business_quality_view}. The useful next step is to source revenue, margin, and cash-flow evidence."


def _valuation_tension_sentence(inputs: BuySideMemoInput) -> str:
    price = _mock_price(inputs)
    fair_value = inputs.fair_value_per_share
    entry_zone = _entry_zone_label(inputs).lower()
    if price > 0 and fair_value > 0:
        gap = (price / fair_value - 1) * 100
        direction = "above" if gap >= 0 else "below"
        return (
            f"Latest price is {_money(price)} versus scenario-weighted fair value of {_money(fair_value)}, "
            f"about {abs(gap):.1f}% {direction}; the entry framework reads {entry_zone}."
        )
    if fair_value > 0:
        return f"Scenario-weighted fair value is {_money(fair_value)}, but latest price is unavailable from current sources."
    return "Fair value is not yet available, so the memo should emphasize evidence quality before valuation conclusions."


def _next_view_change_sentence(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    if decision.decision_ready_status == "decision_ready":
        monitors = ", ".join(inputs.required_monitoring_indicators[:3])
        if monitors:
            return f"The view should move only if primary sources change revenue, margins, FCF, or these checks: {monitors}."
        return decision.what_would_change
    return decision.what_would_change


def _risk_opportunity_sentence(inputs: BuySideMemoInput) -> str:
    items = inputs.risk_opportunity_trackers
    high_items = [item for item in items if item.importance == "high"]
    positive = next((item.event_or_indicator for item in high_items if item.impact_if_validated == "positive"), None)
    negative = next((item.event_or_indicator for item in high_items if item.impact_if_validated == "negative"), None)
    validated_count = sum(1 for item in high_items if item.status == "validated")
    pending_count = sum(1 for item in high_items if item.status == "pending")
    details = [f"{len(high_items)} high-importance tracker items", f"{validated_count} validated", f"{pending_count} pending"]
    if positive:
        details.append(f"key upside check: {positive}")
    if negative:
        details.append(f"key downside check: {negative}")
    return "; ".join(details) + "."


def _executive_summary_panel(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    tracker_items = inputs.risk_opportunity_trackers
    high_items = [item for item in tracker_items if item.importance == "high"]
    escalated_items = [item for item in tracker_items if item.status == "escalated"]
    pending_items = [item for item in tracker_items if item.status == "pending"]
    positive_items = [item for item in high_items if item.impact_if_validated == "positive"]
    negative_items = [item for item in high_items if item.impact_if_validated == "negative"]

    valuation = _executive_valuation_readout(inputs)
    growth = decision.growth_view
    tam = _executive_tam_readout(inputs)
    gf_dma = (
        f"GF-DMA is {inputs.gf_dma_health.overall_gf_dma_health_score:.1f}/100; "
        "this is a timing and entry-discipline signal, not intrinsic value."
    )
    tracker = _executive_tracker_readout(
        high_count=len(high_items),
        escalated_items=escalated_items,
        pending_count=len(pending_items),
        positive_items=positive_items,
        negative_items=negative_items,
    )

    rows = (
        ("Business quality", decision.business_quality_view),
        ("Valuation", valuation),
        ("Growth", growth),
        ("TAM-adjusted PEG", tam),
        ("Timing", f"{decision.timing_view}. {gf_dma}"),
        ("Data confidence", decision.data_confidence_view),
        ("Risk & opportunity", tracker),
    )
    body = "".join(
        f"<div><span>{escape(label)}</span><p>{escape(text)}</p></div>"
        for label, text in rows
    )
    return (
        '<article class="executive-summary-card">'
        "<h3>Executive summary</h3>"
        f'<div class="executive-summary-grid">{body}</div>'
        "</article>"
    )


def _executive_valuation_readout(inputs: BuySideMemoInput) -> str:
    if inputs.fair_value_per_share <= 0:
        return "Scenario fair value is unavailable until source-backed valuation inputs pass period and audit checks."
    return (
        f"Scenario-weighted fair value is {_money(inputs.fair_value_per_share)}, "
        f"with the current entry framework labeled {_entry_zone_label(inputs).lower()}."
    )


def _executive_tam_readout(inputs: BuySideMemoInput) -> str:
    if inputs.tam_adjusted_peg.tam_adjusted_peg <= 0:
        return "TAM-adjusted PEG is unavailable until P/E and EPS growth inputs are sourced or explicitly modeled."
    return (
        f"TAM-adjusted PEG is {inputs.tam_adjusted_peg.tam_adjusted_peg:.2f}x, "
        f"classified as {inputs.tam_adjusted_peg.quality_adjusted_interpretation.lower()}."
    )


def _executive_tracker_readout(
    high_count: int,
    escalated_items: list[RiskOpportunityTrackerItem],
    pending_count: int,
    positive_items: list[RiskOpportunityTrackerItem],
    negative_items: list[RiskOpportunityTrackerItem],
) -> str:
    if escalated_items:
        top = escalated_items[0].event_or_indicator
        return f"{len(escalated_items)} escalated tracker item(s), led by {top}; review scenario assumptions before changing the view."
    positive_label = positive_items[0].event_or_indicator if positive_items else "no high-importance positive item"
    negative_label = negative_items[0].event_or_indicator if negative_items else "no high-importance negative item"
    return (
        f"{high_count} high-importance tracker item(s) and {pending_count} pending signal(s). "
        f"Key opportunity: {positive_label}. Key risk: {negative_label}."
    )


def _dashboard_value(value: str) -> str:
    if value == "Not available from current sources":
        return "Unavailable"
    return value


def _valuation_card_note(inputs: BuySideMemoInput) -> str:
    if inputs.fair_value_per_share <= 0:
        return "Source-backed valuation inputs needed"
    return f"Fair value {_money(inputs.fair_value_per_share)}"


def _html_valuation_summary(inputs: BuySideMemoInput) -> str:
    if inputs.fair_value_per_share <= 0:
        return (
            "Scenario-weighted fair value is not available from current sources because required live valuation inputs are missing. "
            "This is not an instruction to transact."
        )
    return (
        f"Scenario-weighted fair value is {_money(inputs.fair_value_per_share)}. "
        "This is an analytical reference point, not an instruction to transact."
    )


def _display_archetype(archetype_name: str) -> str:
    if "(" in archetype_name and archetype_name.endswith(")"):
        return archetype_name.split("(", 1)[1].removesuffix(")")
    return archetype_name


def _short_confidence(confidence_level: str) -> str:
    lowered = confidence_level.lower()
    if "high" in lowered:
        return "High"
    if "medium" in lowered:
        return "Medium"
    return "Low"


def _mock_price(inputs: BuySideMemoInput) -> float:
    if inputs.latest_price > 0:
        return inputs.latest_price
    if inputs.fair_value_per_share <= 0:
        return 0.0
    return max(1.0, inputs.fair_value_per_share * 0.96)


def _entry_zone_label(inputs: BuySideMemoInput) -> str:
    if inputs.fair_value_per_share <= 0:
        return "Not decision-ready"
    price = _mock_price(inputs)
    if price <= 0:
        return "Unavailable"
    if price <= inputs.entry_zones.conservative_entry_max:
        return "Conservative"
    if price <= inputs.entry_zones.reasonable_accumulation_max:
        return "Reasonable"
    return "Expensive / wait"


def _risk_level(inputs: BuySideMemoInput) -> str:
    score = inputs.gf_dma_health.overall_gf_dma_health_score
    if "speculative" in inputs.archetype_name:
        return "Very High"
    if score >= 80:
        return "Medium"
    if score >= 65:
        return "Medium-High"
    return "High"


def _calculation_audit_label(inputs: BuySideMemoInput) -> str:
    return "PASS" if inputs.calculation_audit_passed else "FAIL"


def _calculation_audit_card(inputs: BuySideMemoInput) -> str:
    status = _calculation_audit_label(inputs)
    badge_class = "source-available" if inputs.calculation_audit_passed else "source-unavailable"
    warning_rows = inputs.calculation_audit_warnings or (
        "All deterministic fixture checks passed for valuation, scenario, entry-zone, PEG, GF-DMA, moving-average, and data-quality formulas.",
    )
    rows = "".join(f"<li>{escape(item)}</li>" for item in warning_rows)
    return (
        '<div class="audit-card">'
        f'<p><span class="source-status {badge_class}">{escape(status)}</span> '
        "Calculations are checked against the shared formula registry before the memo is rendered.</p>"
        "<ul>"
        f"{rows}"
        "</ul>"
        '<p class="subtle">Run <code>python run_report.py --audit-calculations</code> to regenerate the standalone audit report.</p>'
        "</div>"
    )


def _dict_table(values: dict[str, str], caption: str = "") -> str:
    rows = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>"
        for key, value in values.items()
    )
    heading = f"<h3>{escape(caption)}</h3>" if caption else ""
    return f'{heading}<div class="table-wrap"><table>{rows}</table></div>'


def _key_metric_cards(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    metrics = [
        _decision_metric("Latest price", _format_valuation_figure("Latest price", inputs.valuation_multiples.get("Latest price", "")), _metric_period_source(inputs, "Latest price"), "neutral", _valuation_insight("Latest price", inputs.valuation_multiples.get("Latest price", ""), inputs), _latest_price_so_what(inputs)),
        _decision_metric_from_snapshot(inputs, "Revenue", _revenue_so_what(inputs)),
        _decision_metric("Gross margin", _format_valuation_figure("Gross margin", inputs.valuation_multiples.get("Gross margin", "")), _valuation_source_note("Gross margin", inputs.valuation_multiples.get("Gross margin", "")), _status_from_available_text(inputs.valuation_multiples.get("Gross margin", "")), _valuation_insight("Gross margin", inputs.valuation_multiples.get("Gross margin", ""), inputs), _margin_so_what(inputs, "gross")),
        _decision_metric("Operating margin", _format_valuation_figure("Operating margin", inputs.valuation_multiples.get("Operating margin", "")), _valuation_source_note("Operating margin", inputs.valuation_multiples.get("Operating margin", "")), _status_from_available_text(inputs.valuation_multiples.get("Operating margin", "")), _valuation_insight("Operating margin", inputs.valuation_multiples.get("Operating margin", ""), inputs), _margin_so_what(inputs, "operating")),
        _decision_metric("Valuation readiness", decision.valuation_view, "Period-aware valuation checks", "negative" if not _valuation_ready(inputs) else "positive", decision.verdict_reason, _valuation_readiness_so_what(inputs)),
        _decision_metric("Bayesian growth", _pct(inputs.bayesian_growth.intrinsic_growth_estimate), "Research model", "positive" if inputs.bayesian_growth.intrinsic_growth_estimate >= 0.15 else "neutral", decision.growth_view, _bayesian_so_what(inputs)),
        _decision_metric("GF-DMA timing", f"{inputs.gf_dma_health.overall_gf_dma_health_score:.1f}/100", "Market data + fundamentals", "positive" if inputs.gf_dma_health.overall_gf_dma_health_score >= 70 else "neutral", inputs.gf_dma_health.explanation, _gf_dma_so_what(inputs)),
        _decision_metric("Risk tracker", _risk_level(inputs), "Risk & Opportunity Tracker", "negative" if _risk_level(inputs) in {"High", "Very High"} else "neutral", _executive_tracker_readout(
            len([item for item in inputs.risk_opportunity_trackers if item.importance == "high"]),
            [item for item in inputs.risk_opportunity_trackers if item.status == "escalated"],
            len([item for item in inputs.risk_opportunity_trackers if item.status == "pending"]),
            [item for item in inputs.risk_opportunity_trackers if item.importance == "high" and item.impact_if_validated == "positive"],
            [item for item in inputs.risk_opportunity_trackers if item.importance == "high" and item.impact_if_validated == "negative"],
        ), _risk_tracker_so_what(inputs)),
    ]
    return '<div class="decision-metric-grid">' + "".join(metrics) + "</div>"


def _decision_metric_from_snapshot(inputs: BuySideMemoInput, label: str, decision_impact: str) -> str:
    figure, source = _split_metric_value(inputs.financial_snapshot.get(label, "Not available from current sources"))
    return _decision_metric(
        label,
        _format_financial_figure(label, figure),
        source,
        _status_from_available_text(figure),
        _financial_insight(label, figure, inputs.financial_snapshot),
        decision_impact,
    )


def _latest_price_so_what(inputs: BuySideMemoInput) -> str:
    price = _safe_float(inputs.valuation_multiples.get("Latest price", ""))
    fair_value = inputs.fair_value_per_share
    if price and fair_value > 0:
        premium = price / fair_value - 1
        if premium > 0.10:
            return f"At {_money(price)}, price is {premium:.1%} above scenario-weighted fair value, so entry discipline matters."
        if premium < -0.10:
            return f"At {_money(price)}, price is {abs(premium):.1%} below scenario-weighted fair value, so downside assumptions need checking."
        return f"At {_money(price)}, price is close to the scenario-weighted fair value and sits in the {_entry_zone_label(inputs).lower()} zone."
    return "Use this only as the market reference point once a source-backed price is available."


def _revenue_so_what(inputs: BuySideMemoInput) -> str:
    snapshot = inputs.financial_snapshot
    revenue = _safe_float(_split_metric_value(snapshot.get("Revenue", ""))[0])
    gross_profit = _safe_float(_split_metric_value(snapshot.get("Gross profit", ""))[0])
    operating_income = _safe_float(_split_metric_value(snapshot.get("Operating income", ""))[0])
    if revenue and gross_profit and operating_income:
        gross_margin = gross_profit / revenue
        operating_margin = operating_income / revenue
        return (
            f"{_compact_money(revenue)} revenue produced {_compact_money(gross_profit)} gross profit and "
            f"{_compact_money(operating_income)} operating income; {gross_margin:.1%} gross margin and "
            f"{operating_margin:.1%} operating margin show high-quality revenue conversion."
        )
    if revenue:
        return f"{_compact_money(revenue)} revenue is meaningful, but profit-conversion data is incomplete."
    return "Revenue is not source-backed yet, so growth-quality conclusions should remain limited."


def _margin_so_what(inputs: BuySideMemoInput, margin_type: str) -> str:
    label = "Gross margin" if margin_type == "gross" else "Operating margin"
    margin = _safe_float(inputs.valuation_multiples.get(label, ""))
    if margin is None:
        return f"{label} is unavailable, so this card cannot confirm pricing power or operating leverage."
    if margin_type == "gross":
        if margin >= 60:
            return f"{margin:.1f}% gross margin is exceptional; downside analysis should test whether product mix can stay this favorable."
        if margin >= 45:
            return f"{margin:.1f}% gross margin is strong; valuation support depends on durability."
        return f"{margin:.1f}% gross margin is not strong enough to justify a premium multiple by itself."
    if margin >= 50:
        return f"{margin:.1f}% operating margin means growth is converting into profit at a very high rate."
    if margin >= 30:
        return f"{margin:.1f}% operating margin is strong; test whether it survives a slower AI capex cycle."
    return f"{margin:.1f}% operating margin leaves less cushion if growth slows."


def _valuation_readiness_so_what(inputs: BuySideMemoInput) -> str:
    if _valuation_ready(inputs):
        ev_sales = inputs.valuation_multiples.get("EV/Sales", "Unavailable")
        pe = inputs.valuation_multiples.get("P/E", "Unavailable")
        return f"Fair value and entry zones are available; main supported multiples are EV/Sales {ev_sales} and P/E {pe}."
    blockers = _valuation_blockers(inputs)
    return "Valuation is blocked by " + (blockers[0] if blockers else "missing source-backed inputs.")


def _bayesian_so_what(inputs: BuySideMemoInput) -> str:
    growth = inputs.bayesian_growth.intrinsic_growth_estimate
    market_growth = inputs.bayesian_growth.market_implied_growth
    regime = inputs.bayesian_growth.most_likely_regime.value
    return (
        f"The model puts intrinsic growth at {_pct(growth)} versus market-implied growth of {_pct(market_growth)}; "
        f"the current regime read is {regime}."
    )


def _gf_dma_so_what(inputs: BuySideMemoInput) -> str:
    score = inputs.gf_dma_health.overall_gf_dma_health_score
    return f"{score:.1f}/100 suggests timing is {'healthy' if score >= 70 else 'not clean'}; use it for entry discipline, not fair value."


def _risk_tracker_so_what(inputs: BuySideMemoInput) -> str:
    validated = len([item for item in inputs.risk_opportunity_trackers if item.status == "validated"])
    pending = len([item for item in inputs.risk_opportunity_trackers if item.status == "pending"])
    high = len([item for item in inputs.risk_opportunity_trackers if item.importance == "high"])
    return f"{high} high-importance items, {validated} validated, and {pending} pending; validated risks/opportunities should update only their linked assumptions."


def _decision_metric(label: str, value: str, source_period: str, status: str, interpretation: str, decision_impact: str) -> str:
    return (
        '<article class="decision-metric">'
        f'<span class="status-dot status-{escape(status)}">{escape(status.title())}</span>'
        f"<h3>{escape(label)}</h3>"
        f'<strong>{escape(value or "Unavailable")}</strong>'
        f"<p>{escape(interpretation)}</p>"
        f"<small>{escape(source_period or 'Source/period not available')}</small>"
        f'<p class="decision-impact"><b>So what:</b> {escape(decision_impact)}</p>'
        "</article>"
    )


def _status_from_available_text(value: object) -> str:
    if not _is_available_text(value):
        return "unavailable"
    text = str(value).lower()
    if "risk" in text or "weak" in text:
        return "negative"
    return "positive"


def _metric_period_source(inputs: BuySideMemoInput, label: str) -> str:
    if label in {"Latest price", "Price timestamp", "20DMA", "50DMA", "100DMA", "200DMA", "Market cap"}:
        return f"Market data | {inputs.latest_price_timestamp}"
    return _valuation_source_note(label, inputs.valuation_multiples.get(label, ""))


def _financial_quality_summary(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    warning = ""
    if _has_mixed_period_warning(inputs):
        warning = (
            '<div class="warning-callout">'
            "<strong>Financial periods are inconsistent.</strong> This report is not valuation-ready until TTM and point-in-time inputs are reconciled."
            "</div>"
        )
    summary = _financial_quality_summary_cards(inputs, decision)
    return warning + summary


def _financial_quality_summary_cards(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    snapshot = inputs.financial_snapshot
    revenue = _safe_float(_split_metric_value(snapshot.get("Revenue", ""))[0])
    gross_profit = _safe_float(_split_metric_value(snapshot.get("Gross profit", ""))[0])
    operating_income = _safe_float(_split_metric_value(snapshot.get("Operating income", ""))[0])
    net_income = _safe_float(_split_metric_value(snapshot.get("Net income", ""))[0])
    cash = _safe_float(_split_metric_value(snapshot.get("Cash and equivalents", ""))[0])
    debt = _safe_float(_split_metric_value(snapshot.get("Total debt", ""))[0])
    operating_cash_flow = _safe_float(_split_metric_value(snapshot.get("Operating cash flow", ""))[0])

    scale_value = _compact_money(revenue) if revenue else "Unavailable"
    scale_text = (
        "Large enough that incremental upside must come from sustained AI demand, not just first-time adoption."
        if revenue and revenue >= 40_000_000_000
        else "Revenue scale needs more source-backed context before it can support a strong quality read."
    )

    if revenue and gross_profit and operating_income and net_income:
        gross_margin = gross_profit / revenue
        operating_margin = operating_income / revenue
        net_margin = net_income / revenue
        profit_value = f"GM {gross_margin:.1%} / OM {operating_margin:.1%} / NM {net_margin:.1%}"
        profit_text = (
            f"{_compact_money(gross_profit)} gross profit, {_compact_money(operating_income)} operating income, "
            f"and {_compact_money(net_income)} net income show very strong conversion from sales into earnings."
        )
    else:
        profit_value = "Unavailable"
        profit_text = "Profit-conversion data is incomplete, so margin quality should not be over-read."

    if cash is not None and debt is not None:
        balance_value = f"{_compact_money(cash)} cash / {_compact_money(debt)} debt"
        balance_text = (
            "Net cash position lowers balance-sheet stress risk."
            if cash >= debt
            else "Debt exceeds cash, so financing resilience needs closer review."
        )
    else:
        balance_value = "Unavailable"
        balance_text = "Cash and debt data are incomplete."

    cash_flow_value = _compact_money(operating_cash_flow) if operating_cash_flow else "Unavailable"
    cash_flow_text = (
        f"Operating cash flow is strong at {cash_flow_value}, but FCF remains lower-confidence until current-period capex is sourced cleanly."
        if operating_cash_flow
        else "Cash-flow quality is not yet clean enough for a confident read."
    )

    facts = (
        ("Scale", scale_value, scale_text),
        ("Profit conversion", profit_value, profit_text),
        ("Balance sheet", balance_value, balance_text),
        ("Cash-flow caveat", cash_flow_value, cash_flow_text),
        ("Evidence gaps", "Still open", _financial_quality_next_checks(inputs)),
    )
    fact_rows = "".join(
        '<div class="quality-summary-fact">'
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(value)}</strong>"
        f"<p>{escape(text)}</p>"
        "</div>"
        for label, value, text in facts
    )
    return (
        '<div class="quality-summary-panel">'
        '<div class="quality-summary-lead">'
        "<span>Financial quality read</span>"
        f"<strong>{escape(decision.business_quality_view.replace('Business quality: ', '').title())}</strong>"
        f"<p>{escape(_financial_quality_read(inputs))}</p>"
        "</div>"
        f'<div class="quality-summary-strip">{fact_rows}</div>'
        "</div>"
    )


def _financial_quality_read(inputs: BuySideMemoInput) -> str:
    gross_margin = _safe_float(inputs.valuation_multiples.get("Gross margin", ""))
    operating_margin = _safe_float(inputs.valuation_multiples.get("Operating margin", ""))
    net_margin = _safe_float(inputs.valuation_multiples.get("Net margin", ""))
    cash = _safe_float(_split_metric_value(inputs.financial_snapshot.get("Cash and equivalents", ""))[0])
    debt = _safe_float(_split_metric_value(inputs.financial_snapshot.get("Total debt", ""))[0])
    revenue = _safe_float(_split_metric_value(inputs.financial_snapshot.get("Revenue", ""))[0])

    reads: list[str] = []
    if revenue and revenue >= 50_000_000_000:
        reads.append(f"{_compact_money(revenue)} revenue means the company is already scaled; the question is durability of high growth from a large base")
    elif revenue:
        reads.append(f"{_compact_money(revenue)} revenue gives a real demand base")
    if gross_margin is not None and operating_margin is not None:
        if gross_margin >= 55 and operating_margin >= 35:
            reads.append(f"{gross_margin:.1f}% gross margin and {operating_margin:.1f}% operating margin show unusually strong profit conversion")
        elif gross_margin >= 40 and operating_margin >= 20:
            reads.append(f"{gross_margin:.1f}% gross margin and {operating_margin:.1f}% operating margin are healthy")
        else:
            reads.append("Margin quality is not yet strong enough to carry the thesis by itself")
    if net_margin is not None and net_margin >= 25:
        reads.append(f"{net_margin:.1f}% net margin supports earnings-based valuation cross-checks")
    if cash is not None and debt is not None:
        if cash >= debt:
            reads.append(f"{_compact_money(cash)} cash versus {_compact_money(debt)} debt lowers balance-sheet stress risk")
        else:
            reads.append(f"{_compact_money(debt)} debt exceeds {_compact_money(cash)} cash, so resilience needs monitoring")
    if not reads:
        return "The live dataset does not yet provide enough clean financial evidence for a confident quality read."
    return "; ".join(reads) + "."


def _financial_quality_next_checks(inputs: BuySideMemoInput) -> str:
    checks: list[str] = []
    if not _is_available_text(inputs.valuation_multiples.get("Revenue growth", "")):
        checks.append("Comparable revenue-growth history is missing")
    if not _is_available_text(inputs.valuation_multiples.get("FCF margin", "")):
        checks.append("FCF margin is blocked because current-period capex is not cleanly sourced")
    if not _is_available_text(inputs.valuation_multiples.get("EV/EBITDA", "")):
        checks.append("EV/EBITDA is unavailable because TTM EBITDA is missing")
    if not checks:
        checks.append("Next filing should confirm whether margin, cash flow, and share count are improving or deteriorating")
    return "; ".join(checks) + "."


def _valuation_section(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    if not _valuation_ready(inputs):
        blockers = _valuation_blockers(inputs)
        return (
            '<div class="warning-callout">'
            "<strong>Not decision-ready.</strong> Valuation conclusions are blocked until required inputs pass source, period, and calculation-audit checks."
            f"{_bullet_list(blockers or ('Required valuation inputs are unavailable.',))}"
            "</div>"
            '<div class="split-cards">'
            f'{_mini_card("Valuation view", decision.valuation_view)}'
            f'{_mini_card("Decision-ready status", decision.decision_ready_status.replace("_", " ").title())}'
            f'{_mini_card("Calculation audit", _calculation_audit_label(inputs))}'
            f'{_mini_card("Decision-useful quality", f"{decision.decision_quality_score:.1f}/100")}'
            "</div>"
        )
    return _scenario_cards(inputs) + _fair_value_table(inputs)


def _growth_drivers_section(inputs: BuySideMemoInput) -> str:
    driver_cards = [
        _horizontal_insight_card("AI value-chain role", inputs.ai_value_chain_classification, inputs.business_summary),
        _horizontal_insight_card("Bayesian growth", _pct(inputs.bayesian_growth.intrinsic_growth_estimate), inputs.bayesian_growth.explanation),
        _horizontal_insight_card("Moat evidence", _scored_assumption_value(inputs, "moat"), "Competitive durability score from the rubric; verify with primary source evidence."),
        _horizontal_insight_card("Next evidence to monitor", ", ".join(inputs.required_monitoring_indicators[:3]) or "Not available", "These are the next operating checks that can increase or reduce thesis confidence."),
    ]
    return '<div class="horizontal-card-list growth-driver-list">' + "".join(driver_cards) + "</div>"


def _simple_card(label: str, value: str, note: str) -> str:
    return f'<article class="card"><span class="label">{escape(label)}</span><strong>{escape(value)}</strong><p>{escape(note)}</p></article>'


def _horizontal_insight_card(label: str, value: str, note: str) -> str:
    return (
        '<article class="horizontal-card">'
        f'<div class="horizontal-card-label"><span>{escape(label)}</span></div>'
        '<div class="horizontal-card-body">'
        f"<strong>{escape(value)}</strong>"
        f"<p>{escape(note)}</p>"
        "</div>"
        "</article>"
    )


def _scored_assumption_value(inputs: BuySideMemoInput, needle: str) -> str:
    for item in inputs.scoring_rubric:
        if needle.lower() in item.name.lower():
            return f"{item.score}/5"
    return "Not available"


def _risk_validation_cards(inputs: BuySideMemoInput) -> str:
    risk_items = [item for item in inputs.risk_opportunity_trackers if item.impact_if_validated == "negative"]
    if not risk_items:
        risk_items = [item for item in inputs.risk_opportunity_trackers if item.importance == "high"]
    if not risk_items:
        return _bullet_list(inputs.risks)
    cards = []
    for item in risk_items[:8]:
        judgment = _risk_current_judgment(inputs, item)
        cards.append(
            '<article class="risk-decision-card">'
            '<div class="risk-decision-main">'
            f'<span class="status-dot status-{escape(judgment[0])}">{escape(judgment[1])}</span>'
            f"<h3>{escape(item.event_or_indicator)}</h3>"
            f'<p class="tracker-meta">{escape(item.category.title())} | {escape(item.importance.title())} importance | {escape(item.confidence.title())} confidence</p>'
            f"<p>{escape(item.why_it_matters)}</p>"
            "</div>"
            '<div class="risk-evidence-grid">'
            f'<div><strong>Current evidence</strong><span>{escape(judgment[2])}</span></div>'
            f'<div><strong>Validation / dismiss rule</strong><span>{escape(item.validation_rule)}</span></div>'
            f'<div><strong>Research response</strong><span>{escape(item.suggested_research_response)}</span></div>'
            f'<div><strong>Source basis</strong><span>{escape(judgment[3])}</span></div>'
            "</div>"
            "</article>"
        )
    return '<div class="risk-decision-list">' + "".join(cards) + "</div>"


def _risk_current_judgment(inputs: BuySideMemoInput, item: RiskOpportunityTrackerItem) -> tuple[str, str, str, str]:
    if item.status == "validated":
        return (
            "negative" if item.impact_if_validated == "negative" else "positive",
            "Validated signal",
            item.evidence_summary or "A high-confidence official or primary source matched this tracker item.",
            item.source_url or ", ".join(item.source_priority) or "Source not available",
        )
    if item.status == "invalidated":
        return (
            "positive",
            "Dismissed for now",
            item.evidence_summary or "Current source evidence does not support this risk signal.",
            item.source_url or ", ".join(item.source_priority) or "Source not available",
        )
    if item.status == "pending":
        return (
            "unavailable",
            "Pending evidence",
            item.evidence_summary if item.evidence_summary and "Pending" not in item.evidence_summary else "No source-backed validation yet; wait for the rule evidence before changing assumptions.",
            ", ".join(item.source_priority) or "Source not available",
        )
    if item.category == "macro":
        macro_readout = _macro_readout_for_item(inputs, item)
        return (
            "neutral",
            "Monitoring",
            macro_readout or "Macro connector is available, but this tracker needs persistence before it changes the thesis.",
            ", ".join(item.source_priority) or "FRED / Treasury data",
        )
    if item.category == "technical":
        return (
            "neutral",
            "Monitoring",
            f"{inputs.gf_dma_health.explanation} Treat this as timing and entry-discipline evidence, not intrinsic value.",
            ", ".join(item.source_priority) or "Market data",
        )
    return (
        "neutral",
        item.status.replace("_", " ").title(),
        item.evidence_summary or "Monitor the next source update before changing assumptions.",
        ", ".join(item.source_priority) or "Source not available",
    )


def _macro_readout_for_item(inputs: BuySideMemoInput, item: RiskOpportunityTrackerItem) -> str:
    item_name = item.event_or_indicator.lower()
    for readout in inputs.macro_industry_tracker:
        lowered = readout.lower()
        if "10-year" in item_name and "10-year" in lowered:
            return readout
        if "vix" in item_name and "vix" in lowered:
            return readout
        if "dxy" in item_name and "dxy" in lowered:
            return readout
    return ""


def _entry_framework_section(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    technical = f"<p><strong>Timing-only read:</strong> {escape(inputs.gf_dma_health.explanation)}</p>"
    if not _valuation_ready(inputs):
        return (
            '<div class="warning-callout">'
            "<strong>Entry framework unavailable until valuation inputs pass audit.</strong> Moving-average and GF-DMA data can still help with timing discipline, but they do not estimate intrinsic value."
            "</div>"
            f"{technical}"
        )
    return _entry_zone_table(inputs) + technical


def _scenario_analysis_section(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    if not _valuation_ready(inputs):
        return (
            '<div class="warning-callout">'
            "<strong>Scenario analysis is not valuation-ready.</strong> Bear/base/bull cases remain placeholders until TTM denominators and source-backed valuation inputs are available."
            "</div>"
            + _scenario_cards(inputs)
        )
    return _scenario_cards(inputs) + _fair_value_table(inputs)


def _model_detail_section(inputs: BuySideMemoInput) -> str:
    tam_assumption_section = _tam_assumption_section(inputs)
    return (
        f"{_model_detail_intro()}"
        '<div id="bayesian-growth" class="model-subsection"><h3>Bayesian growth</h3>'
        f"{_bayesian_evidence_intro() + _bayesian_table(inputs)}</div>"
        '<div id="bayesian-growth-evidence-table" class="model-subsection"><h3>Bayesian Growth Evidence Table</h3>'
        f"{_evidence_table(inputs.bayesian_growth_evidence)}</div>"
        '<div id="tam-adjusted-peg-view" class="model-subsection"><h3>TAM-adjusted PEG view</h3>'
        f"{_tam_model_explainer() + _tam_table(inputs)}</div>"
        f"{tam_assumption_section}"
        '<div id="scoring-rubric-table" class="model-subsection"><h3>Scoring Rubric Table</h3>'
        f"{_scoring_rubric_explainer() + _scoring_table(inputs)}</div>"
        '<div id="gf-dma-health-view" class="model-subsection"><h3>GF-DMA health view</h3>'
        f"{_gf_dma_explainer() + _gf_dma_table(inputs)}</div>"
        '<div id="macro-and-industry-tracker" class="model-subsection"><h3>Macro and industry tracker</h3>'
        f"{_macro_tracker(inputs)}</div>"
        '<div id="recent-validated-developments" class="model-subsection"><h3>Recent validated developments</h3>'
        f"{_bullet_list(inputs.recent_validated_developments)}</div>"
        '<div id="pending-signals" class="model-subsection"><h3>Pending signals</h3>'
        f"{_bullet_list(inputs.pending_signals)}</div>"
        '<div id="what-changed-since-last-review" class="model-subsection"><h3>What changed since last review</h3>'
        f"{_change_table(inputs)}</div>"
        '<div id="what-would-change-the-view" class="model-subsection"><h3>What would change the view</h3>'
        f"{_bullet_list(inputs.view_change_triggers)}</div>"
    )


def _tam_assumption_section(inputs: BuySideMemoInput) -> str:
    if not _visible_evidence_items(inputs.tam_assumptions):
        return ""
    return (
        '<div id="tam-adjusted-peg-assumption-table" class="model-subsection"><h3>TAM-Adjusted PEG Assumption Table</h3>'
        f"{_evidence_table(inputs.tam_assumptions)}</div>"
    )


def _model_detail_intro() -> str:
    return (
        '<div class="model-explainer model-stack-intro">'
        "<h3>Why this model stack matters</h3>"
        "<p>"
        "AI stocks can look expensive on current earnings while still carrying real option value from new demand cycles. "
        "Using several models keeps the memo from depending on one lens: valuation checks what is priced in, Bayesian growth tests whether evidence supports a stronger regime, TAM-adjusted PEG checks whether growth quality can justify the multiple, and GF-DMA separates timing health from intrinsic value."
        "</p>"
        "<p>"
        "Use the stack as a decision checklist. A clearer view requires alignment between source-backed financials, growth evidence, valuation support, tracker status, and timing discipline."
        "</p>"
        "</div>"
    )


def _scoring_rubric_explainer() -> str:
    return (
        '<div class="model-explainer">'
        "<h3>How to read these scores</h3>"
        "<p>"
        "The scoring rubric turns qualitative AI-stock questions into a structured checklist. "
        "A 5/5 score means the evidence strongly supports that dimension; a lower score means the thesis needs more proof or carries more risk."
        "</p>"
        "<p>"
        "Use these scores to understand why the TAM-adjusted PEG moved up or down. "
        "Runway, business quality, pricing power, recurring revenue, and moat can support a premium multiple, while cyclicality, dilution, customer concentration, and execution risk reduce support."
        "</p>"
        "</div>"
    )


def _audit_appendix(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    return (
        '<div id="data-source-status" class="appendix-block"><h3>Data Source Status</h3>'
        f"{_data_source_status_table(inputs)}</div>"
        '<div id="calculation-audit-status" class="appendix-block"><h3>Calculation Audit Status</h3>'
        f"{_calculation_audit_card(inputs)}</div>"
        '<div id="data-coverage" class="appendix-block"><h3>Data Coverage</h3>'
        f"{_data_coverage_card(inputs)}</div>"
        '<div id="data-coverage-needed-to-improve-this-memo" class="appendix-block"><h3>Data Coverage Needed to Improve This Memo</h3>'
        f"{_coverage_needed(inputs)}</div>"
        '<div id="period-reconciliation" class="appendix-block"><h3>Period reconciliation warnings</h3>'
        f"{_period_basis_table(inputs)}</div>"
        '<div id="missing-evidence-low-confidence-warnings" class="appendix-block"><h3>Missing Evidence / Low Confidence Warnings</h3>'
        f"{_bullet_list(_visible_low_confidence_warnings(inputs.low_confidence_warnings))}</div>"
        '<div id="data-quality-and-confidence-level" class="appendix-block"><h3>Data quality and confidence level</h3>'
        f"{_quality_table(inputs, decision)}</div>"
        '<div id="sources" class="appendix-block"><h3>Sources</h3>'
        f"{_bullet_list(inputs.sources)}</div>"
        '<div id="official-sources-discovered" class="appendix-block"><h3>Official sources discovered</h3>'
        f"{_search_result_cards(inputs, official_only=True)}</div>"
        '<div id="anysearch-query-log" class="appendix-block"><h3>AnySearch query log</h3>'
        f"{_bullet_list(inputs.anysearch_query_log)}</div>"
    )


def _visible_low_confidence_warnings(warnings: tuple[str, ...]) -> tuple[str, ...]:
    visible = tuple(
        warning
        for warning in warnings
        if not (
            "forward eps growth" in warning.lower()
            and ("fmp" in warning.lower() or "structured estimates provider" in warning.lower())
        )
    )
    return visible or ("No non-optional low-confidence warnings are currently displayed.",)


def _data_source_status_table(inputs: BuySideMemoInput) -> str:
    rows = "".join(
        "<tr>"
        f"<th>{escape(item.category)}</th>"
        f'<td><span class="source-status source-{_source_status_class(item.configured)}">{escape(item.configured.title())}</span></td>'
        f'<td><span class="source-status source-{_source_status_class(item.used)}">{escape(item.used.title())}</span></td>'
        f'<td><span class="source-status source-{_source_status_class(item.availability)}">{escape(item.availability.title())}</span></td>'
        f"<td>{escape(item.reason)}</td>"
        f"<td>{escape(item.last_successful_retrieval)}</td>"
        "</tr>"
        for item in inputs.data_source_status
    )
    return (
        '<div class="table-wrap"><table class="source-status-table">'
        "<tr><th>Provider</th><th>Configured</th><th>Used</th><th>Available</th><th>Reason</th><th>Last successful retrieval</th></tr>"
        f"{rows}</table></div>"
    )


def _period_basis_table(inputs: BuySideMemoInput) -> str:
    if not inputs.period_basis_rows:
        return '<p class="subtle">No fiscal-period basis rows generated.</p>'
    rows = "".join(
        "<tr>"
        f"<th>{escape(row.metric)}</th>"
        f"<td>{escape(row.period_basis)}</td>"
        f"<td>{escape(row.source)}</td>"
        f"<td>{escape(row.periods_used)}</td>"
        f"<td>{escape(row.warning or 'None')}</td>"
        "</tr>"
        for row in inputs.period_basis_rows
    )
    return (
        '<div class="table-wrap"><table>'
        "<tr><th>Metric</th><th>Period basis</th><th>Source</th><th>Periods used</th><th>Warning</th></tr>"
        f"{rows}</table></div>"
        '<p class="subtle">Valuation multiples default to TTM financial denominators. If four comparable quarters are unavailable, only the affected metric is marked unavailable.</p>'
    )


def _financial_snapshot_cards(inputs: BuySideMemoInput) -> str:
    cards = []
    for label, raw_value in inputs.financial_snapshot.items():
        figure, source_note = _split_metric_value(raw_value)
        cards.append(
            '<article class="figure-card">'
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(_format_financial_figure(label, figure))}</strong>"
            f"<p>{escape(_financial_insight(label, figure, inputs.financial_snapshot))}</p>"
            f"<small>{escape(source_note)}</small>"
            "</article>"
        )
    return '<div class="figure-grid">' + "".join(cards) + "</div>"


def _valuation_multiple_cards(inputs: BuySideMemoInput) -> str:
    cards = []
    for label, value in inputs.valuation_multiples.items():
        if _hide_optional_fmp_metric(label, value):
            continue
        cards.append(
            '<article class="figure-card valuation-card">'
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(_format_valuation_figure(label, value))}</strong>"
            f"<p>{escape(_valuation_insight(label, value, inputs))}</p>"
            f"<small>{escape(_valuation_source_note(label, value))}</small>"
            "</article>"
        )
    return '<h3>Valuation multiples</h3>' + _valuation_multiples_summary(inputs) + '<div class="figure-grid">' + "".join(cards) + "</div>"


def _valuation_multiples_summary(inputs: BuySideMemoInput) -> str:
    pe = _safe_float(inputs.valuation_multiples.get("P/E", ""))
    ev_sales = _safe_float(inputs.valuation_multiples.get("EV/Sales", ""))
    fcf_margin = _safe_float(inputs.valuation_multiples.get("FCF margin", "").replace("%", ""))
    price = _safe_float(inputs.valuation_multiples.get("Latest price", ""))
    reads: list[str] = []
    if ev_sales is not None:
        if ev_sales >= 15:
            reads.append("EV/Sales is premium, so revenue growth durability matters more than one-period scale")
        elif ev_sales >= 8:
            reads.append("EV/Sales is elevated and needs strong margin support")
        else:
            reads.append("EV/Sales is not the main stretch point")
    if pe is not None:
        if pe >= 45:
            reads.append("P/E embeds a demanding earnings-growth path")
        elif pe >= 25:
            reads.append("P/E is elevated but can be coherent if margins and estimate revisions hold")
        else:
            reads.append("P/E is not especially stretched versus high-growth technology peers")
    if fcf_margin is not None:
        reads.append("FCF margin looks strong but should be source-reconciled before anchoring valuation")
    if price and inputs.fair_value_per_share > 0:
        premium = price / inputs.fair_value_per_share - 1
        if premium > 0.10:
            reads.append("current price sits above the scenario-weighted fair value")
        elif premium < -0.10:
            reads.append("current price sits below the scenario-weighted fair value")
        else:
            reads.append("current price is near the scenario-weighted fair value")
    if not reads:
        reads.append("valuation is still limited by missing or period-incompatible inputs")
    return (
        '<div class="decision-box valuation-summary-box">'
        f"<p><strong>Valuation read:</strong> {escape('; '.join(reads))}.</p>"
        "<p><strong>Use carefully:</strong> multiples are decision-useful only when the denominator period is clean and source-backed; missing metrics should not be filled by guesswork.</p>"
        "</div>"
    )


def _split_metric_value(raw_value: str) -> tuple[str, str]:
    parts = [part.strip() for part in str(raw_value).split("|")]
    figure = parts[0] if parts else str(raw_value)
    source = ""
    period = ""
    for part in parts[1:]:
        if part.lower().startswith("source:"):
            source = part.split(":", 1)[1].strip()
        elif part.lower().startswith("period:"):
            period = part.split(":", 1)[1].strip()
    note = "Not available from current sources"
    if source or period:
        note = " | ".join(item for item in (source, period) if item)
    return figure, note


def _format_financial_figure(label: str, figure: str) -> str:
    number = _safe_float(figure)
    if number is None:
        return figure
    if "EPS" in label:
        return f"${number:,.2f}"
    if "Shares" in label:
        return f"{number / 1_000_000_000:.2f}B"
    return _compact_money(number)


def _format_valuation_figure(label: str, value: str) -> str:
    if "Unavailable:" in str(value) or "Not available" in str(value):
        return "Unavailable"
    if label in {"Market cap", "Enterprise value"}:
        number = _safe_float(value)
        return _compact_money(number) if number is not None else value
    if label == "Latest price":
        number = _safe_float(value)
        return _money(number) if number is not None else value
    return value


def _financial_insight(label: str, figure: str, snapshot: dict[str, str]) -> str:
    value = _safe_float(figure)
    if value is None:
        return "Missing source field; do not draw a financial-quality conclusion from this metric yet."
    revenue = _safe_float(_split_metric_value(snapshot.get("Revenue", ""))[0])
    gross_profit = _safe_float(_split_metric_value(snapshot.get("Gross profit", ""))[0])
    operating_income = _safe_float(_split_metric_value(snapshot.get("Operating income", ""))[0])
    net_income = _safe_float(_split_metric_value(snapshot.get("Net income", ""))[0])
    cash = _safe_float(_split_metric_value(snapshot.get("Cash and equivalents", ""))[0])
    debt = _safe_float(_split_metric_value(snapshot.get("Total debt", ""))[0])
    if label == "Revenue":
        if gross_profit and operating_income and revenue:
            return (
                f"{_compact_money(value)} revenue produced {_compact_money(gross_profit)} gross profit "
                f"and {_compact_money(operating_income)} operating income; that is high-margin demand, not low-quality volume."
            )
        if value >= 100_000_000_000:
            return f"{_compact_money(value)} revenue is already very large, so sustaining high growth from this base is the core test."
        return f"{_compact_money(value)} revenue is a meaningful demand base, but margin conversion is not fully sourced here."
    if label == "Gross profit" and revenue:
        margin = gross_profit / revenue
        if margin >= 0.55:
            return f"Gross margin is {margin:.1%}; this is a strong quality signal, but watch product mix and supply costs."
        return f"Gross margin is {margin:.1%}; acceptable, but not enough by itself to prove pricing power."
    if label == "Operating income" and revenue:
        margin = operating_income / revenue
        if margin >= 0.30:
            return f"Operating margin is {margin:.1%}; operating leverage looks strong if this period is comparable."
        return f"Operating margin is {margin:.1%}; monitor whether growth is translating into operating profit."
    if label == "Net income" and revenue:
        margin = net_income / revenue
        if margin >= 0.25:
            return f"Net margin is {margin:.1%}; earnings conversion is strong, supporting P/E-based cross-checks."
        return f"Net margin is {margin:.1%}; earnings conversion needs improvement before valuation support is strong."
    if label == "Cash and equivalents":
        if debt is not None and value >= debt:
            return "Cash is above total debt; balance-sheet risk is not the main constraint in this memo."
        return "Cash balance is useful, but compare it with debt, capex, and supply commitments."
    if label == "Total debt":
        if cash is not None and cash >= value:
            return "Debt is covered by cash; leverage does not appear to dominate the risk case."
        return "Debt needs monitoring against cash and free-cash-flow resilience."
    if label == "Operating cash flow":
        return "Operating cash flow is the cleaner cash-generation signal; reconcile working capital before extrapolating."
    if label == "Capital expenditure":
        _, source_note = _split_metric_value(snapshot.get(label, ""))
        if "2019" in source_note or "unavailable" in source_note.lower():
            return "Capex evidence looks stale or incomplete; avoid relying on FCF until current-period capex is sourced."
        return "Capex intensity is central to cash conversion; compare it with operating cash flow for the same period."
    if label == "Free cash flow":
        return "Free cash flow is useful only after CFO and capex periods match; fallback values should be treated cautiously."
    if label == "Shares outstanding":
        return "Share count affects every per-share output; monitor buybacks or dilution before comparing fair-value ranges."
    if label == "Diluted EPS":
        return "EPS is a helpful earnings anchor, but use matching-period earnings for valuation multiples."
    return "Use this figure as supporting evidence only after period, source, and scale checks are clear."


def _valuation_insight(label: str, value: str, inputs: BuySideMemoInput) -> str:
    if "Unavailable:" in str(value) or "Not available" in str(value):
        return _valuation_missing_insight(label)
    latest_price = _safe_float(inputs.valuation_multiples.get("Latest price", ""))
    current_value = _safe_float(value)
    if label == "Latest price":
        zone = _entry_zone_label(inputs)
        if inputs.fair_value_per_share > 0 and latest_price:
            premium = latest_price / inputs.fair_value_per_share - 1
            if premium > 0.10:
                return f"Price is {premium:.1%} above the scenario-weighted fair value; valuation compression risk is central."
            if premium < -0.10:
                return f"Price is {abs(premium):.1%} below the scenario-weighted fair value; confirm downside assumptions before leaning on the gap."
        return f"Current price places the entry framework in the {zone.lower()} zone."
    if label == "Price timestamp":
        return "Freshness check: stale prices can distort entry-zone and GF-DMA reads."
    if label.endswith("DMA") and latest_price is not None and current_value:
        direction = "above" if latest_price > current_value else "below"
        distance = abs(latest_price / current_value - 1)
        if distance >= 0.10 and direction == "above":
            return f"Price is {distance:.1%} above this moving average; trend is strong but timing risk is elevated."
        if direction == "below":
            return f"Price is {distance:.1%} below this moving average; trend support is weakening."
        return f"Price is {distance:.1%} {direction} this moving average; trend signal is moderate."
    if label == "Market cap":
        return "Market value is large, so small changes in growth or margin assumptions can move fair-value conclusions materially."
    if label == "Enterprise value":
        return "Enterprise value is close to the market's total business value after debt and cash; compare it with TTM sales and earnings."
    if label == "EV/Sales":
        if current_value and current_value >= 15:
            return "Premium sales multiple; the market is underwriting durable AI growth and high margin retention."
        if current_value and current_value >= 8:
            return "Elevated sales multiple; growth needs to stay strong to support the valuation."
        return "Sales multiple is not extreme, but still needs margin and growth confirmation."
    if label == "EV/EBITDA":
        if current_value and current_value >= 25:
            return "High operating-earnings multiple; downside case should include multiple compression."
        return "EBITDA multiple appears moderate only if EBITDA is clean and TTM-aligned."
    if label == "P/E":
        if current_value and current_value >= 45:
            return "High earnings multiple; margin durability and estimate revisions must keep confirming the thesis."
        if current_value and current_value >= 25:
            return "Elevated but not unusual for a high-growth AI leader; still vulnerable to compression."
        return "P/E is moderate relative to high-growth tech, but check earnings cyclicality."
    if label == "P/FCF":
        if current_value and current_value >= 40:
            return "High cash-flow multiple; confidence depends on clean FCF and continued cash conversion."
        return "Cash-flow multiple is more useful after SEC cash-flow periods are reconciled."
    if label == "P/S":
        if current_value and current_value >= 15:
            return "Premium sales valuation; revenue growth and margin durability need to remain exceptional."
        return "Sales valuation is less stretched, but still needs growth-quality support."
    if label == "Gross margin":
        if current_value and current_value >= 55:
            return "Very strong margin profile; supports pricing power, but watch for mix or supply-cost pressure."
        return "Margin profile needs improvement before it can support a premium valuation alone."
    if label == "Operating margin":
        if current_value and current_value >= 35:
            return "Strong operating leverage; downside case should test margin normalization."
        return "Operating leverage is not yet high enough to remove execution risk."
    if label == "Net margin":
        if current_value and current_value >= 25:
            return "Strong earnings conversion; P/E support depends on sustaining this level."
        return "Net margin is a watch item for earnings-quality support."
    if label == "FCF margin":
        if current_value and current_value >= 25:
            return "Strong apparent cash conversion, but rely on it only after CFO and capex periods are reconciled."
        return "Cash conversion is not strong enough or not clean enough to anchor valuation."
    if label == "Diluted EPS":
        return "EPS supports P/E analysis only when matched to the same period as price and shares."
    return "Valuation input to interpret alongside source quality, growth, and downside scenarios."


def _valuation_missing_insight(label: str) -> str:
    missing = {
        "Revenue growth": "Needs multi-period sourced revenue history before growth valuation can be updated.",
        "Analyst EPS growth": "Needs a structured estimate provider or an explicit model assumption before PEG can be calculated.",
        "Earnings date": "Needs IR or market-data calendar extraction; do not infer the next event date.",
    }
    return missing.get(label, "Unavailable input; keep the source gap visible instead of estimating silently.")


def _valuation_source_note(label: str, value: str) -> str:
    if "Unavailable:" in str(value) or "Not available" in str(value):
        return value
    if label in {"Latest price", "Price timestamp", "20DMA", "50DMA", "100DMA", "200DMA", "Market cap"}:
        return "Market data"
    if label in {"Enterprise value", "EV/Sales", "EV/EBITDA", "P/E", "P/FCF", "P/S"}:
        return "Calculated from sourced market and financial inputs"
    if label in {"Gross margin", "Operating margin", "Net margin", "FCF margin", "Diluted EPS"}:
        return "Calculated or sourced from financial inputs"
    return "Source-backed input"


def _coverage_needed(inputs: BuySideMemoInput) -> str:
    statuses = {item.category: item for item in inputs.data_source_status}
    items: list[str] = []
    if statuses.get("yfinance") and statuses["yfinance"].configured == "missing":
        items.append("Install yfinance to enable the primary free/no-key market-data and fallback financials path.")
    if statuses.get("yahooquery") and statuses["yahooquery"].configured == "missing":
        items.append("Install yahooquery to enable the backup free/no-key market-data and fallback financials path.")
    if statuses.get("SEC EDGAR") and statuses["SEC EDGAR"].configured == "missing":
        items.append("Add SEC_USER_AGENT to verify financial statement data against SEC EDGAR.")
    anysearch_status = statuses.get("AnySearch Skill / source cache") or statuses.get("AnySearch")
    if anysearch_status and anysearch_status.configured == "missing":
        items.append("Run Codex AnySearch discovery, save outputs/source_cache/{TICKER}.json, and rerun with --use-source-cache to populate catalysts, official source discovery, and tracker evidence.")
    if not items:
        items.append("Core free/no-key providers are available. Optional improvements include FMP for premium coverage and official industry connectors for SIA, SEMI, WSTS, TSMC monthly revenue, and hyperscaler capex extraction.")
    return _bullet_list(tuple(items))


def _data_coverage_card(inputs: BuySideMemoInput) -> str:
    statuses = {item.category: item for item in inputs.data_source_status}
    price_source = _first_used_status(statuses, ("yfinance", "yahooquery", "FMP optional", "FMP", "EODHD", "Alpha Vantage"))
    financial_sources = _used_status_names(statuses, ("SEC EDGAR", "yfinance", "yahooquery", "FMP optional", "FMP"))
    macro_source = _first_used_status(statuses, ("FRED",))
    news_source = _first_used_status(statuses, ("AnySearch Skill / source cache", "AnySearch", "Company IR"))
    unavailable = [
        f"{key}: {value}"
        for key, value in {**inputs.financial_snapshot, **inputs.valuation_multiples}.items()
        if "Unavailable:" in str(value) or "Not available from current sources" in str(value)
        if not _hide_optional_fmp_metric(key, value)
    ][:8]
    if not unavailable:
        unavailable = ["No major displayed fields are marked unavailable in the current memo."]
    return (
        '<div class="split-cards">'
        f'{_mini_card("Price data", price_source or "Unavailable from current providers")}'
        f'{_mini_card("Financials", ", ".join(financial_sources) if financial_sources else "Unavailable from current providers")}'
        f'{_mini_card("Macro", macro_source or "Unavailable from current providers")}'
        f'{_mini_card("News / tracker", news_source or "Unavailable unless source cache or IR links are available")}'
        "</div>"
        "<h3>Unavailable Fields</h3>"
        f"{_bullet_list(tuple(unavailable))}"
    )


def _hide_optional_fmp_metric(label: str, value: object) -> bool:
    """Hide fields that only exist when the optional FMP upgrade is configured."""

    if _is_available_text(value):
        return False
    normalized = label.strip().lower()
    return normalized in {"analyst eps growth", "earnings date"}


def _first_used_status(statuses: dict[str, object], names: tuple[str, ...]) -> str:
    for name in names:
        item = statuses.get(name)
        if item and getattr(item, "used", "") == "used":
            return name
    return ""


def _used_status_names(statuses: dict[str, object], names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in names if statuses.get(name) and getattr(statuses[name], "used", "") == "used")


def _scenario_cards(inputs: BuySideMemoInput) -> str:
    cards = []
    for scenario in inputs.valuation_scenarios:
        cards.append(
            '<article class="scenario-card">'
            f"<span>{escape(scenario.name)}</span>"
            f"<strong>{_money_or_unavailable(scenario.fair_value_per_share)}</strong>"
            f"<p>Enterprise value {_money_or_unavailable(scenario.enterprise_value)}; probability {_pct(scenario.probability)}</p>"
            "</article>"
        )
    return '<div class="scenario-grid">' + "\n".join(cards) + "</div>"


def _fair_value_table(inputs: BuySideMemoInput) -> str:
    return (
        '<div class="callout">Probability-weighted fair value: '
        f"<strong>{_money_or_unavailable(inputs.fair_value_per_share)}</strong>. "
        f"Fair value range: <strong>{_money_or_unavailable(min(s.fair_value_per_share for s in inputs.valuation_scenarios))} to {_money_or_unavailable(max(s.fair_value_per_share for s in inputs.valuation_scenarios))}</strong>. "
        "Use this as a scenario reference point, not as an instruction to transact.</div>"
    )


def _bayesian_table(inputs: BuySideMemoInput) -> str:
    rows = "".join(
        "<tr>"
        f"<th>{escape(hypothesis.name)}: {escape(hypothesis.value)}</th>"
        f"<td>{_pct(prior)}</td>"
        f"<td>{_pct(inputs.bayesian_growth.updated_probabilities[hypothesis])}</td>"
        "</tr>"
        for hypothesis, prior in inputs.bayesian_growth.prior_probabilities.items()
    )
    summary = (
        f"<p>{escape(inputs.bayesian_growth.explanation)}</p>"
        '<div class="split-cards">'
        f'{_mini_card("Intrinsic growth", _pct(inputs.bayesian_growth.intrinsic_growth_estimate))}'
        f'{_mini_card("Market-implied growth", _pct(inputs.bayesian_growth.market_implied_growth))}'
        "</div>"
        f"<p class=\"subtle\">Market-implied comparison: {escape(inputs.bayesian_growth.market_implied_comparison)}</p>"
        f"{_bayesian_evidence_gap(inputs)}"
    )
    return f'<div class="table-wrap"><table><tr><th>Hypothesis</th><th>Prior</th><th>Updated</th></tr>{rows}</table></div>{summary}'


def _bayesian_evidence_gap(inputs: BuySideMemoInput) -> str:
    unchanged = all(
        abs(inputs.bayesian_growth.updated_probabilities[hypothesis] - prior) < 0.0001
        for hypothesis, prior in inputs.bayesian_growth.prior_probabilities.items()
    )
    if not unchanged:
        return ""
    items = (
        "Revenue growth trend: needs multi-quarter or year-over-year source-backed revenue history from SEC/company IR.",
        "Margin trend: needs gross and operating margin trend by period, not just the latest quarter.",
        "FCF trend: SEC matching-period capex is incomplete; reconcile operating cash flow and capex before using FCF evidence.",
        "Demand evidence: needs confirmed hyperscaler capex, backlog/RPO, signed contracts, or customer commitments from filings/IR.",
        "Estimate revisions: needs a structured estimates source; AnySearch/news should not change Bayesian probabilities by itself.",
    )
    return (
        '<div class="callout"><strong>Evidence gap:</strong> Bayesian probabilities remain close to priors because the live dataset does not yet provide enough validated trend evidence. '
        "Use the sources below before increasing high-growth probabilities."
        f"{_bullet_list(items)}</div>"
    )


def _tam_table(inputs: BuySideMemoInput) -> str:
    if inputs.tam_adjusted_peg.quality_adjusted_interpretation == "Not available from current sources":
        return (
            '<div class="split-cards">'
            f'{_mini_card("Traditional PEG", "Not available from current sources")}'
            f'{_mini_card("TAM-adjusted PEG", "Not available from current sources")}'
            "</div>"
            f"<p><strong>Growth quality valuation check:</strong> {escape(inputs.tam_adjusted_peg.quality_adjusted_interpretation)}</p>"
            f"<p>{escape(inputs.tam_adjusted_peg.explanation)}</p>"
            f"{_tam_missing_inputs(inputs)}"
        )
    return (
        '<div class="split-cards">'
        f'{_mini_card("Traditional PEG", f"{inputs.tam_adjusted_peg.traditional_peg:.2f}x")}'
        f'{_mini_card("TAM-adjusted PEG", f"{inputs.tam_adjusted_peg.tam_adjusted_peg:.2f}x")}'
        "</div>"
        f"<p><strong>Growth quality valuation check:</strong> {escape(inputs.tam_adjusted_peg.quality_adjusted_interpretation)}</p>"
        f'<div class="callout"><strong>Insights:</strong> {escape(_peg_plain_english(inputs))}</div>'
    )


def _peg_plain_english(inputs: BuySideMemoInput) -> str:
    peg = inputs.tam_adjusted_peg.traditional_peg
    adjusted = inputs.tam_adjusted_peg.tam_adjusted_peg
    if peg <= 0 or adjusted <= 0:
        return "PEG cannot be interpreted until P/E and expected EPS growth are available."
    if adjusted < 1.0:
        stance = "growth appears inexpensive relative to the scored runway"
    elif adjusted < 1.6:
        stance = "growth support looks broadly fair, but still depends on evidence quality"
    elif adjusted < 2.3:
        stance = "the stock is expensive on growth-adjusted terms, but strong TAM and quality scores may partly justify it"
    else:
        stance = "valuation looks expensive and needs stronger source-backed growth evidence"
    delta = "improves" if adjusted < peg else "worsens"
    return (
        f"Traditional PEG compares the P/E multiple with expected EPS growth. "
        f"Here it is {peg:.2f}x. The TAM-adjusted version {delta} that reading after considering runway, quality, cyclicality, dilution, and execution risk, landing at {adjusted:.2f}x. "
        f"In plain English, {stance}. This is a valuation-quality check, not a transaction signal."
    )


def _tam_missing_inputs(inputs: BuySideMemoInput) -> str:
    pe = inputs.valuation_multiples.get("P/E", "")
    items = [
        "Expected EPS growth: missing structured forward EPS-growth estimate or explicit analyst assumption.",
        "TAM runway score: needs analyst-defined TAM/SAM assumptions for AI accelerators, networking, and AI factory systems.",
        "Business quality score: needs explicit pricing power, gross-margin durability, and recurring/software mix assumptions.",
        "Risk penalties: needs scored cyclicality, customer concentration, dilution, execution, and moat inputs.",
    ]
    if "Unavailable" not in pe:
        items.insert(0, f"P/E is available ({pe}), but PEG cannot be calculated until expected EPS growth is sourced or explicitly modeled.")
    return '<div class="callout"><strong>Missing TAM-adjusted PEG inputs:</strong>' + _bullet_list(tuple(items)) + "</div>"


def _evidence_table(items: tuple[object, ...]) -> str:
    visible_items = _visible_evidence_items(items)
    if not visible_items:
        return '<div class="evidence-card-list"><article class="evidence-card"><p class="subtle">No evidence rows generated.</p></article></div>'
    cards = "".join(_evidence_card(item) for item in visible_items)
    return f'<div class="evidence-card-list">{cards}</div>'


def _visible_evidence_items(items: tuple[object, ...]) -> tuple[object, ...]:
    return tuple(item for item in items if not _hide_optional_fmp_evidence_item(item))


def _hide_optional_fmp_evidence_item(item: object) -> bool:
    text = " ".join(
        str(getattr(item, attr, ""))
        for attr in ("name", "value", "warning", "explanation", "source", "evidence")
    ).lower()
    return "forward eps growth" in text and ("fmp" in text or "structured estimates provider" in text)


def _evidence_card(item: object) -> str:
    name = getattr(item, "name", "Evidence")
    value = getattr(item, "value", "")
    confidence = getattr(item, "confidence", "low")
    warning = getattr(item, "warning", "") or "None"
    explanation = getattr(item, "explanation", "")
    source = getattr(item, "source", "") or getattr(item, "evidence", "")
    detail = explanation or source
    detail_html = ""
    if detail:
        detail_html = (
            '<details class="evidence-detail">'
            "<summary>Evidence basis</summary>"
            f"<p>{escape(_shorten_text(str(detail), 360))}</p>"
            "</details>"
        )
    return (
        '<article class="evidence-card">'
        '<div class="evidence-card-head">'
        "<div>"
        f"<span>{escape(str(name))}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</div>"
        f'<span class="source-status source-quality-{escape(str(confidence).lower())}">{escape(str(confidence).title())} confidence</span>'
        "</div>"
        f"<p><strong>Insights:</strong> {escape(_evidence_interpretation(item))}</p>"
        f"<p class=\"subtle\"><strong>Warning:</strong> {escape(str(warning))}</p>"
        f"{detail_html}"
        "</article>"
    )


def _bayesian_evidence_intro() -> str:
    return (
        '<div class="model-explainer">'
        "<h3>What this model is doing</h3>"
        "<p>"
        "This section asks a simple question: are the company's real business signals strong enough to support a higher growth outlook over the next three to five years? "
        "The model starts with baseline odds for several growth regimes, then looks for evidence that should move those odds up or down."
        "</p>"
        "<p>"
        "Use it as a thesis-confidence map, not a price target. Revenue growth shows whether demand is expanding, margins show whether the company keeps enough profit from that growth, free cash flow shows whether growth is turning into cash, and estimate revisions show whether outside analysts are also updating expectations. "
        "Probabilities should move only when source-backed evidence changes."
        "</p>"
        "</div>"
    )


def _tam_model_explainer() -> str:
    return (
        '<div class="model-explainer">'
        "<h3>What TAM-adjusted PEG checks</h3>"
        "<p>"
        "Traditional PEG compares the P/E multiple with expected EPS growth. TAM-adjusted PEG asks whether the growth is high-quality enough to deserve a better reading: larger runway, stronger margins, pricing power, recurring revenue, and moat lower the adjusted PEG, while cyclicality, dilution, concentration, and execution risk raise it."
        "</p>"
        "<p>"
        "Use it to judge whether a premium multiple has enough growth-quality support. It is a valuation-quality check, not a transaction signal."
        "</p>"
        "</div>"
    )


def _gf_dma_explainer() -> str:
    return (
        '<div class="model-explainer">'
        "<h3>How to use GF-DMA</h3>"
        "<p>"
        "GF-DMA combines growth fundamentals with moving-average trend health. It asks whether price action is supported by revenue, EPS, FCF, estimate revisions, and trend structure."
        "</p>"
        "<p>"
        "Use it for timing discipline and overextension risk. It does not estimate intrinsic value and should not override the valuation or growth evidence."
        "</p>"
        "</div>"
    )


def _evidence_interpretation(item: object) -> str:
    name = str(getattr(item, "name", "")).lower()
    value = str(getattr(item, "value", ""))
    explanation = str(getattr(item, "explanation", ""))
    if "revenue growth" in name:
        return "Positive demand evidence if sourced periods are comparable; check whether growth is broad-based."
    if "gross margin" in name:
        return "Supports pricing power and product-mix quality when positive."
    if "operating margin" in name:
        return "Shows operating leverage; positive trend strengthens business-quality scoring."
    if "fcf" in name:
        return "Negative or volatile FCF trend lowers confidence until CFO and capex periods are reconciled."
    if "hyperscaler" in name:
        return "Demand-support signal, but valuation changes require primary hyperscaler filing or earnings confirmation."
    if "remaining performance" in name or "backlog" in name or "purchase obligation" in name:
        return "Potential backlog or demand-visibility clue; use it only if the filing or IR source provides a clear amount, trend, or commitment."
    if "estimate revisions" in name:
        return "Missing revisions leave FOMO risk higher because price and multiples lack estimate confirmation."
    if "forward eps" in name:
        return "Model assumption used for PEG; replace with structured estimates when available."
    return explanation or value


def _scoring_table(inputs: BuySideMemoInput) -> str:
    if not inputs.scoring_rubric:
        return '<div class="evidence-card-list scoring-card-list"><article class="evidence-card"><p class="subtle">No scoring rows generated.</p></article></div>'
    cards = "".join(
        '<article class="evidence-card scoring-card">'
        '<div class="evidence-card-head">'
        "<div>"
        f"<span>{escape(item.name)}</span>"
        f"<strong>{item.score}/5</strong>"
        "</div>"
        f'<span class="source-status source-quality-{escape(item.confidence.lower())}">{escape(item.confidence.title())} confidence</span>'
        "</div>"
        f"<p><strong>Insights:</strong> {escape(item.explanation)}</p>"
        '<details class="evidence-detail">'
        "<summary>Evidence basis</summary>"
        f"<p>{escape(_shorten_text(item.evidence, 420))}</p>"
        "</details>"
        f"<p class=\"subtle\"><strong>Warning:</strong> {escape(item.warning or 'None')}</p>"
        "</article>"
        for item in inputs.scoring_rubric
    )
    return f'<div class="evidence-card-list scoring-card-list">{cards}</div>'


def _gf_dma_table(inputs: BuySideMemoInput) -> str:
    values = {
        "Fundamental growth": f"{inputs.gf_dma_health.fundamental_growth_score:.1f}/100",
        "DMA trend": f"{inputs.gf_dma_health.dma_trend_score:.1f}/100",
        "Divergence": f"{inputs.gf_dma_health.divergence_score:.1f}/100",
        "Estimate revisions": f"{inputs.gf_dma_health.estimate_revision_score:.1f}/100",
        "Escape ratio": f"{inputs.gf_dma_health.escape_ratio:.3f}x",
        "Overall GF-DMA health": f"{inputs.gf_dma_health.overall_gf_dma_health_score:.1f}/100",
    }
    return _dict_table(values) + f"<p><strong>Trend health and entry discipline:</strong> {escape(inputs.gf_dma_health.explanation)}</p>"


def _entry_zone_table(inputs: BuySideMemoInput) -> str:
    rows = {
        "Conservative entry zone": f"Up to {_money_or_unavailable(inputs.entry_zones.conservative_entry_max)}",
        "Reasonable accumulation zone": f"{_money_or_unavailable(inputs.entry_zones.reasonable_accumulation_min)} to {_money_or_unavailable(inputs.entry_zones.reasonable_accumulation_max)}",
        "Expensive/wait zone": f"Above {_money_or_unavailable(inputs.entry_zones.expensive_wait_min)}",
    }
    return _dict_table(rows) + "<p class=\"subtle\">Entry zones are scenario-based and do not create an instruction to transact.</p>"


def _macro_tracker(inputs: BuySideMemoInput) -> str:
    cards = []
    for item in inputs.macro_industry_tracker:
        name, value, date_source = _parse_macro_item(item)
        cards.append(
            '<article class="macro-card">'
            f"<span>{escape(name)}</span>"
            f"<strong>{escape(value)}</strong>"
            f"<p>{escape(_macro_insight(name, value))}</p>"
            f"<small>{escape(date_source)}</small>"
            "</article>"
        )
    if not cards:
        return '<p class="subtle">No macro or industry indicators available from current sources.</p>'
    return '<div class="macro-grid">' + "".join(cards) + "</div>"


def _parse_macro_item(item: str) -> tuple[str, str, str]:
    name, separator, rest = item.partition(":")
    if not separator:
        return item, "Not available", ""
    value = rest.strip()
    date_source = ""
    if "(" in value and value.endswith(")"):
        value, date_source = value.rsplit("(", 1)
        date_source = date_source.rstrip(")")
    return name.strip(), value.strip(), date_source


def _macro_insight(name: str, value: str) -> str:
    lowered = name.lower()
    if "10-year" in lowered:
        return "Higher long-term rates can compress valuation multiples for long-duration AI growth equities."
    if "federal funds" in lowered:
        return "Policy-rate level affects discount rates, risk appetite, and the valuation tolerance for AI infrastructure names."
    if lowered == "cpi":
        return "Inflation trend shapes rate expectations; sticky CPI can pressure high-multiple technology stocks."
    if lowered == "pce":
        return "PCE is central to Fed reaction function and therefore relevant to multiple expansion or compression."
    if "unemployment" in lowered:
        return "Labor-market softening can shift rate expectations but may also signal macro demand risk."
    if "industry" in lowered:
        return "Industry source coverage is still incomplete; add SIA, SEMI, WSTS, TSMC monthly revenue, and hyperscaler filings."
    return "Monitor direction and source freshness before changing valuation assumptions."



def _risk_opportunity_tracker_cards(inputs: BuySideMemoInput) -> str:
    if not inputs.risk_opportunity_trackers:
        return '<p class="subtle">No tracker entries configured for this ticker yet.</p>'

    risk_items = tuple(
        item
        for item in inputs.risk_opportunity_trackers
        if item.impact_if_validated == "negative"
    )
    opportunity_items = tuple(
        item
        for item in inputs.risk_opportunity_trackers
        if item.impact_if_validated == "positive"
    )
    mixed_items = tuple(
        item
        for item in inputs.risk_opportunity_trackers
        if item.impact_if_validated in {"mixed", "neutral"}
    )
    groups = [
        _tracker_split_group(
            inputs,
            "Risks to Watch",
            "Downside signals that could reduce thesis confidence, compress valuation assumptions, or affect entry discipline if validated.",
            risk_items,
            "risk",
        ),
        _tracker_split_group(
            inputs,
            "Opportunities to Validate",
            "Positive signals and catalysts that could support thesis confidence only after source confirmation.",
            opportunity_items,
            "opportunity",
        ),
        _tracker_split_group(
            inputs,
            "Mixed / Neutral Monitoring",
            "Context indicators with both positive and negative read-through; useful for monitoring but not a standalone thesis change.",
            mixed_items,
            "mixed",
        ),
    ]
    return "\n".join(group for group in groups if group)


def _tracker_split_group(
    inputs: BuySideMemoInput,
    title: str,
    intro: str,
    items: tuple[RiskOpportunityTrackerItem, ...],
    tone: str,
) -> str:
    if not items:
        return ""
    cards = "\n".join(_tracker_card(inputs, item) for item in sorted(items, key=_tracker_sort_key))
    return (
        f'<div class="tracker-category tracker-split-group tracker-split-{escape(tone)}">'
        f"<h3>{escape(title)}</h3>"
        f'<p class="tracker-group-intro">{escape(intro)}</p>'
        f'<div class="tracker-grid">{cards}</div>'
        "</div>"
    )


def _tracker_sort_key(item: RiskOpportunityTrackerItem) -> tuple[int, int, str]:
    importance_order = {"high": 0, "medium": 1, "low": 2}
    status_order = {"escalated": 0, "validated": 1, "monitoring": 2, "pending": 3, "invalidated": 4}
    return (
        importance_order.get(item.importance, 3),
        status_order.get(item.status, 5),
        item.event_or_indicator.lower(),
    )


def _search_result_cards(inputs: BuySideMemoInput, official_only: bool = False) -> str:
    results = inputs.source_discovery_results
    if official_only:
        official_types = {
            "primary_company_source",
            "official_regulator",
            "official_government",
            "sec_filing",
            "industry_body",
        }
        results = tuple(
            result
            for result in results
            if result.source_type in official_types and result.confidence == "high"
        )
    if not results:
        return "<p>No official source-cache results loaded for this memo.</p>"

    cards = []
    for result in results:
        url = escape(result.url)
        link = (
            f'<a href="{url}" rel="noreferrer">{escape(result.source_name or result.url)}</a>'
            if url
            else escape(result.source_name or "Unknown source")
        )
        cards.append(
            '<article class="source-card">'
            '<div class="tracker-badges">'
            f'<span class="tracker-badge source-quality-{escape(result.confidence)}">{escape(result.confidence.title())}</span>'
            f'<span class="tracker-badge source-type">{escape(result.source_type.replace("_", " ").title())}</span>'
            f'<span class="tracker-badge status-{_status_class(result.status)}">{escape(result.status.title())}</span>'
            "</div>"
            f"<h4>{escape(result.title or 'Untitled source result')}</h4>"
            f"<p>{escape(result.summary or result.snippet or result.reason_for_classification)}</p>"
            f'<p class="tracker-meta">{link} | Published: {escape(result.published_date or "Not available")} | Retrieved: {escape(result.retrieved_at)}</p>'
            f"<p><strong>Classification:</strong> {escape(result.reason_for_classification)}</p>"
            "</article>"
        )
    return f'<div class="source-card-grid">{"".join(cards)}</div>'


def _tracker_card(inputs: BuySideMemoInput, item: RiskOpportunityTrackerItem) -> str:
    importance = f"{item.importance.title()} Importance"
    status = item.status.title()
    impact = f"{item.impact_if_validated.title()} if validated"
    sources = ", ".join(item.source_priority) if item.source_priority else "Not specified"
    source_url = item.source_url if item.source_url and item.source_url != "TODO" else "TODO"
    status_class, status_label, evidence, source_basis = _risk_current_judgment(inputs, item)
    insight = _tracker_interpretation(item, evidence)
    evidence_readout = _tracker_evidence_readout(inputs, item, evidence)
    return (
        '<article class="tracker-card">'
        '<div class="tracker-card-head">'
        "<div>"
        f"<h4>{escape(item.event_or_indicator)}</h4>"
        f'<p class="tracker-meta">{escape(item.category.title())} | Confidence: {escape(item.confidence.title())}</p>'
        "</div>"
        '<div class="tracker-badges">'
        f'<span class="tracker-badge importance-{_importance_class(item.importance)}">{escape(importance)}</span>'
        f'<span class="tracker-badge status-{_status_class(item.status)}">{escape(status)}</span>'
        f'<span class="tracker-badge impact-{_impact_class(item.impact_if_validated)}">{escape(impact)}</span>'
        "</div>"
        "</div>"
        f'<p class="tracker-summary">{escape(item.why_it_matters)}</p>'
        '<div class="tracker-current-grid">'
        '<div class="tracker-current-panel tracker-current-primary">'
        "<strong>Current status</strong>"
        f'<span class="status-dot status-{escape(status_class)}">{escape(status_label)}</span>'
        f"<p>{escape(insight)}</p>"
        "</div>"
        '<div class="tracker-current-panel">'
        "<strong>Signal readout</strong>"
        f"<p>{escape(evidence_readout)}</p>"
        "</div>"
        "</div>"
        '<details class="tracker-secondary-details">'
        "<summary>Validation rules, source basis, and schedule</summary>"
        '<div class="tracker-detail-grid">'
        f"<p><strong>Validation rule</strong><span>{escape(item.validation_rule)}</span></p>"
        f"<p><strong>Suggested response</strong><span>{escape(item.suggested_research_response)}</span></p>"
        f"<p><strong>Status note</strong><span>{escape(_tracker_status_note(item))}</span></p>"
        f"<p><strong>Source basis</strong><span>{escape(source_basis or sources)}</span></p>"
        f"<p><strong>Frequency</strong><span>{escape(item.frequency)}</span></p>"
        f"<p><strong>Next check date</strong><span>{escape(item.next_check_date)}</span></p>"
        f"<p><strong>Last checked</strong><span>{escape(item.last_checked or 'Not checked by live connectors yet')}</span></p>"
        f"<p><strong>Source priority</strong><span>{escape(sources)}</span></p>"
        f'<p><strong>Source URL</strong><span>{escape(source_url)}</span></p>'
        "</div>"
        "</details>"
        "</article>"
    )


def _tracker_evidence_readout(inputs: BuySideMemoInput, item: RiskOpportunityTrackerItem, evidence: str) -> str:
    event = item.event_or_indicator.lower()
    if item.category == "macro":
        macro = _macro_readout_for_item(inputs, item)
        if macro:
            clean_macro = _clean_tracker_evidence(macro)
            if "10-year" in event:
                return f"Evidence: {clean_macro}. Read-through: rates are above the recent average, so multiple-compression risk is active. Open question: does this persist for several sessions?"
            return f"Evidence: {clean_macro}. Read-through: macro pressure should affect valuation assumptions only if the move persists."
    if item.category == "technical":
        return f"Evidence: GF-DMA is {inputs.gf_dma_health.overall_gf_dma_health_score:.1f}/100. Read-through: trend health is usable for entry discipline, but it does not change intrinsic value."
    if item.status == "pending":
        return f"Evidence: not confirmed yet. Read-through: no valuation or thesis-confidence change until this rule is met: {item.validation_rule}"
    if item.status == "invalidated":
        return "Evidence: current sources do not support the signal. Read-through: keep it dismissed unless fresh source-backed evidence appears."
    clean = _clean_tracker_evidence(item.evidence_summary or evidence)
    if clean:
        return _tracker_signal_readthrough(item, clean)
    if item.status == "validated" and item.impact_if_validated == "positive":
        return "Evidence: confirmed positive signal. Read-through: raise confidence only in the linked growth or quality assumption."
    if item.status == "validated" and item.impact_if_validated == "negative":
        return "Evidence: confirmed downside signal. Read-through: review the linked bear-case, valuation, or entry-zone assumption."
    return "No concise live evidence readout is available yet."


def _tracker_signal_readthrough(item: RiskOpportunityTrackerItem, clean_evidence: str) -> str:
    event = item.event_or_indicator.lower()
    if "export" in event:
        return (
            f"Evidence: {clean_evidence}. Read-through: regulatory risk is validated, so keep an export-control haircut in the downside case. "
            "Open question: the revenue impact is still not quantified."
        )
    if "data-center revenue" in event or "data center revenue" in event:
        return (
            f"Evidence: {clean_evidence}. Read-through: this supports the AI-demand and gross-margin thesis drivers. "
            "Open question: whether the next filing confirms breadth and durability."
        )
    if "gross margin" in event:
        return (
            f"Evidence: {clean_evidence}. Read-through: margin quality supports premium valuation if it persists. "
            "Open question: product mix and supply costs in the next release."
        )
    if "earnings" in event:
        return (
            f"Evidence: {clean_evidence}. Read-through: use the next release to refresh revenue growth, margin, guidance, and scenario assumptions."
        )
    if item.impact_if_validated == "positive":
        return f"Evidence: {clean_evidence}. Read-through: supports the linked upside driver, but update only that specific assumption."
    if item.impact_if_validated == "negative":
        return f"Evidence: {clean_evidence}. Read-through: supports the linked downside driver; review scenario and entry-zone assumptions."
    return f"Evidence: {clean_evidence}. Read-through: update the tracker status without treating it as a standalone valuation signal."


def _clean_tracker_evidence(text: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return ""
    first, separator, rest = clean.partition("). ")
    if separator and any(token in first.lower() for token in ("confidence", "confirmed", "sec_filing", "official_", "primary_company_source")):
        clean = rest.strip()
    clean = clean.replace("SEC-hosted ", "Official ")
    clean = clean.replace("provides official support for", "supports")
    clean = clean.replace("FRED public CSV", "")
    clean = clean.replace("  ", " ")
    clean = clean.replace(" ;", ";").replace("; )", ")").replace(";)", ")").strip(" ;")
    return _shorten_text(clean, 280)


def _tracker_interpretation(item: RiskOpportunityTrackerItem, evidence: str) -> str:
    if item.status == "escalated":
        return "Thesis-impacting item. Review scenario assumptions and risk language before relying on the current memo view."
    if item.status == "validated":
        if item.impact_if_validated == "positive":
            return "Validated support for the thesis. Increase confidence only in the specific assumption tied to this evidence."
        if item.impact_if_validated == "negative":
            return "Validated downside signal. Keep the risk visible and review whether valuation, scenario, or entry-zone assumptions need adjustment."
        if item.impact_if_validated == "mixed":
            return "Validated but mixed signal. Treat it as a model-update item rather than a simple positive or negative."
        return "Validated neutral signal. Keep the memo updated, but do not treat this as a transaction instruction."
    if item.status == "invalidated":
        return "Dismissed for now. Do not let this issue influence assumptions unless new source-backed evidence appears."
    if item.status == "pending":
        return "Still unconfirmed. The memo should not change valuation or growth assumptions until the validation rule is met."
    if item.category == "macro":
        if evidence and "above recent average" in evidence.lower():
            return "Active monitoring item. Rates are above the recent average, so multiple-compression risk remains relevant even if the latest tick is not worsening."
        return "Active monitoring item. Use the latest macro readout as context, but require persistence before changing the thesis."
    if item.category == "technical":
        return "Timing discipline item. It can inform entry pacing, but it should not change intrinsic value by itself."
    if item.impact_if_validated == "positive":
        return "Potential support for the thesis. Wait for source confirmation before increasing confidence."
    if item.impact_if_validated == "negative":
        return "Potential downside risk. Keep it in view until source evidence validates or dismisses the issue."
    return "Monitoring item. Keep the evidence threshold explicit before changing assumptions."


def _tracker_status_note(item: RiskOpportunityTrackerItem) -> str:
    if item.status == "pending":
        return f"Evidence needed for validation: {item.validation_rule}"
    if item.status == "validated":
        return "Update the thesis confidence, scenario assumptions, or valuation inputs tied to this evidence."
    if item.status == "escalated":
        return "Escalated item; review near-term risk, source evidence, and scenario assumptions before the next memo."
    if item.status == "invalidated":
        return "Do not rely on this signal unless fresh source-backed evidence appears."
    return "Monitoring item; keep the evidence threshold explicit before changing the thesis."


def _escalated_tracker_cards(
    items: tuple[RiskOpportunityTrackerItem, ...],
) -> list[str]:
    escalated = [item for item in items if item.status == "escalated"]
    if not escalated:
        return []
    return [
        _metric_card(
            "Escalated Tracker Item",
            item.event_or_indicator,
            "Review risk and scenario assumptions",
        )
        for item in escalated
    ]


def _catalyst_risk_cards(inputs: BuySideMemoInput) -> str:
    catalyst_cards = "".join(_catalyst_risk_card(item, inputs, is_risk=False) for item in inputs.catalysts)
    risk_cards = "".join(_catalyst_risk_card(item, inputs, is_risk=True) for item in inputs.risks)
    return f'<div class="card-grid">{catalyst_cards}{risk_cards}</div>'


def _catalyst_risk_card(item: str, inputs: BuySideMemoInput, is_risk: bool) -> str:
    tracker = _matching_tracker_item(item, inputs.risk_opportunity_trackers)
    label = "Risk" if is_risk else "Potential catalyst"
    class_name = "risk-card" if is_risk else "catalyst-card"
    severity = (tracker.importance.title() if tracker else ("High" if is_risk else "Medium"))
    explanation = _catalyst_risk_explanation(item, tracker, is_risk)
    response = tracker.suggested_research_response if tracker else _fallback_research_response(item, is_risk)
    return (
        f'<article class="{class_name}">'
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(item)}</strong>"
        f"<p>{escape(explanation)}</p>"
        f"<small>Severity: {escape(severity)} | Response: {escape(response)}</small>"
        "</article>"
    )


def _matching_tracker_item(item: str, trackers: tuple[RiskOpportunityTrackerItem, ...]) -> RiskOpportunityTrackerItem | None:
    lowered = item.lower()
    for tracker in trackers:
        event = tracker.event_or_indicator.lower()
        if lowered in event or event in lowered:
            return tracker
        key_terms = [word for word in lowered.replace("/", " ").replace("-", " ").split() if len(word) > 4]
        if key_terms and sum(1 for word in key_terms if word in event) >= min(2, len(key_terms)):
            return tracker
    return None


def _catalyst_risk_explanation(item: str, tracker: RiskOpportunityTrackerItem | None, is_risk: bool) -> str:
    if tracker:
        return tracker.why_it_matters
    lowered = item.lower()
    if "10-year" in lowered or "yield" in lowered or "rate" in lowered:
        return "Higher discount rates can pressure long-duration AI growth multiples even when fundamentals remain strong."
    if "export" in lowered or "china" in lowered:
        return "Restrictions can reduce addressable demand or force scenario changes for affected AI accelerator sales."
    if "moving average" in lowered or "50-day" in lowered or "200-day" in lowered or "divergence" in lowered:
        return "Technical extension can weaken entry discipline when price action runs ahead of estimate revisions."
    if "earnings" in lowered or "financial results" in lowered:
        return "A fresh company release can validate or challenge revenue, margin, guidance, and AI demand assumptions."
    if "hbm" in lowered or "packaging" in lowered or "supply" in lowered:
        return "Supply availability can determine whether AI demand converts into recognized revenue and margin leverage."
    if is_risk:
        return "This item can weaken thesis confidence or require lower scenario assumptions if confirmed by primary sources."
    return "This item can improve thesis confidence if confirmed by primary or official sources and reflected in fundamentals."


def _fallback_research_response(item: str, is_risk: bool) -> str:
    lowered = item.lower()
    if "export" in lowered or "china" in lowered:
        return "escalate risk review"
    if "moving average" in lowered or "divergence" in lowered:
        return "review entry zone"
    if "earnings" in lowered or "financial results" in lowered:
        return "update valuation model"
    if is_risk:
        return "reduce thesis confidence if validated"
    return "increase thesis confidence if validated"


def _change_table(inputs: BuySideMemoInput) -> str:
    rows = "".join(
        "<tr>"
        f"<th>{escape(change.category)}</th>"
        f"<td>{escape(change.previous)}</td>"
        f"<td>{escape(change.current)}</td>"
        f"<td>{escape(change.summary)}</td>"
        "</tr>"
        for change in inputs.changes_since_last_review
    )
    return f'<div class="table-wrap"><table><tr><th>Area</th><th>Previous</th><th>Latest</th><th>Change</th></tr>{rows}</table></div>'


def _quality_table(inputs: BuySideMemoInput, decision: DecisionProfile) -> str:
    return _dict_table(
        {
            "Data freshness": "Mock data; refresh after real connectors are available"
            if inputs.report_mode == "mock"
            else "Live source check; unavailable fields reflect missing connector data or credentials",
            "Data quality": inputs.data_quality,
            "Confidence level": inputs.confidence_level,
            "Connector health score": f"{inputs.data_quality_score:.1f}/100",
            "Decision-useful quality score": f"{decision.decision_quality_score:.1f}/100",
            "Decision-ready status": decision.decision_ready_status.replace("_", " ").title(),
            "Quality score note": "Connector health can be high while valuation confidence is lower; missing valuation fields, fallback data, and period mismatches reduce the decision-useful score.",
            "Latest price timestamp": inputs.latest_price_timestamp,
            "Latest filing date": inputs.latest_filing_date,
            "Latest financial data period": inputs.latest_financial_data_period,
            "Latest macro data date": inputs.latest_macro_data_date,
            "Latest news retrieval date": inputs.latest_news_retrieval_date,
            "Missing data warnings": "; ".join(inputs.connector_warnings + inputs.missing_data_warnings) or "None recorded",
        }
    )


def _pill_list(items: tuple[str, ...]) -> str:
    return '<div class="pill-row">' + "".join(f"<span>{escape(item)}</span>" for item in items) + "</div>"


def _card_list(items: tuple[str, ...], class_name: str) -> str:
    return '<div class="card-grid">' + "".join(f'<article class="{class_name}-card">{escape(item)}</article>' for item in items) + "</div>"


def _bullet_list(items: tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _shorten_text(text: str, limit: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "..."


def _mini_card(label: str, value: str) -> str:
    return f'<article class="mini-card"><span>{escape(label)}</span><strong>{escape(value)}</strong></article>'


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _compact_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000_000_000:
        return f"{sign}${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"{sign}${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    return f"{sign}${value:,.2f}"


def _safe_float(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("%", "").replace("x", ""))
    except (TypeError, ValueError):
        return None


def _money_or_unavailable(value: float) -> str:
    if value <= 0:
        return "Not available from current sources"
    return _money(value)


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _slug(title: str) -> str:
    return (
        title.lower()
        .replace("&", "and")
        .replace(" / ", "-")
        .replace("/", "-")
        .replace(" ", "-")
        .replace("--", "-")
    )


def _status_class(status: str) -> str:
    normalized = status.strip().lower().replace(" ", "-")
    if normalized == "confirmed":
        return "validated"
    if normalized == "rumor":
        return "pending"
    if normalized in {"opinion", "conflicting", "irrelevant"}:
        return "invalidated" if normalized == "irrelevant" else "pending"
    allowed = {"pending", "validated", "invalidated", "monitoring", "escalated"}
    if normalized in allowed:
        return normalized
    return "pending"


def _source_status_class(status: str) -> str:
    normalized = status.strip().lower().replace(" ", "-")
    allowed = {
        "available",
        "unavailable",
        "fallback",
        "yes",
        "no",
        "configured",
        "missing",
        "used",
        "not-used",
        "optional",
        "not-configured",
    }
    return normalized if normalized in allowed else "unavailable"


def _impact_class(impact: str) -> str:
    normalized = impact.strip().lower().replace(" ", "-")
    allowed = {"positive", "negative", "mixed", "neutral"}
    if normalized in allowed:
        return normalized
    return "neutral"


def _importance_class(importance: str) -> str:
    normalized = importance.strip().lower().replace(" ", "-")
    allowed = {"high", "medium", "low"}
    if normalized in allowed:
        return normalized
    return "medium"


def _load_template(name: str) -> str:
    path = Path(__file__).with_name("templates") / name
    return path.read_text(encoding="utf-8")


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{ " + key + " }}", value)
    return rendered


def _strip_markup_for_validation(html: str) -> str:
    return html.replace("<", " <").replace(">", "> ")
