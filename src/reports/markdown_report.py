"""Buy-side equity research memo generator.

The renderer combines mock financial data with outputs from the valuation,
Bayesian growth, TAM-adjusted PEG, and GF-DMA health modules.

TODO: Replace mock builders with source-backed connector outputs, citation
objects, and validated report schemas when real data ingestion is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.config import AppConfig, missing_key_warnings
from src.connectors.mock_data import CompanyMockData
from src.data.data_hub import ProviderDataBundle, collect_provider_data
from src.data import EvidenceItem, ScoredAssumption, SearchResult, ValidatedMetric, validate_metrics
from src.data.periods import (
    FiscalPeriod,
    PeriodMetric,
    calculate_ttm_free_cash_flow,
    calculate_ttm_metric,
    normalize_period_label,
    period_metric_from_sec_row,
    point_in_time_period,
)
from src.research import (
    BayesianGrowthInput,
    BayesianGrowthResult,
    ChangeRecord,
    GfDmaHealthInput,
    GfDmaHealthResult,
    MemoSnapshot,
    RiskOpportunityTrackerItem,
    TamAdjustedPegInput,
    TamAdjustedPegResult,
    calculate_gf_dma_health,
    calculate_tam_adjusted_peg,
    build_growth_trend_evidence,
    build_scoring_rubric,
    build_search_evidence,
    compare_memo_snapshots,
    estimate_intrinsic_growth,
    extract_filing_evidence,
    hyperscaler_capex_evidence_from_source_cache,
    group_tracker_items_by_category,
    load_risk_opportunity_trackers,
    model_eps_growth_assumption,
    update_trackers_from_search_results,
)
from src.valuation import (
    EntryZones,
    ScenarioValuation,
    calculate_entry_zones,
    enterprise_value,
    ev_to_ebitda,
    ev_to_sales,
    price_to_earnings,
    price_to_fcf,
    period_aware_ev_to_ebitda,
    period_aware_ev_to_sales,
    period_aware_margin,
    period_aware_price_to_earnings,
    period_aware_price_to_fcf,
    period_aware_price_to_sales,
    probability_weighted_fair_value,
)
from src.reports.archetypes import CompanyArchetypeProfile, archetype_for_company
from src.reports.report_schema import (
    ClaimType,
    EvidenceClaim,
    validate_report_compliance,
)
from src.validation.calculation_audit import audit_calculations


MANDATORY_SECTIONS = (
    "Executive Dashboard",
    "One-Paragraph Investment View",
    "AI Value-Chain Classification",
    "Financial Snapshot",
    "Fiscal Period & TTM Basis",
    "Valuation Scenarios",
    "Bayesian Intrinsic Growth View",
    "TAM-Adjusted PEG View",
    "GF-DMA Health View",
    "Entry-Price Framework",
    "Macro And Industry Impact",
    "Risk & Opportunity Tracker",
    "Recent Validated Developments",
    "Pending Signals",
    "Catalysts",
    "Risks",
    "What changed since last review",
    "What Would Change The View",
    "Data Quality And Confidence Level",
    "Evidence Classification",
    "Sources",
    "AnySearch Query Log",
)


@dataclass(frozen=True)
class DataSourceStatus:
    """Visible source-health row for memo diagnostics."""

    category: str
    configured: str
    used: str
    availability: str
    reason: str
    last_successful_retrieval: str


@dataclass(frozen=True)
class BuySideMemoInput:
    """Structured inputs for the buy-side memo renderer."""

    company_name: str
    ticker: str
    archetype_name: str
    business_summary: str
    investment_view: str
    ai_value_chain_classification: str
    financial_snapshot: dict[str, str]
    valuation_multiples: dict[str, str]
    valuation_scenarios: tuple[ScenarioValuation, ...]
    fair_value_per_share: float
    entry_zones: EntryZones
    bayesian_growth: BayesianGrowthResult
    tam_adjusted_peg: TamAdjustedPegResult
    gf_dma_health: GfDmaHealthResult
    macro_industry_tracker: tuple[str, ...]
    required_monitoring_indicators: tuple[str, ...]
    catalysts: tuple[str, ...]
    risks: tuple[str, ...]
    risk_opportunity_trackers: tuple[RiskOpportunityTrackerItem, ...]
    changes_since_last_review: tuple[ChangeRecord, ...]
    view_change_triggers: tuple[str, ...]
    data_quality: str
    confidence_level: str
    evidence_claims: tuple[EvidenceClaim, ...]
    is_mock: bool
    sources: tuple[str, ...]
    report_mode: str = "mock"
    connector_warnings: tuple[str, ...] = ()
    missing_data_warnings: tuple[str, ...] = ()
    data_quality_score: float = 0.0
    latest_price_timestamp: str = "Not available from current sources"
    latest_filing_date: str = "Not available from current sources"
    latest_financial_data_period: str = "Not available from current sources"
    latest_macro_data_date: str = "Not available from current sources"
    latest_news_retrieval_date: str = "Not available from current sources"
    anysearch_query_log: tuple[str, ...] = ()
    recent_validated_developments: tuple[str, ...] = ()
    pending_signals: tuple[str, ...] = ()
    source_discovery_results: tuple[SearchResult, ...] = ()
    latest_price: float = 0.0
    data_source_status: tuple[DataSourceStatus, ...] = ()
    evidence_classification: tuple[EvidenceItem, ...] = ()
    bayesian_growth_evidence: tuple[EvidenceItem, ...] = ()
    tam_assumptions: tuple[EvidenceItem, ...] = ()
    scoring_rubric: tuple[ScoredAssumption, ...] = ()
    low_confidence_warnings: tuple[str, ...] = ()
    period_basis_rows: tuple["PeriodBasisRow", ...] = ()
    calculation_audit_passed: bool = True
    calculation_audit_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PeriodBasisRow:
    metric: str
    period_basis: str
    source: str
    periods_used: str
    warning: str = "None"


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _money_or_unavailable(value: float) -> str:
    if value <= 0:
        return "Not available from current sources"
    return _money(value)


def _bullet_list(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _checklist(items: tuple[str, ...]) -> str:
    return "\n".join(f"- [ ] {item}" for item in items)


def _dict_table(values: dict[str, str]) -> str:
    rows = ["| Metric | View |", "| --- | --- |"]
    rows.extend(f"| {key} | {value} |" for key, value in values.items())
    return "\n".join(rows)


def _calculation_audit_label(inputs: BuySideMemoInput) -> str:
    return "PASS" if inputs.calculation_audit_passed else "FAIL"


def _calculation_audit_note(inputs: BuySideMemoInput) -> str:
    if inputs.calculation_audit_passed:
        return (
            "Calculation audit PASS. Shared formula-registry fixtures passed for valuation, scenario, "
            "entry-zone, Bayesian-supporting growth trends, TAM-adjusted PEG, GF-DMA, moving-average, "
            "and data-quality checks."
        )
    return "Calculation audit FAIL. Issues:\n\n" + _warnings_list(inputs.calculation_audit_warnings)


def _period_basis_markdown_table(rows: tuple[PeriodBasisRow, ...]) -> str:
    if not rows:
        return "No fiscal-period basis rows generated."
    output = ["| Metric | Period basis | Source | Periods used | Warning |", "| --- | --- | --- | --- | --- |"]
    output.extend(
        f"| {row.metric} | {row.period_basis} | {row.source} | {row.periods_used} | {row.warning or 'None'} |"
        for row in rows
    )
    return "\n".join(output)


def _valuation_scenario_table(scenarios: tuple[ScenarioValuation, ...]) -> str:
    rows = [
        "| Case | Enterprise value | Equity value | Fair value/share | Probability |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for scenario in scenarios:
        rows.append(
            "| "
            f"{scenario.name} | "
            f"{_money_or_unavailable(scenario.enterprise_value)} | "
            f"{_money_or_unavailable(scenario.equity_value)} | "
            f"{_money_or_unavailable(scenario.fair_value_per_share)} | "
            f"{_pct(scenario.probability)} |"
        )
    return "\n".join(rows)


def _scenario_anchor_table(scenarios: tuple[ScenarioValuation, ...]) -> str:
    rows = ["| Scenario anchor | Fair value/share |", "| --- | ---: |"]
    for scenario in scenarios:
        rows.append(f"| {scenario.name} case | {_money_or_unavailable(scenario.fair_value_per_share)} |")
    return "\n".join(rows)


def _bayesian_table(result: BayesianGrowthResult) -> str:
    rows = ["| Hypothesis | Prior | Updated |", "| --- | ---: | ---: |"]
    for hypothesis, prior in result.prior_probabilities.items():
        rows.append(
            "| "
            f"{hypothesis.name}: {hypothesis.value} | "
            f"{_pct(prior)} | "
            f"{_pct(result.updated_probabilities[hypothesis])} |"
        )
    return "\n".join(rows)


def _evidence_markdown_table(items: tuple[EvidenceItem, ...]) -> str:
    if not items:
        return "No evidence rows generated."
    rows = ["| Item | Layer | Value | Source | Confidence | Warning |", "| --- | --- | --- | --- | --- | --- |"]
    rows.extend(
        f"| {item.name} | {item.data_layer} | {item.value} | {item.source_name} | {item.confidence} | {item.warning or 'None'} |"
        for item in items
    )
    return "\n".join(rows)


def _scoring_markdown_table(items: tuple[ScoredAssumption, ...]) -> str:
    if not items:
        return "No scoring rows generated."
    rows = ["| Score | Value | Rubric | Confidence | Warning |", "| --- | ---: | --- | --- | --- |"]
    rows.extend(
        f"| {item.name} | {item.score}/5 | {item.explanation} | {item.confidence} | {item.warning or 'None'} |"
        for item in items
    )
    return "\n".join(rows)


def _source_list(sources: tuple[str, ...]) -> str:
    if not sources:
        return "- TODO: Add source-backed citations from primary documents."
    return _bullet_list(sources)


def _warnings_list(items: tuple[str, ...]) -> str:
    if not items:
        return "- No connector warnings recorded."
    return _bullet_list(items)


def _search_query_log(results: tuple[SearchResult, ...], use_source_cache: bool) -> tuple[str, ...]:
    if not use_source_cache:
        return (
            "Source cache not used. Run Codex AnySearch discovery and rerun with --use-source-cache to include recent developments.",
        )
    if not results:
        return ("Source cache requested, but outputs/source_cache/{TICKER}.json contained no usable results.",)
    return tuple(
        f"{result.query or 'Cached source'} -> {result.source_name}: {result.status} ({result.confidence}, {result.source_type})"
        for result in results
    )


def _evidence_claim_table(claims: tuple[EvidenceClaim, ...]) -> str:
    rows = [
        "| Type | Claim/Input | Value | Source | Confidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for claim in claims:
        source = claim.source or "Not provided"
        value = claim.value or "-"
        rows.append(
            "| "
            f"{claim.claim_type.value} | "
            f"{claim.text} | "
            f"{value} | "
            f"{source} | "
            f"{claim.confidence} |"
        )
    return "\n".join(rows)


def _change_table(changes: tuple[ChangeRecord, ...]) -> str:
    rows = [
        "| Area | Previous review | Latest review | Plain-English change |",
        "| --- | --- | --- | --- |",
    ]
    for change in changes:
        rows.append(
            "| "
            f"{_clean_cell(change.category)} | "
            f"{_clean_cell(change.previous)} | "
            f"{_clean_cell(change.current)} | "
            f"{_clean_cell(change.summary)} |"
        )
    return "\n".join(rows)


def _clean_cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ")


def _tracker_markdown(
    items: tuple[RiskOpportunityTrackerItem, ...],
) -> str:
    if not items:
        return "No tracker entries configured for this ticker yet."

    sections = []
    for category, category_items in group_tracker_items_by_category(items):
        rows = [
            f"### {category.title()}",
            "",
            "| Importance | Status | Impact | Event or indicator | Why it matters | Validation / response | Evidence | Frequency | Next check | Source / confidence |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for item in category_items:
            sources = ", ".join(item.source_priority) if item.source_priority else item.source_url
            validation_note = _tracker_status_note(item)
            rows.append(
                "| "
                f"{item.importance.title()} | "
                f"{item.status.title()} | "
                f"{item.impact_if_validated.title()} | "
                f"{_clean_cell(item.event_or_indicator)} | "
                f"{_clean_cell(item.why_it_matters)} | "
                f"{_clean_cell(validation_note)} Suggested response: {_clean_cell(item.suggested_research_response)} | "
                f"{_clean_cell(item.evidence_summary)} Last checked: {_clean_cell(item.last_checked or 'Not checked by live connectors yet')} | "
                f"{_clean_cell(item.frequency)} | "
                f"{_clean_cell(item.next_check_date)} | "
                f"{_clean_cell(sources)} / {item.confidence.title()} |"
            )
        sections.append("\n".join(rows))
    return "\n\n".join(sections)


def _tracker_status_note(item: RiskOpportunityTrackerItem) -> str:
    if item.status == "pending":
        return f"Evidence needed: {item.validation_rule}."
    if item.status == "validated":
        return f"Validated; update thesis or valuation inputs tied to: {item.validation_rule}."
    if item.status == "escalated":
        return f"Escalated; prioritize risk review using: {item.validation_rule}."
    if item.status == "invalidated":
        return f"Invalidated; reduce weight on the signal unless new evidence appears. Rule: {item.validation_rule}."
    return f"Monitoring rule: {item.validation_rule}."


def _escalated_tracker_summary(items: tuple[RiskOpportunityTrackerItem, ...]) -> str:
    escalated = [item for item in items if item.status == "escalated"]
    if not escalated:
        return "None"
    return "; ".join(item.event_or_indicator for item in escalated)


def _valuation_summary(inputs: BuySideMemoInput) -> str:
    if inputs.fair_value_per_share <= 0:
        return (
            "Scenario-weighted fair value is not available from current sources because required live valuation inputs are missing. "
            "This report does not provide buy/sell advice."
        )
    return (
        f"Scenario-weighted fair value is {_money(inputs.fair_value_per_share)}. "
        "This is an analytical reference point, not an instruction to transact."
    )


def _valuation_assumption_note(inputs: BuySideMemoInput) -> str:
    if inputs.report_mode == "mock":
        return (
            "Mock valuation assumptions: scenario fair values come from fixture data. "
            "Enterprise value is modeled as 105% of equity value, using 100 mock shares outstanding. "
            "These assumptions are classified below and must be replaced before any source-backed report is produced."
        )
    if inputs.fair_value_per_share <= 0:
        return (
            "Live valuation note: source-backed scenario valuation is unavailable because price, annual earnings power, "
            "share count, or SEC filing fields are missing. The memo does not substitute mock figures in live mode."
        )
    return (
        "Live valuation assumptions: scenario fair values use sourced latest-available market price, SEC shares outstanding, "
        "and annual SEC net income where available. Bear/base/bull scenarios apply explicit model assumptions of 65%, 100%, "
        "and 125% of the current P/E anchor. These are estimates, not factual claims or transaction advice."
    )


def _data_quality_note(inputs: BuySideMemoInput) -> str:
    if inputs.report_mode == "mock":
        return "Mock data is suitable only for workflow testing. Real memos must cite factual claims, separate facts from assumptions, and show calculation inputs."
    return "Live mode does not silently use mock data. Missing data is marked unavailable, and source-backed inputs are required before valuation outputs become decision-useful."


def render_buy_side_memo(inputs: BuySideMemoInput) -> str:
    """Render a user-friendly buy-side equity research memo."""

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    valuation_summary = _valuation_summary(inputs)

    report = f"""# {inputs.company_name} ({inputs.ticker}) Buy-Side Equity Research Memo

