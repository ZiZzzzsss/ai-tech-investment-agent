import unittest

from src.data.periods import FiscalPeriod, PeriodMetric
from src.valuation.multiples import (
    period_aware_ev_to_sales,
    period_aware_margin,
    period_aware_price_to_earnings,
)


class ValuationPeriodAlignmentTests(unittest.TestCase):
    def test_market_cap_over_quarterly_net_income_fails(self) -> None:
        market_cap = PeriodMetric("market_cap", 1000, FiscalPeriod("point_in_time", period_end_date="2026-07-07"), "fixture")
        quarterly_net_income = PeriodMetric("net_income", 12.5, FiscalPeriod("quarterly", fiscal_year=2025, fiscal_quarter=4, period_end_date="2025-12-31"), "fixture")

        result = period_aware_price_to_earnings(market_cap, quarterly_net_income)

        self.assertIsNone(result.value)
        self.assertIn("must be TTM", result.warning)

    def test_pe_uses_ttm_net_income(self) -> None:
        market_cap = PeriodMetric("market_cap", 1000, FiscalPeriod("point_in_time", period_end_date="2026-07-07"), "fixture")
        ttm_net_income = PeriodMetric("net_income", 50, FiscalPeriod("ttm", source_period_label="TTM"), "fixture")

        result = period_aware_price_to_earnings(market_cap, ttm_net_income)

        self.assertEqual(result.value, 20)
        self.assertEqual(result.output_period_basis, "TTM")

    def test_ev_sales_uses_ttm_revenue(self) -> None:
        ev = PeriodMetric("enterprise_value", 1200, FiscalPeriod("point_in_time", period_end_date="2026-07-07"), "fixture")
        ttm_revenue = PeriodMetric("revenue", 500, FiscalPeriod("ttm", source_period_label="TTM"), "fixture")

        result = period_aware_ev_to_sales(ev, ttm_revenue)

        self.assertEqual(result.value, 2.4)

    def test_annual_revenue_with_quarterly_operating_income_fails_margin(self) -> None:
        annual_revenue = PeriodMetric("revenue", 500, FiscalPeriod("annual", fiscal_year=2025, period_end_date="2025-12-31"), "fixture")
        quarterly_operating_income = PeriodMetric("operating_income", 100, FiscalPeriod("quarterly", fiscal_year=2025, fiscal_quarter=4, period_end_date="2025-12-31"), "fixture")

        result = period_aware_margin("Operating margin", quarterly_operating_income, annual_revenue, "operating_income")

        self.assertIsNone(result.value)
        self.assertIn("period mismatch", result.warning)


if __name__ == "__main__":
    unittest.main()
