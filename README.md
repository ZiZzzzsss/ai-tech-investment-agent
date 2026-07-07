# AI Technology Investment Research Agent

## Overview

This is a local AI-assisted equity research agent for AI, semiconductor, cloud infrastructure, data center, and technology companies.

The project generates structured investment research memos using source-backed data, valuation models, risk tracking, calculation audits, and local HTML output. It is designed as a disciplined research assistant, not as a trading bot and not as financial advice.

The current implementation focuses on the engineering architecture behind a research agent:

- Source-specific data connectors and fallback logic.
- Financial metric normalization and fiscal-period handling.
- Valuation, scenario, growth, and trend-health models.
- Source quality, missing-data, and calculation-audit checks.
- Local-only Markdown and HTML report generation.
- Tests that protect valuation math, report schema, source handling, and privacy constraints.

## Why This Project Exists

AI and semiconductor stocks can be difficult to analyze because current valuation may look expensive while future growth depends on uncertain variables such as hyperscaler capex, product cycles, signed contracts, supply constraints, advanced packaging capacity, export controls, and estimate revisions.

This project was built to separate:

- Current fundamentals.
- Future growth optionality.
- Market-implied expectations.
- Confirmed evidence.
- Analyst assumptions.
- Narrative or FOMO-driven signals.

The goal is to make the research process more reproducible, transparent, and source-aware.

## What The Agent Produces

The agent produces a buy-side-style company memo in Markdown and/or static local HTML. A full memo includes:

1. **Executive dashboard**: high-level valuation, growth, risk, entry-zone, data-quality, and calculation-audit status.
2. **Data coverage and source status**: which connectors worked, which were unavailable, and why.
3. **Financial snapshot**: source-labeled financial figures and concise analytical context.
4. **Fiscal Period & TTM Basis**: period basis for financial inputs, TTM construction status, and alignment warnings.
5. **Valuation multiples**: EV/Sales, EV/EBITDA, P/E, P/FCF, P/S, margins, and growth metrics where available.
6. **Bear/base/bull scenario valuation**: scenario-weighted fair value rather than a single target price.
7. **Entry-price framework**: conservative, reasonable, and expensive/wait zones without direct buy/sell language.
8. **GF-DMA health view**: trend health and entry discipline based on fundamentals, moving averages, divergence, and estimate support.
9. **Bayesian intrinsic growth view**: probability-weighted growth-regime analysis using evidence quality.
10. **TAM-adjusted PEG view**: growth-stock valuation adjusted for runway, quality, moat, cyclicality, dilution, and execution risk.
11. **Risk & Opportunity Tracker**: macro, market, industry, regulatory, company-specific, valuation, and technical signals.
12. **Macro and industry tracker**: rates, inflation, volatility, semiconductor cycle, capex, export controls, and other relevant signals.
13. **Recent validated developments**: source-backed updates from official or high-quality sources.
14. **Pending signals**: items that require validation before affecting the thesis.
15. **Catalysts and risks**: positive and negative developments to monitor.
16. **What changed since last review**: comparison with the prior memo for the same ticker.
17. **What would change the view**: explicit thesis-change triggers.
18. **Data quality and confidence level**: missing fields, freshness, connector warnings, and confidence assessment.
19. **Sources and query log**: source list and AnySearch/source-cache query trail where available.

## Analytical Models

### Traditional Valuation

Traditional valuation is used to evaluate current fundamentals through EV/Sales, EV/EBITDA, P/E, P/FCF, P/S, margins, revenue growth, and free cash flow. These metrics are period-aware and prefer TTM financial denominators where appropriate.

### Scenario Valuation

High-growth AI companies should not be reduced to one target price. The agent uses bear, base, and bull cases, then calculates a probability-weighted fair value and a visible scenario range.

### Entry-Price Framework

The project avoids direct buy/sell recommendations. Instead, it presents entry zones derived from scenario valuation:

- Conservative entry zone.
- Reasonable accumulation zone.
- Expensive/wait zone.

These zones are research aids, not trading instructions.

### GF-DMA Health Index

GF-DMA is used for trend health and entry discipline. It evaluates the relationship between price trend, moving averages, fundamental growth, divergence, and estimate support.