Generated: {generated_at}

> Mock research output only. This memo does not provide buy, sell, or hold advice. All factual claims must be replaced with cited primary-source evidence before real use.

## Executive Dashboard

| Item | Current view |
| --- | --- |
| Company | {inputs.company_name} |
| Ticker | {inputs.ticker} |
| Archetype | {inputs.archetype_name} |
| AI value-chain role | {inputs.ai_value_chain_classification} |
| Scenario-weighted fair value | {_money_or_unavailable(inputs.fair_value_per_share)} |
| Bayesian intrinsic growth | {_pct(inputs.bayesian_growth.intrinsic_growth_estimate)} |
| Most likely growth regime | {inputs.bayesian_growth.most_likely_regime.value} |
| TAM-adjusted PEG | {inputs.tam_adjusted_peg.tam_adjusted_peg:.2f}x |
| GF-DMA health score | {inputs.gf_dma_health.overall_gf_dma_health_score:.1f}/100 |
| Escalated tracker items | {_escalated_tracker_summary(inputs.risk_opportunity_trackers)} |
| Report mode | {inputs.report_mode} |
| Data quality score | {inputs.data_quality_score:.1f}/100 |
| Calculation audit | {_calculation_audit_label(inputs)} |
| Latest price timestamp | {inputs.latest_price_timestamp} |
| Confidence level | {inputs.confidence_level} |

## One-Paragraph Investment View

{inputs.investment_view} {valuation_summary}

## AI Value-Chain Classification

{inputs.ai_value_chain_classification}. {inputs.business_summary}

## Financial Snapshot

{_dict_table(inputs.financial_snapshot)}

Valuation multiple snapshot:

{_dict_table(inputs.valuation_multiples)}

## Fiscal Period & TTM Basis

{_period_basis_markdown_table(inputs.period_basis_rows)}

## Valuation Scenarios

{_valuation_scenario_table(inputs.valuation_scenarios)}

| Summary | Value |
| --- | ---: |
| Probability-weighted fair value | {_money_or_unavailable(inputs.fair_value_per_share)} |

{_valuation_assumption_note(inputs)}

## Bayesian Intrinsic Growth View

{_bayesian_table(inputs.bayesian_growth)}

| Output | View |
| --- | --- |
| Most likely regime | {inputs.bayesian_growth.most_likely_regime.value} |
| Intrinsic growth estimate | {_pct(inputs.bayesian_growth.intrinsic_growth_estimate)} |
| Market-implied growth | {_pct(inputs.bayesian_growth.market_implied_growth)} |
| Market comparison | {inputs.bayesian_growth.market_implied_comparison} |
| FOMO risk score | {inputs.bayesian_growth.fomo_risk_score:.1f}/100 |

{inputs.bayesian_growth.explanation}

### Bayesian Growth Evidence Table

{_evidence_markdown_table(inputs.bayesian_growth_evidence)}

## TAM-Adjusted PEG View

| Metric | Value |
| --- | ---: |
| Traditional PEG | {inputs.tam_adjusted_peg.traditional_peg:.2f}x |
| TAM-adjusted PEG | {inputs.tam_adjusted_peg.tam_adjusted_peg:.2f}x |

**Interpretation:** {inputs.tam_adjusted_peg.quality_adjusted_interpretation}

{inputs.tam_adjusted_peg.explanation}

### TAM-Adjusted PEG Assumption Table

{_evidence_markdown_table(inputs.tam_assumptions)}

### Scoring Rubric Table

{_scoring_markdown_table(inputs.scoring_rubric)}

### Missing Evidence / Low Confidence Warnings

{_bullet_list(inputs.low_confidence_warnings)}

## GF-DMA Health View

| Component | Score |
| --- | ---: |
| Fundamental growth | {inputs.gf_dma_health.fundamental_growth_score:.1f}/100 |
| DMA trend | {inputs.gf_dma_health.dma_trend_score:.1f}/100 |
| Divergence | {inputs.gf_dma_health.divergence_score:.1f}/100 |
| Estimate revisions | {inputs.gf_dma_health.estimate_revision_score:.1f}/100 |
| Escape ratio | {inputs.gf_dma_health.escape_ratio:.3f}x |
| Overall GF-DMA health | {inputs.gf_dma_health.overall_gf_dma_health_score:.1f}/100 |

**Interpretation:** {inputs.gf_dma_health.interpretation}

{inputs.gf_dma_health.explanation}

## Entry-Price Framework

Scenario anchors:

{_scenario_anchor_table(inputs.valuation_scenarios)}

