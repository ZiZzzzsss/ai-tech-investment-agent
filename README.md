# AI Technology Investment Agent

TODO: Add setup instructions, architecture notes, and example workflows.

This Python project will support source-backed investment research for AI, semiconductor, and technology companies. Planned outputs include research memos with valuation scenarios, AI growth optionality, entry-price ranges, macro and industry risks, catalysts, and monitoring indicators.

## Report Generator

Live data is the default. The agent uses configured source-specific connectors
and marks unavailable fields clearly when credentials or sources are missing.

Generate a live Markdown memo:

```bash
python run_report.py --ticker NVDA --format markdown --live
```

The report is written to:

```text
outputs/markdown/NVDA.md
```

Generate a live HTML memo:

```bash
python run_report.py --ticker NVDA --format html --live
```

The HTML memo is written to:

```text
local_site/company_memos/NVDA.html
```

Generate both formats:

```bash
python run_report.py --ticker NVDA --format both --live
```

Use mock fixtures only when explicitly requested:

```bash
python run_report.py --ticker NVDA --format html --mock
```

Generate the local dashboard:

```bash
python run_dashboard.py --live
```

The dashboard is written to:

```text
local_site/index.html
```

Preview locally:

```bash
cd local_site
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

Tracked live tickers include `NVDA`, `AMD`, `ASML`, `TSM`, `ARM`, `MU`, `AVGO`, `MSFT`, `GOOGL`, `AMZN`, `META`, `ORCL`, `PLTR`, and `NBIS`.

## Source Discipline

- Market data provider priority is yfinance, yahooquery, optional FMP, configured legacy providers, then unavailable.
- Financial data provider priority is SEC EDGAR, yfinance, yahooquery, optional FMP, then unavailable.
- SEC EDGAR remains the highest-confidence official filing verification source.
- yfinance is the primary free/no-key provider for latest available price, OHLCV, history, moving averages, market cap where available, and fallback financial fields.
- yahooquery is the backup free/no-key provider for market and fallback financial data.
- FMP is an optional premium upgrade for broader structured coverage. Missing `FMP_API_KEY` should not block live reports.
- Company guidance and product updates come from official company IR sources.
- Macro data comes from official macro sources such as FRED, BLS, BEA, central banks, and treasury data.
- Industry data comes from official or industry-recognized sources such as SIA, SEMI, WSTS, TSMC monthly revenue, company filings, and hyperscaler earnings releases.
- AnySearch is for source discovery, recent news, catalysts, and tracker updates.
- AnySearch must not be used for stock prices, financial statement figures, valuation multiples, EPS estimates, or macro time series.
- Missing live data is shown as `Not available from current sources`; it is not silently replaced with mock data.

Run data-source diagnostics:

```bash
python run_report.py --diagnose-data
```

Run the calculation audit:

```bash
python run_report.py --audit-calculations
```

The audit checks every registered valuation and research formula against deterministic fixtures in `tests/fixtures/calculation_cases.yaml` and writes:

```text
outputs/calculation_audit.md
```

## Fiscal Period And TTM Handling

Financial metrics are period-aware. The data layer normalizes each financial value with a fiscal-period basis: quarterly, annual, TTM, forward, or point-in-time.

Default valuation period rules:

- Market cap and enterprise value are point-in-time.
- EV/Sales uses TTM revenue.
- EV/EBITDA uses TTM EBITDA.
- P/E uses TTM net income.
- P/FCF uses TTM free cash flow.
- P/S uses TTM revenue.
- Margins use matching-period numerator and denominator values.

TTM is calculated as the sum of the last four comparable fiscal quarters. If fewer than four comparable quarters are available, the affected metric is marked unavailable instead of mixing annual and quarterly values. Capex is normalized as a positive cash outflow before FCF is calculated.

The HTML and Markdown memos include a `Fiscal Period & TTM Basis` section showing the source, period basis, periods used, and period-alignment warnings.

Recommended `.env` coverage order:

```text
SEC_USER_AGENT=      # official SEC verification
FRED_API_KEY=        # optional; FRED public CSV works first when reachable
ANYSEARCH_API_KEY=   # optional; Codex source cache can also be used
FMP_API_KEY=         # optional premium upgrade
```

Install free/no-key provider dependencies:

```bash
pip install -r requirements.txt
```

## Privacy

- Generated HTML reports are static local files under `local_site/`.
- The project does not use GitHub Pages or a `docs/` publishing folder.
- Reports are not uploaded anywhere by the agent.
- HTML uses local CSS and JavaScript only.
- No tracking scripts, analytics, CDN dependencies, or external fonts are used.
- API keys should be loaded from `.env` and never hardcoded.
- `.env`, `local_site/`, `outputs/`, and generated HTML files are ignored by git.

Run tests:

```bash
python -m pytest
```

## Planned Structure

- `watchlist.yaml`: TODO company and ticker watchlist configuration.
- `data_sources.yaml`: TODO source registry for filings, transcripts, market data, industry data, and macro data.
- `prompts/`: TODO prompt templates for research and valuation workflows.
- `src/connectors/`: TODO source connector stubs. No real APIs implemented yet.
- `src/valuation/`: TODO valuation model stubs.
- `src/research/`: TODO research orchestration stubs.
- `src/reports/`: TODO report generation stubs.
- `tests/`: TODO test scaffolding.
- `outputs/`: TODO generated memo and analysis outputs.
