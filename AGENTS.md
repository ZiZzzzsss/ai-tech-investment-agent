# Agent Instructions

## Project Mission

Codex should act as a disciplined investment research engineering assistant for this repository.

The project goal is to produce source-backed buy-side equity research memos for AI, semiconductor, and technology companies. Memos should cover business quality, valuation scenarios, AI growth optionality, entry-price ranges, macro and industry risks, downside cases, catalysts, and monitoring indicators.

This project is not a trading signal generator. It supports structured research, transparent assumptions, and reproducible valuation work.

## Core Research Discipline

Live data is the default operating mode.

Mock data may be used only for:

- Unit tests.
- Offline development.
- Explicit `--mock` mode.

Mock data must never be silently used in live reports. If live data is unavailable, show `Not available from current sources`, list the failed or missing connector, and do not invent replacement figures.

Always separate:

- Facts: directly supported by cited sources.
- Assumptions: explicit inputs chosen by the analyst.
- Estimates: calculations or forecasts derived from facts and assumptions.
- Interpretation: analytical judgment about what the evidence may imply.

Never blur these categories. If a number is not sourced or calculated from visible inputs, label it as an assumption or estimate.

Factual claims must be cited. Prefer precise citations to filings, releases, presentations, transcripts, or official datasets. Do not cite vague source names when a specific document, date, table, page, or section is available.

Never invent financial figures, market data, operating metrics, valuation multiples, growth rates, margins, share counts, WACC inputs, or macro data. If a figure is unavailable, say so and define what source is needed.

Every financial metric must include a source and date where available. Every factual claim must be source-backed. Missing data must be shown as unavailable, not estimated by the agent unless the report explicitly labels it as a model-generated assumption.

Never give automatic buy, sell, hold, or other investment advice. The final memo may describe valuation ranges, risk/reward, evidence quality, and decision-relevant tradeoffs, but it must not instruct the user to transact.

Always include downside scenarios, including company-specific, industry-cycle, valuation-multiple, macro, execution, competitive, and thesis-break risks.

## Data-Source Hierarchy

Prefer primary and official sources over secondary summaries.

Use this hierarchy when gathering or validating factual claims:

1. SEC filings and equivalents: 10-K, 10-Q, 8-K, S-1, proxy statements, annual reports, and foreign issuer filings.
2. Company investor relations: earnings releases, shareholder letters, investor presentations, segment disclosures, official press releases, and conference-call transcripts hosted or linked by the company.
3. Official macroeconomic and industry data: Federal Reserve, BEA, BLS, Census, Treasury, IMF, World Bank, OECD, WTO, industry associations, and regulator datasets.
4. Exchange, index, and market-data provider materials where licensing permits use.
5. Reputable third-party research, news, and expert commentary, used only as secondary context and clearly labeled as such.

When sources conflict, prefer the more primary, more recent, and more directly relevant source. Call out unresolved conflicts instead of silently choosing the convenient figure.

Do not use unsourced web snippets, forum posts, or model memory as factual evidence.

AnySearch is for source discovery, news, catalysts, recent developments, and Risk & Opportunity Tracker updates. It must not be used as financial truth for stock prices, financial statement figures, valuation multiples, EPS estimates, revenue guidance, confirmed backlog, signed contracts, or macroeconomic time series.

The installed AnySearch Codex skill is the approved discovery layer for this repository. Use it only for:

- Official source discovery.
- Recent news and company developments.
- Catalysts.
- Regulatory updates.
- Risk & Opportunity Tracker evidence updates.

Do not use AnySearch for:

- Price.
- OHLCV.
- Market cap.
- Financial statement figures.
- Valuation multiples.
- Macro time series.

Structured data must continue to come from the correct structured provider: FMP or another configured market-data provider for market data, SEC EDGAR and filings for financial statements, and FRED or other official macro providers for macro series.

Free/no-key sources should work first. Use this live-data hierarchy:

- Market data: yfinance, then yahooquery, then optional FMP if `FMP_API_KEY` exists, then unavailable.
- Financial statements: SEC EDGAR when `SEC_USER_AGENT` is configured, then yfinance, then yahooquery, then optional FMP if configured, then unavailable.
- Macro data: FRED public CSV first, then FRED API if `FRED_API_KEY` exists, then unavailable.
- News, catalysts, regulatory updates, and tracker evidence: AnySearch source cache, then company IR links, then yfinance/yahooquery news when available, then unavailable.

FMP is an optional premium provider. Missing `FMP_API_KEY` must not be presented as a blocking live-data error.

Project Python cannot call Codex skills directly as an in-process API. When AnySearch evidence is needed in a report, Codex should run the AnySearch skill during task execution, save normalized results to `outputs/source_cache/{TICKER}.json`, and the user should run `python run_report.py --ticker NVDA --format html --live --use-source-cache`. Reports may read that cache for discovery, catalysts, regulatory updates, and tracker evidence only.

AnySearch-derived results must use the standard `SearchResult` model and classify source type, confidence, status, and reason for classification. Primary and official sources override news. Rumors stay low-confidence and pending. AnySearch results must not change valuation assumptions unless the evidence is confirmed by primary or official sources and the changed assumption is explicitly labeled.