It is not an intrinsic valuation model and should not be interpreted as a fair-value estimate.

### Bayesian Intrinsic Growth

The Bayesian growth module estimates a company's 3-5 year intrinsic growth regime. It separates confirmed evidence from weak evidence, rumors, and price-led FOMO.

Growth hypotheses range from contraction to platform expansion. Price momentum alone does not increase intrinsic growth probability; if price rises without fundamental support, FOMO risk increases instead.

### TAM-Adjusted PEG

The TAM-adjusted PEG module adapts growth-stock valuation for:

- TAM/SAM runway.
- Business quality.
- Pricing power.
- Gross-margin durability.
- Recurring or software revenue quality.
- Cyclicality.
- Customer concentration.
- Dilution risk.
- Execution risk.
- Competitive moat.

Qualitative scores are treated as model-scored assumptions, not direct API facts.

### Risk & Opportunity Tracker

The tracker monitors risk and opportunity signals across macro, market index, industry, company-specific, regulation, valuation, and technical categories. Each tracker item includes status, impact, importance, validation rule, suggested research response, source priority, confidence, and evidence summary.

Supported statuses include pending, validated, invalidated, monitoring, and escalated.

## Data Architecture

The project uses a disciplined source hierarchy. It does not randomly search the web for all data.

### Structured Market Data

Used for price, OHLCV, market cap, history, moving averages, and technical inputs:

- `yfinance`
- `yahooquery`
- Optional Financial Modeling Prep
- Optional EODHD, Polygon, Tiingo, or Alpha Vantage hooks where configured

### Financial Statements

Used for revenue, profit, cash flow, debt, cash, shares, and EPS:

- SEC EDGAR where `SEC_USER_AGENT` is configured
- `yfinance` / `yahooquery` fallback fields
- Optional FMP/EODHD structured fallback

SEC EDGAR is treated as the highest-confidence source for official financial statement verification.

### Macro Data

Used for rates, inflation, unemployment, and other macro indicators:

- FRED public CSV
- FRED API when `FRED_API_KEY` is configured

### News, Catalysts, And Source Discovery

Used for recent developments, official source discovery, regulatory updates, catalysts, and tracker evidence:

- AnySearch skill/source cache
- Company investor relations pages
- Official releases
- SEC filings and company disclosures

AnySearch is not used for price, OHLCV, market cap, financial statement figures, valuation multiples, EPS estimates, or macro time series.

### Official Qualitative Sources

Used for guidance, backlog, product updates, customer commitments, and management commentary:

- Company investor relations.
- Earnings releases.
- Investor presentations.
- SEC filings and 8-K exhibits.
- Earnings transcripts where legally available.

## Engineering Concerns Addressed

This project includes engineering controls for reliability, traceability, and privacy:

- Reliable data pipeline with source-specific connectors.
- Provider fallback logic with visible warnings.
- Primary-source preference and source hierarchy.
- Data freshness and source-status diagnostics.
- Fiscal period and TTM handling.
- Metric-level missing-data handling.
- Separation between direct API fields, calculated fields, filing-extracted evidence, search-discovered evidence, and model-scored assumptions.
- Formula registry for shared calculations.
- Calculation audit command with deterministic fixtures.
- Unit tests and fixture-based tests.
- No silent mock-data fallback in live mode.
- No automatic buy/sell/hold advice.
- Local-only private reports.
- `.gitignore` protection for API keys, generated reports, local caches, and raw outputs.

## Facts Vs Assumptions

The agent separates:

- **Source-backed facts**: directly supported by filings, market-data providers, macro datasets, company IR, or official releases.
- **Calculated metrics**: derived from visible inputs and shared formulas.
- **Extracted filing evidence**: qualitative or semi-structured evidence from filings and IR materials.
- **Search-discovered evidence**: AnySearch/source-cache results used for discovery and catalysts only.
- **Model-scored assumptions**: analyst-style scores for TAM, moat, pricing power, execution risk, and related qualitative factors.
- **Unavailable data**: missing fields that should not be invented or silently replaced.

This distinction matters because qualitative factors such as moat, pricing power, business quality, and TAM runway are not direct API fields.

## Local Privacy

