"""Source registry helpers and provider priority constants."""

from __future__ import annotations

from src.config import load_official_ir_urls


MARKET_DATA_PROVIDER_PRIORITY = (
    "FMP",
    "EODHD",
    "Polygon",
    "Tiingo",
    "Alpha Vantage",
)

FINANCIAL_DATA_PROVIDER_PRIORITY = (
    "SEC EDGAR",
    "FMP",
    "EODHD",
)

MACRO_PROVIDER_PRIORITY = (
    "FRED API",
    "FRED public CSV",
)


__all__ = [
    "FINANCIAL_DATA_PROVIDER_PRIORITY",
    "MACRO_PROVIDER_PRIORITY",
    "MARKET_DATA_PROVIDER_PRIORITY",
    "load_official_ir_urls",
]