| Zone | Scenario range |
| --- | ---: |
| Conservative entry zone | Up to {_money_or_unavailable(inputs.entry_zones.conservative_entry_max)} |
| Reasonable accumulation zone | {_money_or_unavailable(inputs.entry_zones.reasonable_accumulation_min)} to {_money_or_unavailable(inputs.entry_zones.reasonable_accumulation_max)} |
| Expensive/wait zone | Above {_money_or_unavailable(inputs.entry_zones.expensive_wait_min)} |

The zones are derived from the probability-weighted scenario fair value when source-backed inputs are available. Conservative entry is set at a 25% discount to scenario-weighted fair value, reasonable accumulation spans the 25% to 5% discount band, and expensive/wait begins above the 5% discount threshold. If valuation inputs are unavailable, entry zones are marked unavailable. These zones are for entry discipline only and do not create an instruction to transact.

## Macro And Industry Impact

{_bullet_list(inputs.macro_industry_tracker)}

## Risk & Opportunity Tracker

{_tracker_markdown(inputs.risk_opportunity_trackers)}

## Recent Validated Developments

{_warnings_list(inputs.recent_validated_developments)}

## Pending Signals

{_warnings_list(inputs.pending_signals)}

## Required Monitoring Indicators

{_bullet_list(inputs.required_monitoring_indicators)}

## Catalysts

{_bullet_list(inputs.catalysts)}

## Risks

{_bullet_list(inputs.risks)}

## What changed since last review

{_change_table(inputs.changes_since_last_review)}

## What Would Change The View

{_bullet_list(inputs.view_change_triggers)}

## Data Quality And Confidence Level

| Item | Assessment |
| --- | --- |
| Data quality | {inputs.data_quality} |
| Confidence level | {inputs.confidence_level} |
| Data quality score | {inputs.data_quality_score:.1f}/100 |
| Calculation audit | {_calculation_audit_label(inputs)} |
| Latest price timestamp | {inputs.latest_price_timestamp} |
| Latest filing date | {inputs.latest_filing_date} |
| Latest financial data period | {inputs.latest_financial_data_period} |
| Latest macro data date | {inputs.latest_macro_data_date} |
| Latest news retrieval date | {inputs.latest_news_retrieval_date} |

{_data_quality_note(inputs)}

Missing data and connector warnings:

{_warnings_list(inputs.connector_warnings + inputs.missing_data_warnings)}

### Calculation Audit Status

{_calculation_audit_note(inputs)}

## Evidence Classification

{_evidence_claim_table(inputs.evidence_claims)}

## Sources

{_source_list(inputs.sources)}

## AnySearch Query Log

{_warnings_list(inputs.anysearch_query_log)}

## Final Monitoring Checklist