Structured provider priority:

- Market data: Financial Modeling Prep, EODHD, Polygon, Tiingo, Alpha Vantage, then unavailable.
- Financial data: SEC EDGAR, Financial Modeling Prep, EODHD, then unavailable.
- Analyst estimates: Financial Modeling Prep, EODHD where available, then unavailable.
- Earnings calendar: Financial Modeling Prep, EODHD, company IR, then unavailable.
- Macro data: FRED API, FRED public CSV fallback, then unavailable.
- News and catalysts: company IR / official releases, SEC 8-K, AnySearch, FMP news, reputable financial news.

SEC EDGAR is the highest-confidence official verification source. FMP may be used as a structured fallback when SEC fields are unavailable or hard to map, but the memo must label FMP financial data as structured provider data not yet verified against SEC EDGAR. If SEC and FMP conflict, show both values and prefer SEC for official financial statement numbers.

Yahoo and Stooq must not be used as normal live-data fallbacks. They may remain only as explicitly experimental helpers and must not be required for normal report coverage.

## Research Workflow

Use the following workflow for company research:

1. Define the research question, ticker/company scope, date of analysis, and investment horizon.
2. Gather primary source materials and record document names, dates, and URLs or file paths.
3. Extract facts into a structured evidence table before interpretation.
4. Identify key assumptions required for valuation and thesis analysis.
5. Build multiple valuation cases: bear, base, bull, and at least one explicit downside/stress case.
6. Use multiple valuation methods and reconcile the outputs.
7. Analyze AI growth optionality with Bayesian intrinsic growth valuation.
8. Analyze valuation versus growth and TAM using TAM-adjusted PEG.
9. Score monitoring indicators using GF-DMA health scoring.
10. Draft the final memo in buy-side equity research format.
11. Run valuation math and report-schema tests before treating the work as complete.

## Final Output Format

The final research artifact should use a buy-side equity research memo format.

Include these sections unless the user requests a narrower artifact:

- Executive summary.
- Company and ticker context.
- Research question and investment horizon.
- Key facts and source table.
- Thesis drivers.
- Financial and operating snapshot.
- Valuation summary.
- Scenario analysis: bear, base, bull, and downside/stress.
- Bayesian intrinsic growth valuation.
- TAM-adjusted PEG analysis.
- GF-DMA health scoring and monitoring indicators.
- Macro, industry, competitive, and company-specific risks.
- Catalysts and thesis-break triggers.
- Entry-price range framework.
- Open questions and evidence gaps.
- Appendix with assumptions, calculations, and citations.

## HTML Output Requirements

The agent should generate both Markdown and HTML reports when report generation is requested.

The HTML report should be static, readable, elegant, and suitable for local viewing. Default HTML memos are written under `docs/`; `--live` preview output may be written under `local_site/`.

Design style:

- Minimalist.
- Apple-inspired without using Apple branding.
- Clean typography.
- Large spacing.
- Rounded cards.
- Subtle shadows.
- Light background.
- Responsive mobile layout.
- Clear financial tables.
- Professional dashboard layout.

Do not use:

- Apple logos.
- Apple branding.
- Proprietary Apple assets.
- Excessive animations.
- Tracking scripts.
- Unsupported investment recommendations.
- CDN dependencies.
- External fonts, scripts, or assets.

The HTML report must be source-backed and must preserve the same analytical discipline as the Markdown memo. Facts, assumptions, estimates, and interpretation must remain clearly separated. Factual claims must be cited, and the report must not provide automatic buy, sell, or hold advice.

Generated HTML reports are static local artifacts. They must not be uploaded by the agent and must not include tracking scripts or analytics. API keys must be loaded from `.env` and must never be hardcoded.

Generated reports must remain local-only and private. `local_site/`, `outputs/`, `.env`, and generated HTML files must stay in `.gitignore`.

## Risk & Opportunity Tracker

The agent must include a Risk & Opportunity Tracker in each company memo.

The tracker should identify the key macro, market, industry, regulatory, company-specific, valuation, and technical signals that may affect the stock.

Each tracker item must include:

- Status.
- Impact.
- Importance.
- Validation rule.
- Suggested research response.
- Source or source priority.
- Confidence level.

The tracker must distinguish:

- Pending signals.
- Validated signals.
- Invalidated signals.
- Ongoing monitoring items.
- Escalated thesis-impacting items.

The tracker must not give direct buy/sell advice.

Suggested responses should be research-oriented, such as:

- Update valuation model.
- Review entry zone.
- Increase thesis confidence.
- Reduce thesis confidence.
- Wait for confirmation.
- Escalate risk review.
- Monitor next release.

## Valuation Modules

Valuation code and reports should support multiple methods, including:

- Discounted cash flow or owner-earnings valuation.
- Comparable-company multiples.
- Historical multiple ranges.
- Sum-of-the-parts when segments have materially different economics.
- Scenario-weighted valuation.
- Bayesian intrinsic growth valuation.
- TAM-adjusted PEG.
- GF-DMA health scoring.

