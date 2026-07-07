"""Formula tests for the valuation module."""

import unittest
from types import SimpleNamespace

from src.reports.markdown_report import _live_valuation_outputs
from src.valuation import (
    ScenarioInput,
    calculate_entry_zones,
    calculate_scenarios,
    enterprise_value,
    fcf_margin,
    probability_weighted_fair_value,
    revenue_cagr,
)
from src.validation.formula_registry import calculate_formula


class ValuationMathTests(unittest.TestCase):
    def test_enterprise_value_formula(self) -> None:
        result = enterprise_value(
            market_cap=1_000.0,
            total_debt=200.0,
            cash_and_equivalents=150.0,
            minority_interest=25.0,
            preferred_equity=10.0,
        )

        self.assertEqual(result, 1_085.0)

    def test_fixture_valuation_formulas(self) -> None:
        inputs = {
            "price": 100,
            "shares_outstanding": 10,
            "market_cap": 1000,
            "total_debt": 300,
            "cash": 100,
            "enterprise_value": 1200,
            "revenue": 500,
            "ebitda": 120,
            "net_income": 50,
            "operating_cash_flow": 80,
            "capex": 20,
            "free_cash_flow": 60,
            "gross_profit": 250,
            "operating_income": 100,
        }

        self.assertEqual(calculate_formula("market_cap", inputs), 1000)
        self.assertEqual(calculate_formula("enterprise_value", inputs), 1200)
        self.assertEqual(calculate_formula("ev_sales", inputs), 2.4)
        self.assertEqual(calculate_formula("ev_ebitda", inputs), 10)
        self.assertEqual(calculate_formula("pe_ratio", inputs), 20)
        self.assertAlmostEqual(calculate_formula("p_fcf", inputs), 16.6666667)
        self.assertEqual(calculate_formula("gross_margin", inputs), 0.5)
        self.assertEqual(calculate_formula("operating_margin", inputs), 0.2)
        self.assertEqual(calculate_formula("net_margin", inputs), 0.1)
        self.assertEqual(calculate_formula("fcf_margin", inputs), 0.12)

    def test_fcf_margin_formula(self) -> None:
        self.assertEqual(fcf_margin(free_cash_flow=25.0, revenue=100.0), 0.25)

    def test_cagr_formula(self) -> None:
        result = revenue_cagr(start_revenue=100.0, end_revenue=121.0, years=2.0)

        self.assertAlmostEqual(result, 0.10)

    def test_probability_weighted_value_formula(self) -> None:
        scenarios = calculate_scenarios(
            bear=ScenarioInput(
                name="Bear",
                revenue=100.0,
                ebitda_margin=0.20,
                ev_ebitda_multiple=8.0,
                net_debt=10.0,
                shares_outstanding=10.0,
                probability=0.25,
            ),
            base=ScenarioInput(
                name="Base",
                revenue=120.0,
                ebitda_margin=0.25,
                ev_ebitda_multiple=10.0,
                net_debt=10.0,
                shares_outstanding=10.0,
                probability=0.50,
            ),
            bull=ScenarioInput(
                name="Bull",
                revenue=150.0,
                ebitda_margin=0.30,
                ev_ebitda_multiple=12.0,
                net_debt=10.0,
                shares_outstanding=10.0,
                probability=0.25,
            ),
        )

        self.assertEqual([scenario.name for scenario in scenarios], ["Bear", "Base", "Bull"])
        self.assertAlmostEqual(probability_weighted_fair_value(scenarios), 31.5)

    def test_entry_zone_calculation(self) -> None:
        zones = calculate_entry_zones(fair_value_per_share=100.0)

        self.assertEqual(zones.conservative_entry_max, 75.0)
        self.assertEqual(zones.reasonable_accumulation_min, 75.0)
        self.assertEqual(zones.reasonable_accumulation_max, 95.0)
        self.assertEqual(zones.expensive_wait_min, 95.0)

    def test_live_valuation_calculates_partial_metrics(self) -> None:
        market = SimpleNamespace(
            latest_price=10.0,
            price_timestamp="2026-07-01",
            market_cap=None,
            moving_average_20=9.0,
            moving_average_50=8.0,
            moving_average_100=None,
            moving_average_200=None,
            warning="",
        )
        sec = SimpleNamespace(
            metrics={
                "shares_outstanding": {"value": 100.0},
                "revenue": {"value": 500.0},
                "net_income": {"value": None},
                "free_cash_flow": {"value": None},
                "cash_and_equivalents": {"value": 50.0},
                "total_debt": {"value": 25.0},
            }
        )

        multiples, scenarios, fair_value, zones, period_rows = _live_valuation_outputs(market, sec)

        self.assertEqual(multiples["Latest price"], "$10.00")
        self.assertEqual(multiples["Market cap"], "$1,000.00")
        self.assertEqual(multiples["Enterprise value"], "$975.00")
        self.assertIn("revenue missing", multiples["EV/Sales"])
        self.assertIn("Unavailable", multiples["P/E"])
        self.assertEqual(fair_value, 0.0)
        self.assertEqual(zones.expensive_wait_min, 0.0)
        self.assertEqual(scenarios[0].fair_value_per_share, 0.0)
        self.assertTrue(any(row.metric == "EV/Sales" for row in period_rows))


if __name__ == "__main__":
    unittest.main()
