"""Markdown report renderer for mock company memos.

TODO: Add report schemas and richer rendering once real data connectors and
validated valuation modules are implemented.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.connectors.mock_data import CompanyMockData
from src.valuation import gf_dma_average_score, scenario_weighted_value


REQUIRED_SECTIONS = (
    "Executive Dashboard",
    "Business And AI Exposure",
    "Financial Snapshot",
    "Valuation Multiples",
    "Bear/Base/Bull Scenario Table",
    "Bayesian Intrinsic Growth View",
    "TAM-Adjusted PEG View",
    "GF-DMA Health View",
    "Entry-Price Framework",
    "Macro And Industry Tracker",
    "Catalysts",
    "Risks",
    "Data Quality Warning",
    "Source Placeholder Section",
)


def _bullet_list(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _dict_table(values: dict[str, str]) -> str:
    rows = ["| Metric | Mock value |", "| --- | --- |"]
    rows.extend(f"| {key} | {value} |" for key, value in values.items())
    return "\n".join(rows)


def _scenario_table(company: CompanyMockData) -> str:
    rows = [
        "| Case | Revenue CAGR | Terminal margin | Exit multiple | Implied value/share | Probability | Note |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for scenario in company.scenarios:
        rows.append(
            "| "
            f"{scenario.name} | "
            f"{scenario.revenue_cagr_pct:.1f}% | "
            f"{scenario.terminal_margin_pct:.1f}% | "
            f"{scenario.exit_multiple:.1f}x | "
            f"${scenario.implied_value_per_share:,.2f} | "
            f"{scenario.probability:.0%} | "
            f"{scenario.note} |"
        )
    rows.append(
        "| Scenario-weighted | - | - | - | "
        f"${scenario_weighted_value(company.scenarios):,.2f} | 100% | Mock probability-weighted output. |"
    )
    return "\n".join(rows)


def render_company_memo(company: CompanyMockData) -> str:
    """Render a mock buy-side style company memo."""

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    bayesian = company.bayesian_growth
    tam = company.tam_adjusted_peg
    gf_dma = company.gf_dma
    gf_dma_average = gf_dma_average_score(gf_dma)

    return f"""# {company.name} ({company.ticker}) Mock Investment Research Memo

Generated: {generated_at}

> This report uses mock data only. It is a prototype output for workflow testing, not investment advice, not a recommendation, and not a source-backed factual research memo.

## Executive Dashboard

| Item | Mock view |
| --- | --- |
| Company | {company.name} |
| Ticker | {company.ticker} |
| Scenario-weighted value | ${scenario_weighted_value(company.scenarios):,.2f} |
| Bayesian posterior growth | {bayesian.posterior_growth_pct:.1f}% |
| TAM-adjusted PEG | {tam.tam_adjusted_peg:.2f}x |
| GF-DMA score | {gf_dma_average:.1f}/10 |
| GF-DMA trend | {gf_dma.trend} |

## Business And AI Exposure

**Business:** {company.business_summary}

**AI exposure:** {company.ai_exposure}

## Financial Snapshot

{_dict_table(company.financial_snapshot)}

## Valuation Multiples

{_dict_table(company.valuation_multiples)}

## Bear/Base/Bull Scenario Table

{_scenario_table(company)}

## Bayesian Intrinsic Growth View

| Input | Mock value |
| --- | ---: |
| Prior growth | {bayesian.prior_growth_pct:.1f}% |
| Evidence update | {bayesian.evidence_update_pct:+.1f}% |
| Posterior growth | {bayesian.posterior_growth_pct:.1f}% |
| Confidence | {bayesian.confidence} |

Interpretation: {bayesian.interpretation}

## TAM-Adjusted PEG View

| Input | Mock value |
| --- | ---: |
| Serviceable TAM | ${tam.serviceable_tam_usd_b:,.1f}B |
| Assumed penetration | {tam.penetration_pct:.1f}% |
| Growth duration | {tam.growth_duration_years} years |
| Conventional PEG | {tam.conventional_peg:.2f}x |
| TAM-adjusted PEG | {tam.tam_adjusted_peg:.2f}x |

Interpretation: {tam.interpretation}

## GF-DMA Health View

GF-DMA definition for this mock prototype: Growth, Financial quality, Demand momentum, Moat durability, and AI execution.

| Dimension | Mock score |
| --- | ---: |
| Growth | {gf_dma.growth}/10 |
| Financial quality | {gf_dma.financial_quality}/10 |
| Demand momentum | {gf_dma.demand_momentum}/10 |
| Moat durability | {gf_dma.moat_durability}/10 |
| AI execution | {gf_dma.ai_execution}/10 |
| Average | {gf_dma_average:.1f}/10 |
| Trend | {gf_dma.trend} |
| Confidence | {gf_dma.confidence} |

## Entry-Price Framework

{_dict_table(company.entry_price_framework)}

## Macro And Industry Tracker

{_bullet_list(company.macro_industry_tracker)}

## Catalysts

{_bullet_list(company.catalysts)}

## Risks

{_bullet_list(company.risks)}

## Data Quality Warning

All company data, valuation outputs, multiples, scenario values, probabilities, scores, and qualitative statements in this memo are mock placeholders. They should not be used for investment decisions. Real reports must replace these placeholders with cited primary sources, validated calculations, and explicit assumptions.

## Source Placeholder Section

TODO: Add source-backed citations from SEC filings, company investor relations, earnings releases, investor presentations, conference-call transcripts, official macroeconomic data, and licensed market data.

Current source status:

- Facts: no real factual claims validated.
- Assumptions: mock assumptions only.
- Estimates: mock calculations only.
- Interpretation: prototype interpretation only.
"""
