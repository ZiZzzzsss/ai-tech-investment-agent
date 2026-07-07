"""Provider router for live source-backed research data."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import AppConfig, load_official_ir_urls
from src.connectors.anysearch_skill import SearchResult, load_source_cache, search_anysearch
from src.connectors.company_ir import CompanyIrResult, fetch_company_ir_sources
from src.connectors.earnings_calendar import fetch_earnings_calendar
from src.connectors.estimates_data import fetch_analyst_estimates
from src.connectors.fundamentals_data import fetch_fundamentals_with_fallbacks
from src.connectors.industry_data import IndustrySignal, fetch_industry_signals
from src.connectors.macro_data import MacroIndicator, fetch_macro_indicators
from src.connectors.market_data import MarketDataResult, fetch_market_data
from src.connectors.news_data import fetch_recent_news
from src.connectors.sec_edgar import SecFinancialsResult, fetch_sec_financials
from src.connectors.yahooquery_data import is_yahooquery_installed
from src.connectors.yfinance_data import is_yfinance_installed
from src.data.models import ProviderMetric
from src.data.provider_status import ProviderStatus


@dataclass(frozen=True)
class ProviderDataBundle:
    market: MarketDataResult
    sec: SecFinancialsResult
    financial_metrics: dict[str, ProviderMetric]
    estimates: dict[str, ProviderMetric]
    earnings_calendar: dict[str, ProviderMetric]
    macro: tuple[MacroIndicator, ...]
    ir: CompanyIrResult
    industry: tuple[IndustrySignal, ...]
    news: tuple[SearchResult, ...]
    anysearch: tuple[SearchResult, ...]
    statuses: tuple[ProviderStatus, ...]
    warnings: tuple[str, ...]


def collect_provider_data(
    ticker: str,
    config: AppConfig,
    use_source_cache: bool = False,
) -> ProviderDataBundle:
    """Collect live data using the project provider hierarchy."""

    market = fetch_market_data(
        ticker,
        alpha_vantage_api_key=config.alpha_vantage_api_key,
        fmp_api_key=config.fmp_api_key,
        eodhd_api_key=config.eodhd_api_key,
        polygon_api_key=config.polygon_api_key,
        tiingo_api_key=config.tiingo_api_key,
    )
    sec = fetch_sec_financials(ticker, config.sec_user_agent)
    financial_metrics, financial_warnings = fetch_fundamentals_with_fallbacks(
        ticker,
        sec,
        config.fmp_api_key,
        config.eodhd_api_key,
    )
    macro = fetch_macro_indicators(config.fred_api_key)
    ir = fetch_company_ir_sources(ticker, load_official_ir_urls(ticker))
    industry = fetch_industry_signals(ticker)
    source_cache_results = load_source_cache(ticker) if use_source_cache else ()
    news = tuple(
        result
        for result in source_cache_results
        if result.category in {"recent_news", "catalyst", "catalysts", "regulation", "regulatory_update"}
    )
    if not news and not use_source_cache:
        news = fetch_recent_news(ticker, config.anysearch_api_key)
    anysearch = source_cache_results
    if not anysearch and not use_source_cache:
        anysearch = search_anysearch(
            f"{ticker.upper()} official investor relations latest earnings release",
            config.anysearch_api_key,
            ticker=ticker,
            category="official_source_discovery",
        )
    estimates, estimates_status = fetch_analyst_estimates(ticker, config.fmp_api_key, config.eodhd_api_key)
    earnings, earnings_status = fetch_earnings_calendar(ticker, config.fmp_api_key, config.eodhd_api_key, ir)
    warnings = tuple(
        warning
        for warning in (
            market.warning,
            sec.warning,
            *financial_warnings,
            estimates_status if estimates_status != "FMP" else "",
            earnings_status if earnings_status != "FMP" else "",
            *(indicator.warning for indicator in macro if indicator.warning),
        )
        if warning
    )
    return ProviderDataBundle(
        market=market,
        sec=sec,
        financial_metrics=financial_metrics,
        estimates=estimates,
        earnings_calendar=earnings,
        macro=macro,
        ir=ir,
        industry=industry,
        news=news,
        anysearch=anysearch,
        statuses=_provider_statuses(
            config,
            market,
            sec,
            financial_metrics,
            macro,
            ir,
            industry,
            anysearch,
            use_source_cache,
        ),
        warnings=warnings,
    )


def _provider_statuses(
    config: AppConfig,
    market: MarketDataResult,
    sec: SecFinancialsResult,
    financial_metrics: dict[str, ProviderMetric],
    macro: tuple[MacroIndicator, ...],
    ir: CompanyIrResult,
    industry: tuple[IndustrySignal, ...],
    anysearch: tuple[SearchResult, ...],
    use_source_cache: bool = False,
) -> tuple[ProviderStatus, ...]:
    used_financial_providers = {metric.provider for metric in financial_metrics.values()}
    macro_available = [item for item in macro if item.latest_value is not None]
    anysearch_available = [item for item in anysearch if item.url]
    return (
        _status("yfinance", is_yfinance_installed(), market.source_name == "yfinance" or "yfinance" in used_financial_providers, market.source_name == "yfinance" or "yfinance" in used_financial_providers, "Primary free/no-key provider for price, OHLCV, history, moving averages, and financial fallbacks.", market.retrieved_at if market.source_name == "yfinance" else ""),
        _status("yahooquery", is_yahooquery_installed(), market.source_name == "yahooquery" or "yahooquery" in used_financial_providers, market.source_name == "yahooquery" or "yahooquery" in used_financial_providers, "Backup free/no-key provider for market data, financial fallbacks, and news where available.", market.retrieved_at if market.source_name == "yahooquery" else ""),
        _status("FMP optional", bool(config.fmp_api_key), market.source_name == "Financial Modeling Prep" or "FMP" in used_financial_providers, bool(config.fmp_api_key) and (market.source_name == "Financial Modeling Prep" or "FMP" in used_financial_providers), "Optional premium provider; an absent FMP key is not a blocker.", market.retrieved_at if market.source_name == "Financial Modeling Prep" else ""),
        _status("SEC EDGAR", bool(config.sec_user_agent), bool(sec.cik), bool(sec.cik), sec.warning or "Official filing verification source.", sec.retrieved_at if sec.cik else ""),
        _status("FRED", bool(config.fred_api_key), bool(macro_available), bool(macro_available), "FRED API or public CSV fallback for macro indicators.", macro_available[0].date if macro_available else ""),
        _status(
            "AnySearch Skill / source cache",
            bool(config.anysearch_api_key) or use_source_cache,
            bool(anysearch_available),
            bool(anysearch_available),
            "Codex AnySearch skill source-cache for discovery, recent news, catalysts, regulatory updates, and tracker evidence only.",
            anysearch_available[0].retrieved_at if anysearch_available else "",
        ),
        _status("Company IR", bool(ir.sources), bool(ir.sources), bool(ir.sources), f"{len(ir.sources)} official IR source(s) configured." if ir.sources else ir.warning, ir.retrieved_at if ir.sources else ""),
        ProviderStatus("Mock data", "no", "no", "available", "Live mode does not silently use mock fixtures.", ""),
    )


def _status(provider: str, configured: bool, used: bool, available: bool, reason: str, retrieved_at: str) -> ProviderStatus:
    return ProviderStatus(
        provider=provider,
        configured="configured" if configured else "missing",
        used="used" if used else "not used",
        availability="available" if available else "unavailable",
        reason=reason if configured or available else f"Missing credential or implementation. {reason}",
        last_successful_retrieval=retrieved_at or "none",
    )
