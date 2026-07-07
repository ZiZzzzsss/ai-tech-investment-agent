"""Tests for live connector parsing with mocked API responses."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.config import AppConfig, load_official_ir_urls, render_data_diagnostics
from src.connectors.anysearch_skill import classify_source, normalize_search_result, search_anysearch
from src.connectors.macro_data import fetch_macro_indicators
from src.connectors.market_data import fetch_market_data, fetch_stooq_daily_market_data, fetch_yahoo_chart_market_data
from src.connectors.sec_edgar import fetch_sec_financials
from src.data import ValidatedMetric, validate_metrics


class LiveConnectorTests(unittest.TestCase):
    def test_market_data_connector_parses_mocked_alpha_vantage_response(self) -> None:
        payload = {
            "Time Series (Daily)": {
                f"2026-07-{day:02d}": {
                    "1. open": "100",
                    "2. high": "110",
                    "3. low": "95",
                    "4. close": str(100 + day),
                    "6. volume": "1000000",
                }
                for day in range(1, 31)
            }
        }
        with patch("src.connectors.market_data._get_json", return_value=payload):
            result = fetch_market_data("NVDA", "key")

        self.assertEqual(result.ticker, "NVDA")
        self.assertIsNotNone(result.latest_price)
        self.assertIsNotNone(result.moving_average_20)
        self.assertEqual(result.source_name, "Alpha Vantage")
        self.assertEqual(result.latest_available_label, "latest available close")

    def test_market_data_connector_parses_mocked_fmp_response_first(self) -> None:
        history_payload = {
            "historical": [
                {
                    "date": f"2026-07-{day:02d}",
                    "open": 100,
                    "high": 110,
                    "low": 95,
                    "close": 100 + day,
                    "volume": 1000000,
                }
                for day in range(30, 0, -1)
            ]
        }
        quote_payload = [{"price": 130, "marketCap": 1000}]
        with patch("src.connectors.market_data._get_json", side_effect=[quote_payload, history_payload]):
            result = fetch_market_data("NVDA", alpha_vantage_api_key="alpha", fmp_api_key="fmp")

        self.assertEqual(result.source_name, "Financial Modeling Prep")
        self.assertEqual(result.latest_price, 130)
        self.assertEqual(result.market_cap, 1000)
        self.assertIsNotNone(result.moving_average_20)

    def test_market_data_connector_requires_configured_provider_without_api_key(self) -> None:
        with patch("src.connectors.market_data.fetch_stooq_daily_market_data") as stooq:
            with patch("src.connectors.market_data.fetch_yahoo_chart_market_data") as yahoo:
                result = fetch_market_data("NVDA", "")

        self.assertIsNone(result.latest_price)
        self.assertIn("Unavailable: yfinance", result.warning)
        self.assertIn("Unavailable: yahooquery", result.warning)
        self.assertNotIn("FMP_API_KEY missing", result.warning)
        stooq.assert_not_called()
        yahoo.assert_not_called()

    def test_market_data_connector_uses_yahoo_fallback_when_stooq_fails(self) -> None:
        timestamps = [1780272000 + (day * 86400) for day in range(30)]
        closes = [100 + day for day in range(30)]
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": timestamps,
                        "meta": {"regularMarketPrice": 130, "marketCap": 1000},
                        "indicators": {
                            "quote": [
                                {
                                    "open": closes,
                                    "high": [value + 1 for value in closes],
                                    "low": [value - 1 for value in closes],
                                    "close": closes,
                                    "volume": [1000000 for _ in closes],
                                }
                            ]
                        },
                    }
                ]
            }
        }
        with patch("src.connectors.market_data._get_json", return_value=payload):
            result = fetch_yahoo_chart_market_data("NVDA")

        self.assertEqual(result.source_name, "Yahoo Finance chart API")
        self.assertEqual(result.latest_price, 130)
        self.assertIsNotNone(result.moving_average_20)
        self.assertEqual(result.market_cap, 1000)

    def test_stooq_404_handling_returns_specific_warning(self) -> None:
        with patch("src.connectors.market_data._get_text", side_effect=OSError("HTTP Error 404: Not Found")):
            result = fetch_stooq_daily_market_data("NVDA")

        self.assertIsNone(result.latest_price)
        self.assertIn("Unavailable: Stooq unsupported ticker", result.warning)
        self.assertIn("404", result.warning)

    def test_yahoo_429_handling_returns_rate_limit_warning(self) -> None:
        with patch("src.connectors.market_data._get_json", side_effect=OSError("HTTP Error 429: Too Many Requests")):
            result = fetch_yahoo_chart_market_data("NVDA")

        self.assertIsNone(result.latest_price)
        self.assertIn("Unavailable: Yahoo fallback returned rate limit", result.warning)

    def test_sec_connector_requires_user_agent(self) -> None:
        result = fetch_sec_financials("NVDA", "")

        self.assertEqual(result.metrics, {})
        self.assertIn("SEC financial data unavailable because SEC_USER_AGENT is not configured", result.warning)

    def test_sec_connector_parses_mocked_submissions_and_facts(self) -> None:
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K", "10-K"],
                    "filingDate": ["2026-05-01", "2026-04-01", "2026-02-01"],
                    "accessionNumber": ["a1", "a2", "a3"],
                    "reportDate": ["2026-03-31", "2026-04-01", "2025-12-31"],
                }
            }
        }
        facts = {
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [{"val": 1000, "end": "2026-03-31", "filed": "2026-05-01"}]}},
                    "NetIncomeLoss": {"units": {"USD": [{"val": 200, "end": "2026-03-31", "filed": "2026-05-01"}]}},
                }
            }
        }
        with patch("src.connectors.sec_edgar._get_json", side_effect=[submissions, facts]):
            result = fetch_sec_financials("NVDA", "agent@example.com")

        self.assertEqual(result.latest_10q.filing_date, "2026-05-01")
        self.assertEqual(result.metrics["revenue"]["value"], 1000)
        self.assertEqual(result.metrics["revenue"]["classification"], "actual")
        self.assertEqual(result.metrics["operating_income"]["classification"], "unavailable")

    def test_macro_connector_parses_mocked_fred_response(self) -> None:
        payload = {"observations": [{"date": "2026-07-01", "value": "4.5"}, {"date": "2026-06-30", "value": "4.4"}]}
        with patch("src.connectors.macro_data._get_json", return_value=payload):
            result = fetch_macro_indicators("fred")

        self.assertEqual(result[0].source, "FRED")
        self.assertEqual(result[0].trend_direction, "up")

    def test_macro_connector_uses_fred_csv_fallback_without_api_key(self) -> None:
        csv_text = "observation_date,DGS10\n2026-06-30,4.4\n2026-07-01,4.5\n"
        with patch("src.connectors.macro_data._get_text", return_value=csv_text):
            result = fetch_macro_indicators("")

        self.assertEqual(result[0].source, "FRED public CSV")
        self.assertEqual(result[0].latest_value, 4.5)
        self.assertEqual(result[0].trend_direction, "up")

    def test_macro_connector_adds_recent_history_comparison(self) -> None:
        csv_text = (
            "observation_date,DGS10\n"
            "2026-06-26,4.0\n"
            "2026-06-27,4.1\n"
            "2026-06-28,4.2\n"
            "2026-06-30,4.3\n"
            "2026-07-01,4.5\n"
        )
        with patch("src.connectors.macro_data._get_text", return_value=csv_text):
            result = fetch_macro_indicators("")

        self.assertIsNotNone(result[0].historical_average)
        self.assertIn("above recent average", result[0].historical_comparison)

    def test_anysearch_connector_classifies_primary_and_rumor_sources(self) -> None:
        self.assertEqual(classify_source("https://www.sec.gov/ixviewer", "SEC", "")[0], "sec_filing")
        self.assertEqual(classify_source("https://www.sec.gov/ixviewer", "SEC", "")[1], "high")
        self.assertEqual(classify_source("https://blog.example.com/rumor", "Blog", "rumor")[1], "low")

    def test_anysearch_connector_normalizes_cached_response(self) -> None:
        result = normalize_search_result(
            {
                "query": "NVDA release",
                "title": "Official release",
                "source_name": "Company IR",
                "url": "https://investor.example.com/news",
                "published_date": "2026-07-01",
                "snippet": "official",
                "relevance_score": 0.9,
            },
            ticker="NVDA",
        )

        self.assertEqual(result.source_type, "primary_company_source")
        self.assertEqual(result.confidence, "high")
        self.assertEqual(result.status, "confirmed")

    def test_anysearch_direct_call_does_not_fetch_financial_data(self) -> None:
        results = search_anysearch("NVDA price market cap", "key", ticker="NVDA")

        self.assertEqual(results[0].source_name, "AnySearch Codex skill")
        self.assertEqual(results[0].status, "pending")
        self.assertIn("cache", results[0].snippet.lower())

    def test_validation_flags_missing_and_impossible_values(self) -> None:
        report = validate_metrics(
            (
                ValidatedMetric("price", -1, "Market data", "2026-07-06", "actual"),
                ValidatedMetric("revenue", None, "SEC", "", "unavailable"),
            )
        )

        self.assertLess(report.data_quality_score, 100)
        self.assertTrue(report.missing_data_warnings)
        self.assertTrue(report.impossible_value_warnings)

    def test_official_ir_urls_load_from_data_sources_yaml(self) -> None:
        urls = load_official_ir_urls("NVDA")

        self.assertIn("https://investor.nvidia.com/", urls)

    def test_environment_diagnostics_show_missing_and_fallbacks(self) -> None:
        text = render_data_diagnostics(AppConfig("", "", "", "", "", "", "", ""))

        self.assertIn("SEC_USER_AGENT", text)
        self.assertIn("missing", text)
        self.assertIn("required for SEC", text)
        self.assertIn("FRED public CSV", text)
        self.assertIn("yfinance", text)
        self.assertIn("FMP is optional", text)
        self.assertIn("outputs/source_cache", text)


if __name__ == "__main__":
    unittest.main()
