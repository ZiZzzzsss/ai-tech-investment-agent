import unittest

from src.data.periods import FiscalPeriod, PeriodMetric, calculate_ttm_free_cash_flow, calculate_ttm_metric


def quarter(name: str, value: float, year: int, quarter_num: int) -> PeriodMetric:
    return PeriodMetric(
        name=name,
        value=value,
        period=FiscalPeriod(
            "quarterly",
            fiscal_year=year,
            fiscal_quarter=quarter_num,
            period_end_date=f"{year}-0{quarter_num * 3}-30" if quarter_num < 4 else f"{year}-12-31",
            source_period_label=f"FY{year} Q{quarter_num}",
        ),
        source_name="fixture",
        source_lineage=(f"FY{year} Q{quarter_num}",),
    )


def annual(name: str, value: float, year: int) -> PeriodMetric:
    return PeriodMetric(
        name=name,
        value=value,
        period=FiscalPeriod(
            "annual",
            fiscal_year=year,
            period_end_date=f"{year}-12-31",
            source_period_label=f"FY{year}",
        ),
        source_name="fixture",
        source_lineage=(f"FY{year}",),
    )


def sec_quarter(name: str, value: float, year: int, quarter_num: int, label: str) -> PeriodMetric:
    return PeriodMetric(
        name=name,
        value=value,
        period=FiscalPeriod(
            "quarterly",
            fiscal_year=year,
            fiscal_quarter=quarter_num,
            period_end_date=f"{year}-0{quarter_num * 3}-30" if quarter_num < 4 else f"{year}-12-31",
            source_period_label=label,
        ),
        source_name="fixture",
        source_lineage=(label,),
    )


class TtmCalculationTests(unittest.TestCase):
    def test_correct_ttm_revenue_calculation(self) -> None:
        result = calculate_ttm_metric(
            "revenue",
            (
                quarter("revenue", 100, 2025, 1),
                quarter("revenue", 120, 2025, 2),
                quarter("revenue", 130, 2025, 3),
                quarter("revenue", 150, 2025, 4),
            ),
        )

        self.assertEqual(result.value, 500)
        self.assertEqual(result.period.period_type, "ttm")

    def test_ttm_derives_q4_from_annual_and_ignores_ytd_duplicates(self) -> None:
        result = calculate_ttm_metric(
            "revenue",
            (
                sec_quarter("revenue", 100, 2025, 1, "Q1"),
                sec_quarter("revenue", 100, 2025, 1, "CY2025Q1"),
                sec_quarter("revenue", 220, 2025, 2, "Q2"),
                sec_quarter("revenue", 120, 2025, 2, "CY2025Q2"),
                sec_quarter("revenue", 350, 2025, 3, "Q3"),
                sec_quarter("revenue", 130, 2025, 3, "CY2025Q3"),
                annual("revenue", 500, 2025),
                sec_quarter("revenue", 160, 2026, 1, "CY2026Q1"),
            ),
        )

        self.assertEqual(result.value, 560)
        self.assertEqual(result.source_lineage, ("CY2025Q2", "CY2025Q3", "FY2025 derived Q4", "CY2026Q1"))
        self.assertEqual(result.period.period_type, "ttm")

    def test_missing_quarter_prevents_ttm(self) -> None:
        result = calculate_ttm_metric(
            "revenue",
            (
                quarter("revenue", 100, 2025, 1),
                quarter("revenue", 120, 2025, 2),
                quarter("revenue", 130, 2025, 3),
            ),
        )

        self.assertIsNone(result.value)
        self.assertIn("fewer than four quarters", result.warning)

    def test_capex_sign_is_normalized_for_fcf(self) -> None:
        ocf = PeriodMetric("ttm_operating_cash_flow", 100, FiscalPeriod("ttm", source_period_label="TTM"), "fixture")
        capex = PeriodMetric("ttm_capex", -30, FiscalPeriod("ttm", source_period_label="TTM"), "fixture")

        fcf = calculate_ttm_free_cash_flow(ocf, capex)

        self.assertEqual(fcf.value, 70)

    def test_margin_alignment_from_ttm_inputs(self) -> None:
        revenue = PeriodMetric("ttm_revenue", 500, FiscalPeriod("ttm", source_period_label="TTM", period_end_date="2025-12-31"), "fixture")
        gross_profit = PeriodMetric("ttm_gross_profit", 250, FiscalPeriod("ttm", source_period_label="TTM", period_end_date="2025-12-31"), "fixture")

        self.assertEqual(gross_profit.value / revenue.value, 0.5)


if __name__ == "__main__":
    unittest.main()
