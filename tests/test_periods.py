import unittest

from src.data.models import DataPoint
from src.data.validation import period_validation_warnings
from src.data.periods import (
    FiscalPeriod,
    PeriodMetric,
    normalize_period_label,
    point_in_time_period,
    validate_matching_periods,
)


class FiscalPeriodTests(unittest.TestCase):
    def test_normalizes_quarterly_label(self) -> None:
        period = normalize_period_label("FY 2025 Q1", provider="SEC EDGAR", as_of_date="2025-04-27")

        self.assertEqual(period.period_type, "quarterly")
        self.assertEqual(period.fiscal_year, 2025)
        self.assertEqual(period.fiscal_quarter, 1)
        self.assertEqual(period.period_end_date, "2025-04-27")

    def test_datapoint_gets_fiscal_period(self) -> None:
        point = DataPoint(
            value=100,
            source_name="SEC EDGAR",
            provider="SEC",
            source_url="",
            retrieved_at="2026-07-07",
            fiscal_period="FY 2025 Q4",
        )

        self.assertIsNotNone(point.period)
        self.assertEqual(point.period.period_type, "quarterly")
        self.assertEqual(point.period.fiscal_quarter, 4)

    def test_matching_period_validation_rejects_annual_quarterly_mix(self) -> None:
        annual = PeriodMetric("revenue", 500, FiscalPeriod("annual", fiscal_year=2025, period_end_date="2025-12-31"), "fixture")
        quarterly = PeriodMetric("operating_income", 100, FiscalPeriod("quarterly", fiscal_year=2025, fiscal_quarter=4, period_end_date="2025-12-31"), "fixture")

        result = validate_matching_periods(quarterly, annual)

        self.assertFalse(result.aligned)
        self.assertIn("period mismatch", result.warning)

    def test_period_warnings_flag_quarterly_value(self) -> None:
        metric = PeriodMetric("net_income", 50, FiscalPeriod("quarterly", fiscal_year=2025, fiscal_quarter=4, period_end_date="2025-12-31"), "fixture")

        warnings = period_validation_warnings((metric,))

        self.assertTrue(any("quarterly value" in warning for warning in warnings))

    def test_point_in_time_period(self) -> None:
        period = point_in_time_period("2026-07-07", "yfinance")

        self.assertEqual(period.period_type, "point_in_time")
        self.assertEqual(period.period_end_date, "2026-07-07")


if __name__ == "__main__":
    unittest.main()
