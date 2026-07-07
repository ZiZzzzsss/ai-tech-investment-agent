"""Analyst estimate connector router."""

from __future__ import annotations

from src.connectors.fmp_data import fetch_fmp_market_bundle
from src.data.models import ProviderMetric


def fetch_analyst_estimates(
    ticker: str,
    fmp_api_key: str = "",
    eodhd_api_key: str = "",
) -> tuple[dict[str, ProviderMetric], str]:
    """Fetch analyst estimates by provider priority: FMP, EODHD, unavailable."""

    if fmp_api_key:
        bundle = fetch_fmp_market_bundle(ticker, fmp_api_key)
        estimates = bundle.get("analyst_estimates", {})
        if isinstance(estimates, dict) and any(metric.value is not None for metric in estimates.values()):
            return estimates, "FMP"
    if eodhd_api_key:
        return {}, "Unavailable: EODHD analyst estimate mapping is not implemented yet."
    return {}, ""
