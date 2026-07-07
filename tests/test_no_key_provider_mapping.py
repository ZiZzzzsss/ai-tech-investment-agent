"""Tests for free/no-key provider mapping."""

from __future__ import annotations

from types import ModuleType
from unittest.mock import patch
import sys
import unittest

import pandas as pd

from src.connectors.yahooquery_data import fetch_yahooquery_market_data
from src.connectors.yfinance_data import fetch_yfinance_financials, fetch_yfinance_market_data
from src.data.data_hub import build_company_research_dataset
from src.config import AppConfig


class NoKeyProviderMappingTests(unittest.TestCase):
    def test_yfinance_price_and_history_mapping(self) -> None:
        fake_module = ModuleType("yfinance")
        fake_module.Ticker = lambda ticker: _FakeYFinanceTicker()  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"yfinance": fake_module}):
            result = fetch_yfinance_market_data("NVDA", "2026-07-06T00:00:00Z")

        self.assertEqual(result.source_name, "yfinance")
        self.assertEqual(result.latest_price, 130.0)
        self.assertEqual(result.market_cap, 1_000_000.0)
        self.assertIsNotNone(result.moving_average_20)
        self.assertEqual(len(result.daily_historical_prices), 220)

    def test_yfinance_financials_mapping(self) -> None:
        fake_module = ModuleType("yfinance")
        fake_module.Ticker = lambda ticker: _FakeYFinanceTicker()  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"yfinance": fake_module}):
            result = fetch_yfinance_financials("NVDA")

        self.assertEqual(result["revenue"].value, 1000.0)
        self.assertEqual(result["gross_profit"].value, 700.0)
        self.assertEqual(result["free_cash_flow"].value, 250.0)
        self.assertEqual(result["shares_outstanding"].value, 100.0)

    def test_yahooquery_market_fallback_mapping(self) -> None:
        fake_module = ModuleType("yahooquery")
        fake_module.Ticker = lambda ticker: _FakeYahooQueryTicker()  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"yahooquery": fake_module}):
            result = fetch_yahooquery_market_data("NVDA", "2026-07-06T00:00:00Z")

        self.assertEqual(result.source_name, "yahooquery")
        self.assertEqual(result.latest_price, 140.0)
        self.assertEqual(result.market_cap, 2_000_000.0)
        self.assertIsNotNone(result.moving_average_20)

    def test_dataset_valuation_from_mixed_providers(self) -> None:
        config = AppConfig("", "", "", "", "", "", "", "agent@example.com")
        with patch("src.data.provider_router.fetch_sec_financials") as sec:
            with patch("src.data.provider_router.fetch_market_data") as market:
                with patch("src.data.provider_router.fetch_fundamentals_with_fallbacks") as fundamentals:
                    with patch("src.data.provider_router.fetch_macro_indicators", return_value=()):
                        with patch("src.data.provider_router.fetch_company_ir_sources") as ir:
                            with patch("src.data.provider_router.fetch_industry_signals", return_value=()):
                                with patch("src.data.provider_router.fetch_recent_news", return_value=()):
                                    with patch("src.data.provider_router.search_anysearch", return_value=()):
                                        with patch("src.data.provider_router.fetch_analyst_estimates", return_value=({}, "")):
                                            with patch("src.data.provider_router.fetch_earnings_calendar", return_value=({}, "")):
                                                sec.return_value = _FakeSec()
                                                market.return_value = _FakeMarket()
                                                fundamentals.return_value = (_fake_financial_metrics(), ())
                                                ir.return_value = _FakeIr()
                                                dataset = build_company_research_dataset("NVDA", config)

        self.assertEqual(dataset.market_data["latest_price"].value, 100.0)
        self.assertEqual(dataset.valuation["enterprise_value"].value, 950.0)
        self.assertEqual(dataset.valuation["ev_sales"].value, 0.95)
        self.assertEqual(dataset.valuation["ev_ebitda"].data_type, "unavailable")


class _FakeYFinanceTicker:
    fast_info = {"last_price": 130.0, "previous_close": 129.0, "market_cap": 1_000_000.0}
    info = {"sharesOutstanding": 100.0, "trailingEps": 2.5}

    def history(self, period: str, interval: str, auto_adjust: bool = False):
        dates = pd.date_range("2025-12-01", periods=220, freq="D")
        return pd.DataFrame(
            {
                "Open": [100.0 + i for i in range(220)],
                "High": [101.0 + i for i in range(220)],
                "Low": [99.0 + i for i in range(220)],
                "Close": [100.0 + i for i in range(220)],
                "Volume": [1_000_000 for _ in range(220)],
            },
            index=dates,
        )

    @property
    def financials(self):
        return pd.DataFrame({pd.Timestamp("2026-01-31"): [1000.0, 700.0, 400.0, 300.0, 200.0]}, index=["Total Revenue", "Gross Profit", "Operating Income", "EBITDA", "Net Income"])

    @property
    def balance_sheet(self):
        return pd.DataFrame({pd.Timestamp("2026-01-31"): [500.0, 50.0]}, index=["Cash And Cash Equivalents", "Total Debt"])

    @property
    def cashflow(self):
        return pd.DataFrame({pd.Timestamp("2026-01-31"): [300.0, -50.0]}, index=["Operating Cash Flow", "Capital Expenditure"])


class _FakeYahooQueryTicker:
    summary_detail = {"NVDA": {"previousClose": 139.0}}
    price = {"NVDA": {"regularMarketPrice": 140.0, "marketCap": 2_000_000.0}}

    def history(self, period: str, interval: str):
        dates = pd.date_range("2025-12-01", periods=220, freq="D")
        return pd.DataFrame(
            {
                "symbol": ["NVDA" for _ in range(220)],
                "open": [100.0 + i for i in range(220)],
                "high": [101.0 + i for i in range(220)],
                "low": [99.0 + i for i in range(220)],
                "close": [100.0 + i for i in range(220)],
                "volume": [1_000_000 for _ in range(220)],
            },
            index=dates,
        )


class _FakeMarket:
    latest_price = 100.0
    price_timestamp = "2026-07-01"
    previous_close = 99.0
    open = 98.0
    high = 101.0
    low = 97.0
    volume = 1000
    market_cap = 1000.0
    moving_average_20 = 95.0
    moving_average_50 = 90.0
    moving_average_100 = 85.0
    moving_average_200 = 80.0
    source_name = "yfinance"
    source_url = "https://pypi.org/project/yfinance/"
    retrieved_at = "2026-07-06"
    warning = ""


class _FakeSec:
    cik = "1045810"
    warning = ""
    retrieved_at = "2026-07-06"


class _FakeIr:
    sources = ()
    warning = ""
    retrieved_at = "2026-07-06"


def _fake_financial_metrics():
    from src.data.models import ProviderMetric

    def metric(value: float):
        return ProviderMetric(value, "SEC EDGAR", "https://data.sec.gov", "SEC", "2026-07-06", data_type="actual", confidence="high")

    return {
        "revenue": metric(1000.0),
        "net_income": metric(200.0),
        "cash_and_equivalents": metric(100.0),
        "total_debt": metric(50.0),
        "free_cash_flow": metric(150.0),
    }


if __name__ == "__main__":
    unittest.main()