The project is designed for local private use.

- Reports are generated locally.
- HTML output is local-only under `local_site/`.
- API keys are loaded from `.env`.
- `.env`, `local_site/`, `outputs/`, source caches, raw data, generated HTML, and private reports are ignored by Git.
- Generated memos and source-cache files should not be committed.
- The project does not use tracking scripts, analytics, CDN dependencies, or external fonts in local HTML output.

## How To Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Check data-source readiness:

```bash
python run_report.py --diagnose-data
```

Generate a live HTML memo:

```bash
python run_report.py --ticker NVDA --format html --live
```

Generate a mock HTML memo:

```bash
python run_report.py --ticker NVDA --format html --mock
```

Generate a live HTML memo using a saved AnySearch source cache:

```bash
python run_report.py --ticker NVDA --format html --live --use-source-cache
```

Generate Markdown:

```bash
python run_report.py --ticker NVDA --format markdown --live
```

Generate both Markdown and HTML:

```bash
python run_report.py --ticker NVDA --format both --live
```

Generate the local dashboard:

```bash
python run_dashboard.py --live
```

Preview local HTML output:

```bash
cd local_site
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

Tracked tickers currently include `NVDA`, `AMD`, `ASML`, `TSM`, `ARM`, `MU`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, `META`, `ORCL`, `PLTR`, and `NBIS`.

## Configuration

Use `.env.example` as the template for local credentials:

```text
FMP_API_KEY=
EODHD_API_KEY=
POLYGON_API_KEY=
TIINGO_API_KEY=
ALPHA_VANTAGE_API_KEY=
FRED_API_KEY=
ANYSEARCH_API_KEY=
SEC_USER_AGENT=
```

`SEC_USER_AGENT` is required for SEC EDGAR requests. A typical value should include an app name and a contact email, for example:

```text
SEC_USER_AGENT=AIInvestmentResearchAgent/0.1 your-email@example.com
```

Do not commit `.env`.

## Testing

Run the test suite:

```bash
python -m pytest
```

Run the calculation audit:

```bash
python run_report.py --audit-calculations
```

The tests cover:

- Valuation formulas.
- TTM calculations.
- Fiscal-period alignment.
- Provider fallback behavior.
- Missing-data handling.
- GF-DMA calculations.
- Bayesian growth logic.
- TAM-adjusted PEG logic.
- Risk tracker validation.
- Source-cache reading.
- Report schema and mandatory sections.
- No unsupported buy/sell language.
- No silent mock fallback in live mode.
- No external scripts or CSS in generated HTML.
- Private output folders in `.gitignore`.

## Repository Structure

```text
.
├── AGENTS.md
├── README.md
├── data_sources.yaml
├── watchlist.yaml
├── trackers/
│   └── risk_opportunity_tracker.yaml
├── prompts/
├── run_report.py
├── run_dashboard.py
├── src/
│   ├── connectors/
│   ├── data/
│   ├── reports/
│   ├── research/
│   ├── validation/
│   └── valuation/
└── tests/
```

Generated local files are intentionally excluded:

```text
local_site/
outputs/
reports/
*.html
```

## Current Limitations

- This is not financial advice.
- This is not an automated trading system.
- Some data providers may be delayed, unofficial, rate-limited, incomplete, or unavailable.
- Analyst estimates and estimate revisions may require paid structured providers.
- Qualitative scores require evidence and analyst judgment.
- AnySearch is for source discovery and catalysts, not structured financial numbers.
- SEC XBRL extraction is functional but not exhaustive.
- Multi-currency, corporate actions, and portfolio-level analytics are still early-stage.

## Future Roadmap

Planned improvements include:

- Stronger paid data provider integration.
- Better SEC XBRL extraction and tag mapping.
- Source conflict detection and reconciliation.
- Corporate-action handling.
- FX and portfolio currency handling.
- Portfolio-level risk dashboard.
- Expanded research journal and post-event outcome tracking.
- Alert and monitoring system.
- Richer catalyst and earnings calendar.
- Better multi-company dashboard and comparison views.
- More robust source-backed qualitative scoring.

## Disclaimer

This project is for research and education only. It does not provide investment advice, personalized financial advice, or trading recommendations.