Bayesian intrinsic growth valuation should explicitly define priors, evidence updates, posterior growth assumptions, uncertainty ranges, and sensitivity to base-rate assumptions.

TAM-adjusted PEG should explicitly define TAM, serviceable market, penetration assumptions, growth duration, margin durability, competitive intensity, and valuation multiple implications.

GF-DMA health scoring should be treated as a monitoring framework. Define the dimensions used in the score before applying it. Each score must include source-backed evidence, direction of change, confidence level, and thesis relevance.

## Coding Standards

Use Python for implementation.

Prefer small, testable modules with clear inputs and outputs. Keep research orchestration, data connectors, valuation math, and report generation separated by package boundaries:

- `src/connectors/`: source connectors and data-loading stubs.
- `src/research/`: research workflow orchestration and evidence normalization.
- `src/valuation/`: valuation math, scenarios, assumptions, and model outputs.
- `src/reports/`: memo schemas and report rendering.
- `prompts/`: prompt templates for research and valuation workflows.
- `tests/`: unit and schema tests.
- `outputs/`: generated artifacts only.

Do not implement real API calls until credentials, source permissions, rate limits, and caching rules are defined. Connector code should start as interfaces, fixtures, or local-file loaders.

Use typed dataclasses or Pydantic-style schemas for core research and report objects when practical. Avoid loose dictionaries for valuation outputs once the schema stabilizes.

Keep calculations deterministic and reproducible. Valuation functions should avoid hidden global state, network calls, and time-dependent behavior unless explicitly injected.

## Testing Requirements

Include tests for valuation math and report schema.

At minimum, tests should cover:

- Scenario valuation calculations.
- Weighted valuation calculations.
- Growth, margin, multiple, and discount-rate sensitivity math.
- Bayesian intrinsic growth posterior calculations.
- TAM-adjusted PEG calculations.
- GF-DMA scoring aggregation.
- Report schema validation for required memo sections.
- Citation presence for factual claims in generated report structures.

Use small deterministic fixtures. Tests should not require live API access.

## Calculation Audit Requirements

Every valuation and research calculation must be registered in `src/validation/formula_registry.py` with a formula name, purpose, inputs, output meaning, units, and common error checks.

## Calculation Safety Rules

All financial and model calculations must live in shared calculation functions, not inside report templates.

Every formula must have:

- A named function.
- A formula definition in `formula_registry.py`.
- Fixture-based tests with known expected outputs.
- Unit and scale checks.
- Missing-data behavior.

Before finalizing any change that affects calculations, run:

```bash
python -m pytest
python run_report.py --audit-calculations
```

Do not display a metric in the report if its calculation failed audit.

Before changing or adding any model calculation, Codex must:

- Update `src/validation/formula_registry.py`.
- Add or update deterministic cases in `tests/fixtures/calculation_cases.yaml`.
- Add or update unit tests for the changed formula.
- Run `python run_report.py --audit-calculations`.
- Run `python -m pytest`.
- Confirm that all calculation tests pass.

Report code must not silently redefine financial formulas. If a report needs a calculated value, it should use a shared valuation/research module or the formula registry. If a formula cannot be audited, mark the output low-confidence or unavailable rather than presenting it as validated.

## Fiscal Period And TTM Rules

All valuation calculations must be period-aware.

Codex must not mix quarterly, annual, TTM, point-in-time, and forward values without explicit labeling and validation. Market cap and enterprise value are point-in-time. EV/Sales, EV/EBITDA, P/E, P/FCF, and P/S should use TTM financial denominators by default. Margins must use matching-period numerator and denominator values.

Before changing valuation formulas, Codex must:

- Update period validation if needed.
- Update TTM tests.
- Run `python -m pytest`.
- Run `python run_report.py --audit-calculations`.

If period alignment fails, mark only the affected metric unavailable and show the exact reason. Do not annualize quarterly net income, revenue, EBITDA, or free cash flow for valuation multiples unless the report explicitly labels the shortcut and validates the period basis.

## Forbidden Behavior

Codex must not:

- Invent or hallucinate financial figures.
- Present estimates as facts.
- Omit citations for factual claims.
- Give automatic buy, sell, or hold advice.
- Produce only upside cases.
- Hide downside scenarios or thesis-break risks.
- Use unsupported model memory as evidence.
- Mix real API implementation into placeholder connector work without explicit user direction.
- Store credentials, API keys, tokens, or paid data in the repository.
- Overwrite user work or unrelated files while making scoped changes.

## Definition Of Done

A task is complete when:

- The requested files or code changes are present.
- Facts, assumptions, estimates, and interpretation are clearly separated where research content is involved.
- Primary-source preference is followed or source limitations are disclosed.
- Valuation work uses multiple methods where applicable.
- Downside scenarios are included.
- Bayesian intrinsic growth valuation, TAM-adjusted PEG, and GF-DMA health scoring are included when producing full research memos.
- Factual claims have citations.
- No automatic buy/sell advice is given.
- Valuation math and report-schema tests are added or updated for new valuation/report behavior.
- Relevant tests have been run, or any inability to run them is clearly reported.
