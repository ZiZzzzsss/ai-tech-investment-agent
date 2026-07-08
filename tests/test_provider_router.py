"""Tests for structured provider mappers and routing rules."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.config import AppConfig
from src.connectors.eodhd_data import parse_eodhd_fundamentals, parse_eodhd_historical_prices
from src.connectors.fmp_data import (
    parse_fmp_analyst_estimates,
    parse_fmp_financial_statements,
    parse_fmp_historical_prices,
    parse_fmp_key_metrics,
    parse_fmp_quote,
)
from src.connectors.market_data import fetch_market_data
from src.data.provider_router import _provider_statuses, collect_provider_data


class ProviderRouterTests(unittest.TestCase):
    def test_fmp_quote_mapping(self) -> None:
        result = parse_fmp_quote(
            [{"price": 100, "previousClose": 99, "open": 98, "dayHigh": 101, "dayLow": 97, "volume": 10, "marketCap": 1000}]
        )

        self.assertEqual(result["latest_price"].value, 100.0)
        self.assertEqual(result["market_cap"].provider, "FMP")

    def test_fmp_historical_prices_mapping(self) -> None:
        result = parse_fmp_historical_prices({"historical": [{"date": "2026-07-01", "close": 100, "volume": 1}]})

        self.assertEqual(result[0]["close"], 100.0)

    def test_fmp_financial_statement_mapping(self) -> None:
        result = parse_fmp_financial_statements(
            {"revenue": 1000, "operatingIncome": 200, "ebitda": 250, "netIncome": 150, "weightedAverageShsOutDil": 10, "epsdiluted": 15, "date": "2026"},
            {"cashAndCashEquivalents": 50, "totalDebt": 30},
            {"operatingCashFlow": 180, "capitalExpenditure": -40},
        )

        self.assertEqual(result["revenue"].value, 1000.0)
        self.assertEqual(result["free_cash_flow"].value, 140.0)

    def test_fmp_key_metrics_mapping(self) -> None:
        result = parse_fmp_key_metrics([{"enterpriseValueTTM": 1000, "evToSalesTTM": 10, "peRatioTTM": 30}])

        self.assertEqual(result["enterprise_value"].value, 1000.0)
        self.assertEqual(result["pe_ratio"].value, 30.0)

    def test_fmp_analyst_estimates_mapping(self) -> None:
        result = parse_fmp_analyst_estimates([{"date": "2027", "estimatedEpsAvg": 12.5}])

        self.assertEqual(result["estimated_eps_avg"].value, 12.5)
        self.assertEqual(result["estimated_eps_avg"].data_type, "estimated")

    def test_eodhd_fallback_mapping(self) -> None:
        prices = parse_eodhd_historical_prices([{"date": "2026-07-01", "adjusted_close": 100, "volume": 1}])
        fundamentals = parse_eodhd_fundamentals(
            {
                "Highlights": {"MarketCapitalization": 1000, "DilutedEpsTTM": 10},
                "Valuation": {"EnterpriseValue": 900},
                "SharesStats": {"SharesOutstanding": 100},
                "Financials": {
                    "Income_Statement": {"yearly": {"2025-12-31": {"totalRevenue": 500, "netIncome": 50}}},
                    "Balance_Sheet": {"yearly": {"2025-12-31": {"cash": 20, "shortLongTermDebtTotal": 10}}},
                    "Cash_Flow": {"yearly": {"2025-12-31": {"totalCashFromOperatingActivities": 70, "capitalExpenditures": -20}}},
                },
            }
        )

        self.assertEqual(prices[0]["close"], 100.0)
        self.assertEqual(fundamentals["enterprise_value"].value, 900.0)
        self.assertEqual(fundamentals["free_cash_flow"].value, 50.0)

    def test_provider_priority_uses_fmp_first(self) -> None:
        with patch("src.connectors.market_data.fetch_fmp_market_data") as fmp:
            fmp.return_value = SimpleNamespace(latest_price=1, warning="", source_name="Financial Modeling Prep")
            result = fetch_market_data("NVDA", fmp_api_key="fmp", eodhd_api_key="eodhd")

        self.assertEqual(result.source_name, "Financial Modeling Prep")

    def test_sec_preferred_over_fmp_when_both_available(self) -> None:
        sec = SimpleNamespace(
            cik="1",
            warning="",
            source_url="sec-url",
            retrieved_at="now",
            metrics={"revenue": {"value": 100, "period": "2026", "classification": "actual"}},
        )
        with patch("src.data.provider_router.fetch_sec_financials", return_value=sec):
            with patch("src.data.provider_router.fetch_fundamentals_with_fallbacks") as fundamentals:
                fundamentals.return_value = ({"revenue": SimpleNamespace(value=100, provider="SEC")}, ())
                with patch("src.data.provider_router.fetch_market_data") as market:
                    market.return_value = SimpleNamespace(source_name="Financial Modeling Prep", warning="", latest_price=1, retrieved_at="now")
                    with patch("src.data.provider_router.fetch_macro_indicators", return_value=()):
                        with patch("src.data.provider_router.fetch_company_ir_sources", return_value=SimpleNamespace(sources=(), warning="", retrieved_at="")):
                            with patch("src.data.provider_router.fetch_industry_signals", return_value=()):
                                with patch("src.data.provider_router.fetch_recent_news", return_value=()):
                                    with patch("src.data.provider_router.search_anysearch", return_value=()):
                                        with patch("src.data.provider_router.fetch_analyst_estimates", return_value=({}, "unavailable")):
                                            with patch("src.data.provider_router.fetch_earnings_calendar", return_value=({}, "unavailable")):
                                                bundle = collect_provider_data("NVDA", AppConfig("", "fmp", "", "", "", "", "", "sec"))

        self.assertEqual(bundle.financial_metrics["revenue"].provider, "SEC")

    def test_missing_fmp_key_is_optional_not_unavailable_failure(self) -> None:
        statuses = _provider_statuses(
            AppConfig("", "", "", "", "", "", "", "sec-user-agent"),
            SimpleNamespace(source_name="yfinance", retrieved_at="now"),
            SimpleNamespace(cik="1", warning="", retrieved_at="now"),
            {},
            (),
            SimpleNamespace(sources=("https://investor.nvidia.com",), warning="", retrieved_at="now"),
            (),
            (),
            use_source_cache=False,
        )

        fmp = next(item for item in statuses if item.provider == "FMP optional")
        self.assertEqual(fmp.configured, "optional")
        self.assertEqual(fmp.availability, "not configured")
        self.assertNotEqual(fmp.configured, "missing")
        self.assertNotEqual(fmp.availability, "unavailable")


if __name__ == "__main__":
    unittest.main()
