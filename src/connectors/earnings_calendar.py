"""Earnings-calendar connector router."""

from __future__ import annotations

from src.connectors.company_ir import CompanyIrResult
from src.connectors.fmp_data import fetch_fmp_market_bundle
from src.data.models import ProviderMetric


def fetch_earnings_calendar(
    ticker: str,
    fmp_api_key: str = "",
    eodhd_api_key: str = "",
    company_ir: CompanyIrResult | None = None,
) -> tuple[dict[str, ProviderMetric], str]:
    """Fetch earnings calendar by provider priority: FMP, EODHD, company IR, unavailable."""

    if fmp_api_key:
        bundle = fetch_fmp_market_bundle(ticker, fmp_api_key)
        earnings = bundle.get("earnings_calendar", {})
        if isinstance(earnings, dict) and any(metric.value for metric in earnings.values()):
            return earnings, "FMP"
    if eodhd_api_key:
        return {}, "Unavailable: EODHD earnings-calendar mapping is not implemented yet."
    if company_ir and company_ir.sources:
        return {}, "Unavailable: company IR source configured, but earnings-date extraction is not implemented yet."
    return {}, "Unavailable: FMP_API_KEY and EODHD_API_KEY missing, and company IR earnings extraction is not implemented."