{_checklist(inputs.required_monitoring_indicators + inputs.macro_industry_tracker + inputs.catalysts + inputs.view_change_triggers)}
"""

    validation = validate_report_compliance(
        report_text=report,
        claims=inputs.evidence_claims,
        report_is_mock=inputs.is_mock,
    )
    if not validation.is_valid:
        raise ValueError("Report compliance validation failed: " + "; ".join(validation.errors))
    return report


def render_mock_buy_side_memo(
    company: CompanyMockData,
    previous_snapshot: MemoSnapshot | None = None,
) -> str:
    """Build a buy-side memo from current mock company fixtures."""

    return render_buy_side_memo(
        build_mock_buy_side_memo_input(company, previous_snapshot=previous_snapshot)
    )


def build_live_buy_side_memo_input(
    ticker: str,
    config: AppConfig,
    previous_snapshot: MemoSnapshot | None = None,
    use_source_cache: bool = False,
) -> BuySideMemoInput:
    """Build a live-mode memo input using source-specific connectors.

    Live mode never falls back to mock financial figures. Missing connector data
    is surfaced as unavailable with source warnings.
    """

    ticker = ticker.upper()
    profile = _profile_for_ticker(ticker)
    provider_bundle = collect_provider_data(ticker, config, use_source_cache=use_source_cache)
    market = provider_bundle.market
    sec = provider_bundle.sec
    macro = provider_bundle.macro
    ir = provider_bundle.ir
    industry = provider_bundle.industry
    news = provider_bundle.news
    anysearch = provider_bundle.anysearch

    connector_warnings = tuple(
        warning
        for warning in (
            *missing_key_warnings(config),
            *provider_bundle.warnings,
        )
        if warning
    )
    validated = validate_metrics(
        (
            ValidatedMetric(
                "price",
                market.latest_price,
                market.source_name,
                market.price_timestamp if market.price_timestamp != "Not available from current sources" else "",
                "actual" if market.latest_price is not None else "unavailable",
                market.warning,
            ),
            ValidatedMetric(
                "revenue",
                _provider_metric_value(provider_bundle, "revenue"),
                _provider_metric_source(provider_bundle, "revenue"),
                _provider_metric_period(provider_bundle, "revenue"),
                _provider_metric_type(provider_bundle, "revenue"),
            ),
        ),
        mock_data_used=False,
    )
    financial_snapshot = _live_financial_snapshot(sec, provider_bundle.financial_metrics)
    valuation_multiples, scenarios, fair_value, entry_zones, period_basis_rows = _live_valuation_outputs(market, sec, provider_bundle)
    growth_evidence = _live_growth_trend_evidence(sec, provider_bundle)
    filing_evidence = _live_filing_evidence(provider_bundle, ticker)
    search_evidence = build_search_evidence(anysearch) + hyperscaler_capex_evidence_from_source_cache(anysearch)
    scoring_rubric = build_scoring_rubric(
        ticker,
        growth_evidence,
        filing_evidence,
        search_evidence,
        market_cap=_market_cap_from_sources(market, sec, provider_bundle),
        shares_outstanding=_bundle_metric_number(provider_bundle, sec, "shares_outstanding"),
    )
    bayesian_growth = estimate_intrinsic_growth(
        BayesianGrowthInput(
            revenue_growth=growth_evidence.revenue_growth_trend or 0.0,
            gross_margin_trend=growth_evidence.gross_margin_trend or 0.0,
            operating_margin_trend=growth_evidence.operating_margin_trend or 0.0,
            free_cash_flow_trend=growth_evidence.free_cash_flow_trend or 0.0,
            backlog_or_rpo_growth=0.12 if _has_evidence(filing_evidence, ("backlog", "remaining performance obligations")) else 0.0,
            signed_customer_contracts=sum(1 for item in filing_evidence if "customer commitments" in item.name),
            hyperscaler_capex_exposure=0.75 if any(item.name == "Hyperscaler capex evidence" for item in search_evidence) else 0.0,
            estimate_revisions=_estimate_revision_signal(provider_bundle),
            ai_market_exposure=0.85 if ticker.upper() in {"NVDA", "AMD", "ARM", "AVGO", "TSM", "ASML", "NBIS"} else 0.35,
            market_implied_growth=_market_implied_growth_proxy(valuation_multiples, growth_evidence.revenue_growth_trend),
            stock_price_performance=_stock_price_signal(market),
            fundamental_performance=growth_evidence.revenue_growth_trend or 0.0,
            valuation_premium=_valuation_premium_proxy(valuation_multiples),
        )
    )
    eps_growth_assumption = model_eps_growth_assumption(
        _analyst_eps_growth(provider_bundle),
        growth_evidence.revenue_growth_trend,
        bayesian_growth.intrinsic_growth_estimate,
    )
    tam_adjusted_peg = _live_tam_adjusted_peg(valuation_multiples, scoring_rubric, eps_growth_assumption)
    gf_dma_health = _live_gf_dma(market, growth_evidence, valuation_multiples, provider_bundle)
    search_results = tuple(
        result
        for result in anysearch
        if result.url and result.status != "irrelevant"
    )
    trackers = update_trackers_from_search_results(
        load_risk_opportunity_trackers(ticker),
        search_results,
    )
    macro_tracker = tuple(_macro_indicator_summary(item) for item in macro)
    sources = _live_sources(market, sec, ir, macro, industry, news, anysearch)
    data_source_status = _data_source_status(provider_bundle)
    current_snapshot = MemoSnapshot(
        ticker=ticker,
        price=market.latest_price or 0.0,
        valuation_multiples=valuation_multiples,
        revenue_growth=growth_evidence.revenue_growth_trend or 0.0,
        margin_trend=growth_evidence.operating_margin_trend or 0.0,
        free_cash_flow_trend=growth_evidence.free_cash_flow_trend or 0.0,
        bayesian_growth_probabilities={},
        tam_adjusted_peg_score=tam_adjusted_peg.tam_adjusted_peg,
        gf_dma_health_score=gf_dma_health.overall_gf_dma_health_score,
        catalysts=tuple(result.title for result in news if result.confidence != "low"),
        risks=tuple(item.event_or_indicator for item in trackers if item.impact_if_validated == "negative"),
        entry_price_zone={},
    )
    calculation_audit = audit_calculations()
    return BuySideMemoInput(
        company_name=profile["company_name"],
        ticker=ticker,
        archetype_name=profile["archetype"],
        business_summary=profile["business_summary"],
        investment_view=(
            "Live mode is source-first. Current source coverage is incomplete, so this memo is a research skeleton with unavailable fields rather than invented figures."
        ),
        ai_value_chain_classification=profile["ai_value_chain_classification"],
        financial_snapshot=financial_snapshot,
        valuation_multiples=valuation_multiples,
        period_basis_rows=period_basis_rows,
        valuation_scenarios=scenarios,
        fair_value_per_share=fair_value,
        entry_zones=entry_zones,
        bayesian_growth=bayesian_growth,
        tam_adjusted_peg=tam_adjusted_peg,
        gf_dma_health=gf_dma_health,
        macro_industry_tracker=macro_tracker
        + tuple(f"{signal.indicator_name}: {signal.latest_signal} ({signal.source})" for signal in industry),
        required_monitoring_indicators=tuple(item.event_or_indicator for item in trackers[:8]),
        catalysts=tuple(result.title for result in news if result.confidence in {"high", "medium"} and result.status != "rumor") or ("Not available from current sources",),
        risks=tuple(item.event_or_indicator for item in trackers if item.impact_if_validated == "negative") or ("Not available from current sources",),
        risk_opportunity_trackers=trackers,
        changes_since_last_review=compare_memo_snapshots(previous_snapshot, current_snapshot),
        view_change_triggers=(
            "Source-backed financial statement data becomes available from SEC, yfinance, yahooquery, or optional FMP.",
            "yfinance or yahooquery returns latest available price and moving averages.",
            "Company IR or SEC filings confirm guidance, backlog, or risk-factor changes.",
            "AnySearch identifies a primary source requiring tracker status update.",
        ),
        data_quality="Live mode; missing data is marked unavailable and not replaced with mock data.",
        confidence_level="Low until required live connectors return source-backed financial, market, macro, and company data.",
        evidence_claims=_live_evidence_claims(ticker, market, sec),
        is_mock=False,
        sources=sources,
        report_mode="live",
        connector_warnings=connector_warnings,
        missing_data_warnings=validated.missing_data_warnings,
        data_quality_score=validated.data_quality_score,
        latest_price_timestamp=market.price_timestamp,
        latest_filing_date=_latest_filing_date(sec),
        latest_financial_data_period=_provider_metric_period(provider_bundle, "revenue") or "Not available from current sources",
        latest_macro_data_date=_latest_macro_date(macro),
        latest_news_retrieval_date=news[0].retrieved_at if news else "Not available from current sources",
        anysearch_query_log=_search_query_log(anysearch, use_source_cache),
        recent_validated_developments=tuple(
            f"{result.title} ({result.source_name}; {result.source_type}; {result.confidence})"
            for result in search_results
            if result.confidence == "high" and result.status == "confirmed"
        ) or ("No recent validated developments from current sources.",),
        pending_signals=tuple(item.event_or_indicator for item in trackers if item.status == "pending") or ("No pending tracker signals configured.",),
        source_discovery_results=search_results,
        latest_price=market.latest_price or 0.0,
        data_source_status=data_source_status,
        evidence_classification=_evidence_classification(growth_evidence, filing_evidence, search_evidence, eps_growth_assumption),
        bayesian_growth_evidence=growth_evidence.evidence_items
        + filing_evidence
        + tuple(item for item in search_evidence if item.name == "Hyperscaler capex evidence")
        + (EvidenceItem("Estimate revisions", "structured data", "unavailable", "FMP estimates", explanation="No configured structured estimate-revision provider returned usable data.", confidence="low", warning="Model leaves estimate revisions neutral until structured evidence is available."),),
        tam_assumptions=(eps_growth_assumption,),
        scoring_rubric=scoring_rubric,
        low_confidence_warnings=_low_confidence_warnings(growth_evidence.evidence_items + filing_evidence + search_evidence + (eps_growth_assumption,), scoring_rubric),
        calculation_audit_passed=calculation_audit.passed,
        calculation_audit_warnings=tuple(
            f"{failure.formula_name}: {failure.error}" for failure in calculation_audit.failures
        ),
    )


def build_mock_buy_side_memo_input(
    company: CompanyMockData,
    previous_snapshot: MemoSnapshot | None = None,
) -> BuySideMemoInput:
    """Build structured mock memo inputs for any report renderer."""

    archetype = archetype_for_company(company)
    scenarios = _mock_scenario_valuations(company)
    fair_value = probability_weighted_fair_value(scenarios)
    entry_zones = calculate_entry_zones(fair_value)
    bayesian_growth = _mock_bayesian_growth(company, archetype)
    tam_adjusted_peg = _mock_tam_adjusted_peg(company, bayesian_growth)
    gf_dma_health = _mock_gf_dma_health(company, fair_value, archetype)
    current_snapshot = _mock_snapshot_from_components(
        company,
        fair_value,
        entry_zones,
        bayesian_growth,
        tam_adjusted_peg,
        gf_dma_health,
    )
    calculation_audit = audit_calculations()

    return BuySideMemoInput(
        company_name=company.name,
        ticker=company.ticker,
        archetype_name=f"{archetype.key} ({archetype.display_name})",
        business_summary=company.business_summary,
        investment_view=archetype.investment_view,
        ai_value_chain_classification=_mock_ai_classification(company),
        financial_snapshot=company.financial_snapshot,
        valuation_multiples=company.valuation_multiples,
        period_basis_rows=_mock_period_basis_rows(company),
        valuation_scenarios=scenarios,
        fair_value_per_share=fair_value,
        entry_zones=entry_zones,
        bayesian_growth=bayesian_growth,
        tam_adjusted_peg=tam_adjusted_peg,
        gf_dma_health=gf_dma_health,
        macro_industry_tracker=company.macro_industry_tracker,
        required_monitoring_indicators=archetype.required_monitoring_indicators,
        catalysts=company.catalysts,
        risks=company.risks,
        risk_opportunity_trackers=load_risk_opportunity_trackers(company.ticker),
        changes_since_last_review=compare_memo_snapshots(
            previous_snapshot,
            current_snapshot,
        ),
        view_change_triggers=(
            "Primary-source evidence materially changes revenue, margin, or FCF assumptions.",
            "Estimate revisions diverge from price momentum.",
            "GF-DMA trend breaks down or overextension risk rises.",
            "Macro, export-control, or industry-cycle risks change materially.",
        )
        + archetype.view_change_triggers,
        data_quality="Mock data only; source-backed validation not yet implemented.",
        confidence_level="Low until real data connectors, citations, and calculations are added.",
        evidence_claims=_mock_evidence_claims(
            company,
            scenarios,
            fair_value,
            entry_zones,
            bayesian_growth,
            tam_adjusted_peg,
            gf_dma_health,
        ),
        is_mock=True,
        sources=(
            "TODO: SEC filings and annual reports.",
            "TODO: Company investor relations, earnings releases, and presentations.",
            "TODO: Official macroeconomic and industry datasets.",
            "TODO: Licensed market and estimate data where permitted.",
        ),
        data_source_status=(
            DataSourceStatus("FMP", "missing", "not used", "unavailable", "Mock report mode; FMP connector not used.", "none"),
            DataSourceStatus("EODHD", "missing", "not used", "unavailable", "Mock report mode; EODHD connector not used.", "none"),
            DataSourceStatus("SEC EDGAR", "missing", "not used", "unavailable", "Mock report mode; SEC connector not used.", "none"),
            DataSourceStatus("FRED", "missing", "not used", "unavailable", "Mock report mode; macro connector not used.", "none"),
            DataSourceStatus("AnySearch", "missing", "not used", "unavailable", "Mock report mode; AnySearch connector not used.", "none"),
            DataSourceStatus("Company IR", "missing", "not used", "unavailable", "Mock report mode; IR connector not used.", "none"),
            DataSourceStatus("Industry sources", "missing", "not used", "unavailable", "Mock report mode; industry connector not used.", "none"),
            DataSourceStatus("Mock data", "configured", "used", "available", "Explicit mock mode uses fixture data.", "local fixture"),
        ),
        calculation_audit_passed=calculation_audit.passed,
        calculation_audit_warnings=tuple(
            f"{failure.formula_name}: {failure.error}" for failure in calculation_audit.failures
        ),
    )


def _profile_for_ticker(ticker: str) -> dict[str, str]:
    profiles = {
        "NVDA": ("NVIDIA Corporation", "AI accelerator leader", "AI accelerator platform and data-center infrastructure supplier"),
        "AMD": ("Advanced Micro Devices, Inc.", "AI accelerator challenger", "AI accelerator challenger and diversified compute supplier"),
        "ASML": ("ASML Holding N.V.", "semicap equipment bottleneck", "Semiconductor capital equipment bottleneck supplier"),
        "TSM": ("Taiwan Semiconductor Manufacturing Company Limited", "advanced foundry", "Advanced foundry and AI silicon manufacturing platform"),
        "TSMC": ("Taiwan Semiconductor Manufacturing Company Limited", "advanced foundry", "Advanced foundry and AI silicon manufacturing platform"),
        "ARM": ("Arm Holdings plc", "processor IP platform", "Processor IP platform with edge and data-center AI optionality"),
        "MU": ("Micron Technology, Inc.", "AI memory supplier", "Memory supplier with HBM, DRAM, and NAND exposure"),
        "AVGO": ("Broadcom Inc.", "AI networking and custom silicon", "AI networking, custom silicon, and infrastructure software supplier"),
        "MSFT": ("Microsoft Corporation", "hyperscaler AI platform", "Hyperscaler, enterprise software, AI platform, and cloud infrastructure"),
        "GOOGL": ("Alphabet Inc.", "AI cloud and digital advertising platform", "Hyperscaler, AI models, digital advertising, and cloud platform"),
        "AMZN": ("Amazon.com, Inc.", "AI cloud infrastructure platform", "Hyperscaler, AI cloud infrastructure, ecommerce, and logistics platform"),
        "META": ("Meta Platforms, Inc.", "AI-driven consumer platform", "AI-driven consumer internet, advertising, models, and infrastructure"),
        "ORCL": ("Oracle Corporation", "enterprise AI cloud infrastructure", "Enterprise software, database platform, and AI cloud infrastructure"),
        "PLTR": ("Palantir Technologies Inc.", "AI software platform", "AI software, data integration, and enterprise analytics platform"),
        "NBIS": ("Nebius Group N.V.", "speculative AI infrastructure", "AI cloud infrastructure and neocloud compute platform"),
    }
    name, archetype, classification = profiles.get(
        ticker,
        (ticker, "AI technology company", "AI and technology value-chain participant"),
    )
    return {
        "company_name": name,
        "archetype": archetype,
        "ai_value_chain_classification": classification,
        "business_summary": "Live source-backed business summary is not available from current sources until SEC, IR, and company-release connectors return validated content.",
    }


def _live_financial_snapshot(sec: object, provider_metrics: dict[str, object]) -> dict[str, str]:
    metrics = getattr(sec, "metrics", {})
    sec_unavailable_reason = ""
    if not getattr(sec, "cik", "") and getattr(sec, "warning", ""):
        sec_unavailable_reason = str(getattr(sec, "warning", ""))
    labels = {
        "revenue": "Revenue",
        "gross_profit": "Gross profit",
        "operating_income": "Operating income",
        "net_income": "Net income",
        "cash_and_equivalents": "Cash and equivalents",
        "total_debt": "Total debt",
        "operating_cash_flow": "Operating cash flow",
        "capital_expenditure": "Capital expenditure",
        "free_cash_flow": "Free cash flow",
        "shares_outstanding": "Shares outstanding",
        "diluted_eps": "Diluted EPS",
    }
    output = {}
    for key, label in labels.items():
        provider_metric = provider_metrics.get(key)
        if provider_metric is not None and getattr(provider_metric, "value", None) is not None:
            output[label] = (
                f"{getattr(provider_metric, 'value')} | Source: {getattr(provider_metric, 'source_name', '')} "
                f"| Period: {getattr(provider_metric, 'fiscal_period', '')} | {getattr(provider_metric, 'note', '')}"
            )
        else:
            item = metrics.get(key, {})
            output[label] = sec_unavailable_reason or str(item.get("source", "Unavailable: XBRL tag not found"))
    return output


def _unavailable_scenarios() -> tuple[ScenarioValuation, ...]:
    return (
        ScenarioValuation("Bear", 0.0, 0.0, 0.0, 0.25),
        ScenarioValuation("Base", 0.0, 0.0, 0.0, 0.50),
        ScenarioValuation("Bull", 0.0, 0.0, 0.0, 0.25),
    )


def _live_valuation_outputs(
    market: object,
    sec: object,
    provider_bundle: ProviderDataBundle | None = None,
) -> tuple[dict[str, str], tuple[ScenarioValuation, ...], float, EntryZones, tuple[PeriodBasisRow, ...]]:
    market_cap = _market_cap_from_sources(market, sec, provider_bundle)
    ttm_metrics = _ttm_metrics_for_valuation(sec, provider_bundle)
    revenue = ttm_metrics["revenue"]
    ebitda = ttm_metrics["ebitda"]
    net_income = ttm_metrics["net_income"]
    free_cash_flow = ttm_metrics["free_cash_flow"]
    gross_profit = ttm_metrics["gross_profit"]
    operating_income = ttm_metrics["operating_income"]
    cash = _bundle_metric_number(provider_bundle, sec, "cash_and_equivalents")
    debt = _bundle_metric_number(provider_bundle, sec, "total_debt")
    shares = _bundle_metric_number(provider_bundle, sec, "shares_outstanding")
    eps_raw = _bundle_metric_number(provider_bundle, sec, "diluted_eps")
    enterprise_value_from_provider = _bundle_metric_number(provider_bundle, sec, "enterprise_value")

    ev_value = None
    if enterprise_value_from_provider is not None:
        ev_value = enterprise_value_from_provider
    elif market_cap is not None and cash is not None and debt is not None:
        ev_value = enterprise_value(market_cap, debt, cash)

    market_period = point_in_time_period(str(getattr(market, "price_timestamp", "")), str(getattr(market, "source_name", "Market data")))
    market_cap_metric = PeriodMetric("market_cap", market_cap, market_period, str(getattr(market, "source_name", "Market data")))
    ev_metric = PeriodMetric("enterprise_value", ev_value, market_period, "Internal calculation")
    ev_sales_calc = period_aware_ev_to_sales(ev_metric, revenue)
    ev_ebitda_calc = period_aware_ev_to_ebitda(ev_metric, ebitda)
    pe_calc = period_aware_price_to_earnings(market_cap_metric, net_income)
    p_fcf_calc = period_aware_price_to_fcf(market_cap_metric, free_cash_flow)
    ps_calc = period_aware_price_to_sales(market_cap_metric, revenue)
    gross_margin_calc = period_aware_margin("Gross margin", gross_profit, revenue, "gross_profit")
    operating_margin_calc = period_aware_margin("Operating margin", operating_income, revenue, "operating_income")
    net_margin_calc = period_aware_margin("Net margin", net_income, revenue, "net_income")
    fcf_margin_calc = period_aware_margin("FCF margin", free_cash_flow, revenue, "free_cash_flow")
    period_rows = _period_basis_rows(
        (
            revenue,
            ebitda,
            net_income,
            free_cash_flow,
            gross_profit,
            operating_income,
        ),
        (
            ev_sales_calc,
            ev_ebitda_calc,
            pe_calc,
            p_fcf_calc,
            ps_calc,
            gross_margin_calc,
            operating_margin_calc,
            net_margin_calc,
            fcf_margin_calc,
        ),
    )

    multiples = {
        "Latest price": _amount_or_unavailable(_number(getattr(market, "latest_price", None)), _market_missing_reason(market)),
        "Price timestamp": str(getattr(market, "price_timestamp", "Unavailable: market data unavailable")),
        "20DMA": _amount_or_unavailable(_number(getattr(market, "moving_average_20", None)), "Unavailable: source does not provide this field"),
        "50DMA": _amount_or_unavailable(_number(getattr(market, "moving_average_50", None)), "Unavailable: source does not provide this field"),
        "100DMA": _amount_or_unavailable(_number(getattr(market, "moving_average_100", None)), "Unavailable: source does not provide this field"),
        "200DMA": _amount_or_unavailable(_number(getattr(market, "moving_average_200", None)), "Unavailable: source does not provide this field"),
        "Market cap": _amount_or_unavailable(market_cap),
        "Enterprise value": _amount_or_unavailable(ev_value),
        "EV/Sales": _period_calc_display(ev_sales_calc),
        "EV/EBITDA": _period_calc_display(ev_ebitda_calc),
        "P/E": _period_calc_display(pe_calc),
        "P/FCF": _period_calc_display(p_fcf_calc),
        "P/S": _period_calc_display(ps_calc),
        "Revenue growth": _metric_text(provider_bundle, "revenue_growth"),
        "Gross margin": _period_calc_percent_display(gross_margin_calc),
        "Operating margin": _period_calc_percent_display(operating_margin_calc),
        "Net margin": _period_calc_percent_display(net_margin_calc),
        "FCF margin": _period_calc_percent_display(fcf_margin_calc),
        "Diluted EPS": _amount_or_unavailable(eps_raw, "Unavailable: EPS missing"),
        "Analyst EPS growth": _metric_text(provider_bundle, "analyst_eps_growth"),
        "Earnings date": _metric_text(provider_bundle, "earnings_date"),
    }

    price = _number(getattr(market, "latest_price", None))
    if market_cap is None or net_income.value is None or shares in (None, 0) or price is None or pe_calc.value is None:
        return multiples, _unavailable_scenarios(), 0.0, EntryZones(0.0, 0.0, 0.0, 0.0), period_rows

    earnings_per_share = net_income.value / shares
    current_pe = pe_calc.value
    scenarios = (
        _live_multiple_scenario("Bear case", earnings_per_share, current_pe * 0.65, shares, 0.35),
        _live_multiple_scenario("Base case", earnings_per_share, current_pe, shares, 0.45),
        _live_multiple_scenario("Bull case", earnings_per_share, current_pe * 1.25, shares, 0.20),
    )
    fair_value = probability_weighted_fair_value(scenarios)
    return multiples, scenarios, fair_value, calculate_entry_zones(fair_value), period_rows


def _ttm_metrics_for_valuation(sec: object, provider_bundle: ProviderDataBundle | None) -> dict[str, PeriodMetric]:
    histories = getattr(sec, "metrics_history", {}) or {}
    ttm: dict[str, PeriodMetric] = {}
    for metric_name in (
        "revenue",
        "gross_profit",
        "operating_income",
        "ebitda",
        "net_income",
        "operating_cash_flow",
        "capital_expenditure",
        "diluted_eps",
    ):
        sec_ttm = _sec_ttm_metric(histories, metric_name)
        ttm[metric_name] = sec_ttm if sec_ttm.value is not None else _provider_ttm_metric(provider_bundle, metric_name)
    free_cash_flow = calculate_ttm_free_cash_flow(ttm["operating_cash_flow"], ttm["capital_expenditure"])
    ttm["free_cash_flow"] = free_cash_flow if free_cash_flow.value is not None else _provider_ttm_metric(provider_bundle, "free_cash_flow")
    return ttm


def _sec_ttm_metric(histories: dict[str, tuple[dict[str, object], ...]], metric_name: str) -> PeriodMetric:
    rows = histories.get(metric_name, ())
    quarterly_metrics = tuple(period_metric_from_sec_row(metric_name, row) for row in rows)
    return calculate_ttm_metric(metric_name, quarterly_metrics)


def _provider_ttm_metric(provider_bundle: ProviderDataBundle | None, metric_name: str) -> PeriodMetric:
    metric = provider_bundle.financial_metrics.get(metric_name) if provider_bundle is not None else None
    if metric is None or getattr(metric, "value", None) is None:
        return _unavailable_period_metric(metric_name, "Unavailable: TTM source metric missing")
    period = getattr(metric, "period", None) or normalize_period_label(
        str(getattr(metric, "fiscal_period", "")),
        provider=str(getattr(metric, "source_name", "")),
        as_of_date=str(getattr(metric, "retrieved_at", ""))[:10],
    )
    if period.period_type != "ttm":
        return _unavailable_period_metric(
            metric_name,
            f"Unavailable: {metric_name} must be TTM for valuation multiple; got {period.period_type}",
        )
    return PeriodMetric(
        metric_name,
        _number(getattr(metric, "value", None)),
        period,
        str(getattr(metric, "source_name", "Structured provider")),
        str(getattr(metric, "source_url", "")),
        (period.label,),
        warning=str(getattr(metric, "note", "")),
    )


def _unavailable_period_metric(metric_name: str, warning: str) -> PeriodMetric:
    period = FiscalPeriod(
        period_type="ttm",
        source_period_label="TTM unavailable",
        confidence="low",
        warning=warning,
    )
    return PeriodMetric(metric_name, None, period, "Not available from current sources", warning=warning)


def _period_calc_display(calculation: object) -> str:
    value = getattr(calculation, "value", None)
    warning = getattr(calculation, "warning", "")
    if value is None or warning:
        return warning or "Unavailable: period-aware calculation failed"
    return f"{float(value):.2f}x"


def _period_calc_percent_display(calculation: object) -> str:
    value = getattr(calculation, "value", None)
    warning = getattr(calculation, "warning", "")
    if value is None or warning:
        return warning or "Unavailable: period-aware calculation failed"
    return f"{float(value):.1%}"


def _period_basis_rows(financial_metrics: tuple[PeriodMetric, ...], calculations: tuple[object, ...]) -> tuple[PeriodBasisRow, ...]:
    rows = [
        PeriodBasisRow(
            metric=metric.name.replace("_", " ").title(),
            period_basis=metric.period.period_type.upper(),
            source=metric.source_name,
            periods_used=", ".join(metric.source_lineage) or metric.period.label,
            warning=metric.warning or metric.period.warning or "None",
        )
        for metric in financial_metrics
    ]
    for calculation in calculations:
        rows.append(
            PeriodBasisRow(
                metric=str(getattr(calculation, "metric_name", "Calculation")),
                period_basis=str(getattr(calculation, "output_period_basis", "")),
                source="Internal calculation",
                periods_used="; ".join(
                    f"{key}: {value}"
                    for key, value in getattr(calculation, "input_periods", {}).items()
                ),
                warning=str(getattr(calculation, "warning", "") or "None"),
            )
        )
    return tuple(rows)


def _mock_period_basis_rows(company: CompanyMockData) -> tuple[PeriodBasisRow, ...]:
    return (
        PeriodBasisRow("Revenue", "Mock annual", "Mock fixture", "Mock company scenario period", "Mock data; not source-backed."),
        PeriodBasisRow("Net income", "Mock annual", "Mock fixture", "Mock company scenario period", "Mock data; not source-backed."),
        PeriodBasisRow("Valuation multiples", "Mock annual", "Mock fixture", "Mock company scenario period", "Mock data; not source-backed."),
    )


def _live_growth_trend_evidence(sec: object, provider_bundle: ProviderDataBundle | None) -> object:
    histories = getattr(sec, "metrics_history", {}) or {}
    return build_growth_trend_evidence(
        _history_values(histories, "revenue", provider_bundle),
        _history_values(histories, "gross_profit", provider_bundle),
        _history_values(histories, "operating_income", provider_bundle),
        _history_values(histories, "operating_cash_flow", provider_bundle),
        _history_values(histories, "capital_expenditure", provider_bundle),
        source_name="SEC EDGAR company facts / structured fallback",
    )


def _history_values(histories: dict[str, tuple[dict[str, object], ...]], metric_name: str, provider_bundle: ProviderDataBundle | None) -> tuple[float, ...]:
    values = tuple(
        value
        for value in (_number(row.get("value")) for row in histories.get(metric_name, ()))
        if value is not None
    )
    if len(values) >= 2:
        return values
    fallback = _provider_metric_value(provider_bundle, metric_name) if provider_bundle is not None else None
    fallback_number = _number(fallback)
    return (fallback_number,) if fallback_number is not None else ()


def _live_filing_evidence(provider_bundle: ProviderDataBundle, ticker: str) -> tuple[EvidenceItem, ...]:
    text_parts = []
    for source in getattr(provider_bundle.ir, "sources", ()):
        text_parts.append(f"{getattr(source, 'title', '')} {getattr(source, 'source_type', '')} {getattr(source, 'url', '')}")
    text_parts.extend(
        f"{result.title} {result.summary} {result.snippet} {result.reason_for_classification}"
        for result in provider_bundle.anysearch
        if result.source_type in {"primary_company_source", "sec_filing", "official_government", "industry_body"}
    )
    text_parts.extend(item.evidence_summary for item in load_risk_opportunity_trackers(ticker) if item.evidence_summary)
    return extract_filing_evidence(
        " ".join(text_parts),
        source_name="SEC filings / company IR / official source-cache summaries",
    )


def _has_evidence(items: tuple[EvidenceItem, ...], names: tuple[str, ...]) -> bool:
    lowered_names = tuple(name.lower() for name in names)
    return any(any(name in item.name.lower() for name in lowered_names) for item in items)


def _estimate_revision_signal(provider_bundle: ProviderDataBundle) -> float:
    if provider_bundle.estimates:
        return 0.05
    return 0.0


def _analyst_eps_growth(provider_bundle: ProviderDataBundle) -> float | None:
    current_eps = _bundle_metric_number(provider_bundle, provider_bundle.sec, "diluted_eps")
    estimated_eps = _number(getattr(provider_bundle.estimates.get("estimated_eps_avg"), "value", None))
    if current_eps is None or estimated_eps is None or current_eps <= 0:
        return None
    return max(0.0, estimated_eps / current_eps - 1)


def _stock_price_signal(market: object) -> float:
    price = _number(getattr(market, "latest_price", None))
    previous = _number(getattr(market, "previous_close", None))
    if price is None or previous in (None, 0):
        return 0.0
    return price / previous - 1


def _market_implied_growth_proxy(valuation_multiples: dict[str, str], fallback_growth: float | None) -> float:
    pe = _safe_multiple(valuation_multiples.get("P/E", ""))
    if pe is None or pe <= 0:
        return max(0.0, fallback_growth or 0.0)
    baseline_growth_pe = 25.0
    premium = max(0.0, pe / baseline_growth_pe - 1)
    return max(0.0, min(0.60, 0.08 + premium * 0.12))


def _valuation_premium_proxy(valuation_multiples: dict[str, str]) -> float:
    pe = _safe_multiple(valuation_multiples.get("P/E", ""))
    if pe is None:
        return 0.0
    return max(0.0, pe / 35.0 - 1)


def _live_tam_adjusted_peg(
    valuation_multiples: dict[str, str],
    scoring_rubric: tuple[ScoredAssumption, ...],
    eps_growth: EvidenceItem,
) -> TamAdjustedPegResult:
    pe = _safe_multiple(valuation_multiples.get("P/E", ""))
    expected_growth = _percent_text_to_float(eps_growth.value)
    if pe is None or expected_growth is None or expected_growth <= 0:
        return TamAdjustedPegResult(
            traditional_peg=0.0,
            tam_adjusted_peg=0.0,
            quality_adjusted_interpretation="Not available from current sources",
            explanation=_live_tam_unavailable_explanation(valuation_multiples),
        )
    return calculate_tam_adjusted_peg(
        TamAdjustedPegInput(
            pe_ratio=pe,
            expected_eps_growth=expected_growth,
            tam_score=_score_value(scoring_rubric, "TAM/SAM runway score", 3),
            business_quality_score=_score_value(scoring_rubric, "Business quality score", 3),
            cyclicality_score=_score_value(scoring_rubric, "Cyclicality score", 3),
            dilution_risk_score=_score_value(scoring_rubric, "Dilution risk score", 3),
            execution_risk_score=_score_value(scoring_rubric, "Execution risk score", 3),
        )
    )


def _score_value(scores: tuple[ScoredAssumption, ...], name: str, default: int) -> int:
    return next((score.score for score in scores if score.name == name), default)


def _safe_multiple(value: str) -> float | None:
    return _number(str(value).replace("x", ""))


def _percent_text_to_float(value: str) -> float | None:
    number = _number(str(value).replace("%", ""))
    if number is None:
        return None
    return number / 100


def _evidence_classification(
    growth_evidence: object,
    filing_evidence: tuple[EvidenceItem, ...],
    search_evidence: tuple[EvidenceItem, ...],
    eps_growth: EvidenceItem,
) -> tuple[EvidenceItem, ...]:
    return (
        *getattr(growth_evidence, "evidence_items", ()),
        *filing_evidence,
        *search_evidence,
        eps_growth,
    )


def _low_confidence_warnings(items: tuple[EvidenceItem, ...], scores: tuple[ScoredAssumption, ...]) -> tuple[str, ...]:
    warnings = [f"{item.name}: {item.warning}" for item in items if item.warning]
    warnings.extend(f"{score.name}: {score.warning}" for score in scores if score.warning)
    return tuple(warnings) or ("No low-confidence evidence warnings generated.",)


def _live_tam_unavailable_explanation(valuation_multiples: dict[str, str]) -> str:
    pe = valuation_multiples.get("P/E", "")
    if pe and "Unavailable" not in pe and "Not available" not in pe:
        return (
            f"TAM-adjusted PEG is unavailable even though source-backed P/E is available ({pe}). "
            "The missing inputs are forward EPS growth plus explicit TAM runway, business-quality, "
            "cyclicality, dilution, execution-risk, customer-concentration, and moat scores."
        )
    return (
        "TAM-adjusted PEG is unavailable because source-backed P/E and forward EPS growth inputs are unavailable. "
        "Do not infer valuation support from missing data."
    )


def _live_multiple_scenario(
    name: str,
    earnings_per_share: float,
    pe_multiple: float,
    shares: float,
    probability: float,
) -> ScenarioValuation:
    fair_value_per_share = earnings_per_share * pe_multiple
    equity_value = fair_value_per_share * shares
    return ScenarioValuation(
        name=name,
        enterprise_value=equity_value,
        equity_value=equity_value,
        fair_value_per_share=fair_value_per_share,
        probability=probability,
    )


def _market_cap_from_sources(market: object, sec: object, provider_bundle: ProviderDataBundle | None = None) -> float | None:
    market_cap = _number(getattr(market, "market_cap", None))
    if market_cap is not None:
        return market_cap
    metric_market_cap = _bundle_metric_number(provider_bundle, sec, "market_cap")
    if metric_market_cap is not None:
        return metric_market_cap
    price = _number(getattr(market, "latest_price", None))
    shares = _bundle_metric_number(provider_bundle, sec, "shares_outstanding")
    if price is None or shares is None:
        return None
    return price * shares


def _bundle_metric_number(provider_bundle: ProviderDataBundle | None, sec: object, metric_name: str) -> float | None:
    if provider_bundle is not None:
        metric = provider_bundle.financial_metrics.get(metric_name)
        if metric is not None:
            return _number(getattr(metric, "value", None))
    return _metric_number(sec, metric_name)


def _annualized_income_metric_number(provider_bundle: ProviderDataBundle | None, sec: object, metric_name: str) -> float | None:
    value = _bundle_metric_number(provider_bundle, sec, metric_name)
    if value is None:
        return None
    metric = provider_bundle.financial_metrics.get(metric_name) if provider_bundle is not None else None
    source_name = str(getattr(metric, "source_name", ""))
    provider = str(getattr(metric, "provider", ""))
    if source_name == "SEC EDGAR" or provider == "SEC":
        return value * 4
    return value


def _metric_text(provider_bundle: ProviderDataBundle | None, metric_name: str) -> str:
    if provider_bundle is None:
        return "Unavailable: provider bundle missing"
    metric = provider_bundle.estimates.get(metric_name) or provider_bundle.earnings_calendar.get(metric_name) or provider_bundle.financial_metrics.get(metric_name)
    if metric is None or getattr(metric, "value", None) in (None, ""):
        return "Unavailable: source does not provide this field"
    return f"{getattr(metric, 'value')} | Source: {getattr(metric, 'source_name', '')}"


def _metric_number(sec: object, metric_name: str, annual_only: bool = False) -> float | None:
    metric = getattr(sec, "metrics", {}).get(metric_name, {})
    if annual_only and not _is_annual_metric(metric):
        return None
    return _number(metric.get("value"))


def _is_annual_metric(metric: dict[str, object]) -> bool:
    form = str(metric.get("form", "")).upper()
    fp = str(metric.get("fp", "")).upper()
    frame = str(metric.get("frame", "")).upper()
    return form == "10-K" or fp == "FY" or (frame.startswith("CY") and "Q" not in frame)


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _amount_or_unavailable(value: float | None, reason: str = "Unavailable: required source field missing") -> str:
    if value is None:
        return reason
    return _money(value)


def _multiple_or_unavailable(function: object, first: float | None, second: float | None, reason: str = "Unavailable: required source field missing") -> str:
    if first is None or second is None:
        return reason
    try:
        return f"{function(first, second):.2f}x"  # type: ignore[misc]
    except ValueError:
        return reason


def _market_missing_reason(market: object) -> str:
    warning = str(getattr(market, "warning", ""))
    if "API_KEY missing" in warning:
        details = ["API key missing"]
        if "Stooq unsupported" in warning or "404" in warning:
            details.append("Stooq fallback unsupported or returned 404")
        if "rate limit" in warning or "429" in warning:
            details.append("Yahoo fallback returned rate limit")
        return "Unavailable: " + "; ".join(details)
    if "rate limit" in warning or "429" in warning:
        return "Unavailable: provider returned rate limit"
    if warning:
        return warning
    return "Unavailable: market data source did not return price"


def _data_source_status(provider_bundle: ProviderDataBundle) -> tuple[DataSourceStatus, ...]:
    return tuple(
        DataSourceStatus(
            category=status.provider,
            configured=status.configured,
            used=status.used,
            availability=status.availability,
            reason=status.reason,
            last_successful_retrieval=status.last_successful_retrieval,
        )
        for status in provider_bundle.statuses
    )


def _provider_metric_value(provider_bundle: ProviderDataBundle, metric_name: str) -> object:
    metric = provider_bundle.financial_metrics.get(metric_name)
    return getattr(metric, "value", None) if metric else None


def _provider_metric_source(provider_bundle: ProviderDataBundle, metric_name: str) -> str:
    metric = provider_bundle.financial_metrics.get(metric_name)
    return getattr(metric, "source_name", "Unavailable: source missing") if metric else "Unavailable: source missing"


def _provider_metric_period(provider_bundle: ProviderDataBundle, metric_name: str) -> str:
    metric = provider_bundle.financial_metrics.get(metric_name)
    return getattr(metric, "fiscal_period", "") if metric else ""


def _provider_metric_type(provider_bundle: ProviderDataBundle, metric_name: str) -> str:
    metric = provider_bundle.financial_metrics.get(metric_name)
    return getattr(metric, "data_type", "unavailable") if metric else "unavailable"


def _live_gf_dma(
    market: object,
    growth_evidence: object | None = None,
    valuation_multiples: dict[str, str] | None = None,
    provider_bundle: ProviderDataBundle | None = None,
) -> GfDmaHealthResult:
    price = getattr(market, "latest_price", None)
    ma20 = getattr(market, "moving_average_20", None)
    ma50 = getattr(market, "moving_average_50", None)
    ma100 = getattr(market, "moving_average_100", None)
    ma200 = getattr(market, "moving_average_200", None)
    if all(value and value > 0 for value in (price, ma20, ma50, ma100, ma200)):
        revenue_growth = float(getattr(growth_evidence, "revenue_growth_trend", None) or 0.0)
        fcf_growth = float(getattr(growth_evidence, "free_cash_flow_trend", None) or 0.0)
        eps_growth = max(0.0, min(0.45, revenue_growth * 0.55))
        estimate_signal = _estimate_revision_signal(provider_bundle) if provider_bundle is not None else 0.0
        relative_strength = _relative_strength_proxy(float(price), float(ma50), float(ma200))
        valuation_expansion = _valuation_premium_proxy(valuation_multiples or {}) * 0.20
        return calculate_gf_dma_health(
            GfDmaHealthInput(
                revenue_growth=max(-0.40, min(0.60, revenue_growth)),
                eps_growth=eps_growth,
                fcf_growth=max(-0.40, min(0.60, fcf_growth)),
                estimate_revision_trend=estimate_signal,
                current_price=float(price),
                dma_20=float(ma20),
                dma_50=float(ma50),
                dma_100=float(ma100),
                dma_200=float(ma200),
                relative_strength_vs_sector=relative_strength,
                valuation_multiple_expansion=valuation_expansion,
            )
        )
    return GfDmaHealthResult(
        fundamental_growth_score=0.0,
        dma_trend_score=0.0,
        divergence_score=0.0,
        escape_ratio=0.0,
        estimate_revision_score=0.0,
        overall_gf_dma_health_score=0.0,
        interpretation="Not available from current sources",
        overextension_risk=False,
        explanation="GF-DMA health is unavailable because live market data and moving averages are unavailable. This module remains a trend-health tool and does not estimate intrinsic value.",
    )


def _relative_strength_proxy(price: float, dma_50: float, dma_200: float) -> float:
    if dma_50 <= 0 or dma_200 <= 0:
        return 0.0
    price_vs_50 = price / dma_50 - 1
    dma_slope = dma_50 / dma_200 - 1
    return max(-0.25, min(0.25, (price_vs_50 * 0.5) + (dma_slope * 0.5)))


def _live_sources(market: object, sec: object, ir: object, macro: tuple[object, ...], industry: tuple[object, ...], news: tuple[object, ...], anysearch: tuple[object, ...]) -> tuple[str, ...]:
    sources = [
        f"Market data: {getattr(market, 'source_name', 'Market data connector')} - {getattr(market, 'source_url', '') or 'Not available from current sources'} ({getattr(market, 'retrieved_at', '')})",
        f"Financial statements and filings: {getattr(sec, 'source_name', 'SEC EDGAR')} - {getattr(sec, 'source_url', '') or 'Not available from current sources'} ({getattr(sec, 'retrieved_at', '')})",
    ]
    ir_sources = getattr(ir, "sources", ())
    if ir_sources:
        sources.extend(
            f"Company IR: {source.title} - {source.url} ({source.source_type})"
            for source in ir_sources
        )
    else:
        sources.append(f"Company IR: official IR connector ({getattr(ir, 'retrieved_at', '')})")
    sources.extend(f"Macro: {item.name} from {item.source} ({item.date})" for item in macro)
    sources.extend(f"Industry: {item.indicator_name} from {item.source} ({item.date})" for item in industry)
    sources.extend(f"News/source discovery: {item.source_name} - {item.url or 'Not available from current sources'} ({item.retrieved_at})" for item in news + anysearch)
    return tuple(sources)


def _macro_indicator_summary(item: object) -> str:
    latest = getattr(item, "latest_value", None)
    previous = getattr(item, "previous_value", None)
    latest_text = latest if latest is not None else "Not available from current sources"
    previous_text = previous if previous is not None else "not available"
    historical = getattr(item, "historical_comparison", "Historical comparison unavailable")
    average = getattr(item, "historical_average", None)
    average_text = f"; recent average {average:.2f}" if isinstance(average, (float, int)) else ""
    return (
        f"{getattr(item, 'name', 'Macro indicator')}: {latest_text} "
        f"(previous {previous_text}; {historical}{average_text}; trend {getattr(item, 'trend_direction', 'unknown')}; "
        f"{getattr(item, 'date', 'Not available from current sources')}; {getattr(item, 'source', 'Not available from current sources')})"
    )


def _live_evidence_claims(ticker: str, market: object, sec: object) -> tuple[EvidenceClaim, ...]:
    return (
        EvidenceClaim(
            claim_type=ClaimType.FACT,
            text="Live market data is retrieved only from the configured structured market-data connector.",
            value=getattr(market, "price_timestamp", "Not available from current sources"),
            source=getattr(market, "source_name", "Structured market-data connector"),
            confidence="Medium" if getattr(market, "latest_price", None) is not None else "Low",
            is_mock=False,
        ),
        EvidenceClaim(
            claim_type=ClaimType.FACT,
            text="SEC filing and company facts data are retrieved only from SEC EDGAR when SEC configuration is available.",
            value=_latest_filing_date(sec),
            source=getattr(sec, "source_name", "SEC EDGAR"),
            confidence="Medium" if getattr(sec, "cik", "") else "Low",
            is_mock=False,
        ),
        EvidenceClaim(
            claim_type=ClaimType.INTERPRETATION,
            text=f"{ticker} live memo uses unavailable labels where source-backed metrics cannot be retrieved.",
            value="No silent mock fallback",
            source="Agent data validation layer",
            confidence="High",
            is_mock=False,
        ),
    )


def _latest_filing_date(sec: object) -> str:
    dates = [
        getattr(getattr(sec, "latest_10q", None), "filing_date", ""),
        getattr(getattr(sec, "latest_10k", None), "filing_date", ""),
        getattr(getattr(sec, "latest_8k", None), "filing_date", ""),
    ]
    return next((date for date in dates if date), "Not available from current sources")


def _latest_macro_date(macro: tuple[object, ...]) -> str:
    return next((item.date for item in macro if getattr(item, "date", "") != "Not available from current sources"), "Not available from current sources")


def build_mock_memo_snapshot(company: CompanyMockData) -> MemoSnapshot:
    """Build the structured snapshot saved after report generation."""

    scenarios = _mock_scenario_valuations(company)
    fair_value = probability_weighted_fair_value(scenarios)
    entry_zones = calculate_entry_zones(fair_value)
    archetype = archetype_for_company(company)
    bayesian_growth = _mock_bayesian_growth(company, archetype)
    tam_adjusted_peg = _mock_tam_adjusted_peg(company, bayesian_growth)
    gf_dma_health = _mock_gf_dma_health(company, fair_value, archetype)
    return _mock_snapshot_from_components(
        company,
        fair_value,
        entry_zones,
        bayesian_growth,
        tam_adjusted_peg,
        gf_dma_health,
    )


def _mock_snapshot_from_components(
    company: CompanyMockData,
    fair_value: float,
    entry_zones: EntryZones,
    bayesian_growth: BayesianGrowthResult,
    tam_adjusted_peg: TamAdjustedPegResult,
    gf_dma_health: GfDmaHealthResult,
) -> MemoSnapshot:
    base_case = next(
        scenario for scenario in company.scenarios if scenario.name.lower() == "base"
    )
    return MemoSnapshot(
        ticker=company.ticker,
        price=max(1.0, fair_value * 0.96),
        valuation_multiples=company.valuation_multiples,
        revenue_growth=base_case.revenue_cagr_pct / 100,
        margin_trend=max(0.0, (base_case.terminal_margin_pct - 35.0) / 1000),
        free_cash_flow_trend=max(0.0, (company.bayesian_growth.posterior_growth_pct / 100) / 4),
        bayesian_growth_probabilities={
            hypothesis.name: probability
            for hypothesis, probability in bayesian_growth.updated_probabilities.items()
        },
        tam_adjusted_peg_score=tam_adjusted_peg.tam_adjusted_peg,
        gf_dma_health_score=gf_dma_health.overall_gf_dma_health_score,
        catalysts=company.catalysts,
        risks=company.risks,
        entry_price_zone={
            "conservative_entry_max": entry_zones.conservative_entry_max,
            "reasonable_accumulation_min": entry_zones.reasonable_accumulation_min,
            "reasonable_accumulation_max": entry_zones.reasonable_accumulation_max,
            "expensive_wait_min": entry_zones.expensive_wait_min,
        },
    )


def _mock_evidence_claims(
    company: CompanyMockData,
    scenarios: tuple[ScenarioValuation, ...],
    fair_value: float,
    entry_zones: EntryZones,
    bayesian_growth: BayesianGrowthResult,
    tam_adjusted_peg: TamAdjustedPegResult,
    gf_dma_health: GfDmaHealthResult,
) -> tuple[EvidenceClaim, ...]:
    scenario_values = ", ".join(
        f"{scenario.name}={_money(scenario.fair_value_per_share)}"
        for scenario in scenarios
    )
    return (
        EvidenceClaim(
            claim_type=ClaimType.FACT,
            text="Company identity and ticker are mock fixture fields, not freshly verified facts.",
            value=f"{company.name} ({company.ticker})",
            source="Mock company fixture",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.ASSUMPTION,
            text="Scenario per-share values are placeholder model assumptions.",
            value=scenario_values,
            source="Mock company fixture",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.ASSUMPTION,
            text="Enterprise value is modeled as 105% of equity value using 100 mock shares.",
            value="EV = equity value * 1.05; shares = 100",
            source="Mock report builder",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.ESTIMATE,
            text="Probability-weighted fair value is calculated from mock bear/base/bull scenarios.",
            value=_money(fair_value),
            source="Mock scenario model",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.ESTIMATE,
            text="Entry zones are calculated from scenario-weighted fair value using mock discount bands.",
            value=(
                f"Conservative <= {_money(entry_zones.conservative_entry_max)}; "
                f"reasonable <= {_money(entry_zones.reasonable_accumulation_max)}"
            ),
            source="Mock scenario model",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.ESTIMATE,
            text="Bayesian intrinsic growth output is generated from mock model inputs.",
            value=_pct(bayesian_growth.intrinsic_growth_estimate),
            source="Mock Bayesian growth model",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.ESTIMATE,
            text="TAM-adjusted PEG output is generated from mock score inputs.",
            value=f"{tam_adjusted_peg.tam_adjusted_peg:.2f}x",
            source="Mock TAM-adjusted PEG model",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.ESTIMATE,
            text="GF-DMA score is generated from mock trend and revision inputs.",
            value=f"{gf_dma_health.overall_gf_dma_health_score:.1f}/100",
            source="Mock GF-DMA health model",
            confidence="Low",
            is_mock=True,
        ),
        EvidenceClaim(
            claim_type=ClaimType.INTERPRETATION,
            text="AI value-chain role, catalysts, risks, and monitoring items are prototype interpretations.",
            value="Mock qualitative output",
            source="Mock company fixture",
            confidence="Low",
            is_mock=True,
        ),
    )


def _mock_scenario_valuations(
    company: CompanyMockData,
) -> tuple[ScenarioValuation, ...]:
    scenarios: list[ScenarioValuation] = []
    shares_outstanding = 100.0
    for scenario in company.scenarios:
        equity_value = scenario.implied_value_per_share * shares_outstanding
        enterprise_value = equity_value * 1.05
        scenarios.append(
            ScenarioValuation(
                name=scenario.name,
                enterprise_value=enterprise_value,
                equity_value=equity_value,
                fair_value_per_share=scenario.implied_value_per_share,
                probability=scenario.probability,
            )
        )
    return tuple(scenarios)


def _mock_bayesian_growth(
    company: CompanyMockData,
    archetype: CompanyArchetypeProfile,
) -> BayesianGrowthResult:
    base_case = next(
        scenario for scenario in company.scenarios if scenario.name.lower() == "base"
    )
    posterior_growth = company.bayesian_growth.posterior_growth_pct / 100
    return estimate_intrinsic_growth(
        BayesianGrowthInput(
            revenue_growth=(base_case.revenue_cagr_pct / 100) * archetype.bayesian_revenue_weight,
            gross_margin_trend=max(0.0, (base_case.terminal_margin_pct - 35.0) / 1000)
            * archetype.bayesian_margin_weight,
            operating_margin_trend=max(0.0, (base_case.terminal_margin_pct - 30.0) / 1200)
            * archetype.bayesian_margin_weight,
            free_cash_flow_trend=max(0.0, posterior_growth / 4) * archetype.bayesian_fcf_weight,
            backlog_or_rpo_growth=min(0.50, posterior_growth * 1.4 * archetype.bayesian_backlog_weight),
            signed_customer_contracts=0,
            vague_partnerships=0,
            rumor_intensity=0.0,
            hyperscaler_capex_exposure=min(
                1.0,
                (company.gf_dma.demand_momentum / 10) * archetype.bayesian_hyperscaler_weight,
            ),
            estimate_revisions=0.0,
            ai_market_exposure=min(
                1.0,
                (company.gf_dma.ai_execution / 10) * archetype.bayesian_ai_exposure_weight,
            ),
            stock_price_performance=0.18,
            fundamental_performance=posterior_growth,
            market_implied_growth=posterior_growth + 0.03,
        )
    )


def _mock_tam_adjusted_peg(
    company: CompanyMockData,
    bayesian_growth: BayesianGrowthResult,
) -> TamAdjustedPegResult:
    expected_growth = max(0.01, bayesian_growth.intrinsic_growth_estimate)
    mock_pe = max(1.0, company.tam_adjusted_peg.conventional_peg * expected_growth * 100)
    return calculate_tam_adjusted_peg(
        TamAdjustedPegInput(
            pe_ratio=mock_pe,
            expected_eps_growth=expected_growth,
            tam_score=_score_from_percent(company.tam_adjusted_peg.penetration_pct, invert=True),
            business_quality_score=_score_from_ten_point(company.gf_dma.financial_quality),
            cyclicality_score=max(1, 6 - _score_from_ten_point(company.gf_dma.demand_momentum)),
            dilution_risk_score=3 if company.ticker == "NBIS" else 2,
            execution_risk_score=max(1, 6 - _score_from_ten_point(company.gf_dma.ai_execution)),
        )
    )


def _mock_gf_dma_health(
    company: CompanyMockData,
    fair_value: float,
    archetype: CompanyArchetypeProfile,
) -> GfDmaHealthResult:
    base_case = next(
        scenario for scenario in company.scenarios if scenario.name.lower() == "base"
    )
    current_price = max(1.0, fair_value * 0.96)
    return calculate_gf_dma_health(
        GfDmaHealthInput(
            revenue_growth=(base_case.revenue_cagr_pct / 100) * archetype.gf_dma_revenue_weight,
            eps_growth=(base_case.revenue_cagr_pct / 100 + 0.03) * archetype.gf_dma_eps_weight,
            fcf_growth=(base_case.revenue_cagr_pct / 100 + 0.01) * archetype.gf_dma_fcf_weight,
            estimate_revision_trend=(company.bayesian_growth.evidence_update_pct / 100)
            + archetype.gf_dma_revision_adjustment,
            current_price=current_price,
            dma_20=current_price * 0.98,
            dma_50=current_price * 0.95,
            dma_100=current_price * 0.91,
            dma_200=current_price * 0.86,
            relative_strength_vs_sector=((company.gf_dma.demand_momentum - 5) / 50)
            + archetype.gf_dma_relative_strength_adjustment,
            valuation_multiple_expansion=(
                max(0.0, company.tam_adjusted_peg.conventional_peg - 1.0) / 10
            )
            + archetype.gf_dma_valuation_expansion_penalty,
        )
    )


def _mock_ai_classification(company: CompanyMockData) -> str:
    classifications = {
        "NVDA": "AI accelerator platform and data-center infrastructure supplier",
        "AMD": "AI accelerator challenger and diversified compute supplier",
        "ASML": "Semiconductor capital equipment bottleneck supplier",
        "TSMC": "Advanced foundry and AI silicon manufacturing platform",
        "ARM": "Processor IP platform with edge and data-center AI optionality",
        "NBIS": "AI cloud infrastructure and compute services provider",
    }
    return classifications.get(company.ticker, "AI and technology value-chain participant")


def _score_from_ten_point(score: int) -> int:
    return max(1, min(5, round(score / 2)))


def _score_from_percent(value: float, invert: bool = False) -> int:
    score = 5 if value <= 5 else 4 if value <= 15 else 3 if value <= 30 else 2
    if invert:
        return score
    return max(1, min(5, 6 - score))
