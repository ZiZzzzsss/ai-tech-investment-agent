"""Tests for formula registry and calculation audit report."""

from __future__ import annotations

import unittest

from src.validation.calculation_audit import audit_calculations, render_audit_markdown
from src.validation.formula_registry import FORMULA_REGISTRY, calculate_formula


class CalculationAuditTests(unittest.TestCase):
    def test_formula_registry_contains_required_formulas(self) -> None:
        required = {
            "market_cap",
            "enterprise_value",
            "ev_sales",
            "ev_ebitda",
            "pe_ratio",
            "p_fcf",
            "ps_ratio",
            "gross_margin",
            "operating_margin",
            "net_margin",
            "free_cash_flow",
            "fcf_margin",
            "revenue_growth_yoy",
            "revenue_growth_qoq",
            "cagr",
            "moving_average_n",
            "price_dma_divergence",
            "probability_weighted_value",
            "conservative_entry",
            "traditional_peg",
            "tam_adjusted_peg",
            "gf_dma_escape_ratio",
            "data_quality_score",
        }

        self.assertTrue(required.issubset(FORMULA_REGISTRY))

    def test_fixture_audit_passes(self) -> None:
        report = audit_calculations()

        self.assertTrue(report.passed, [result.formula_name for result in report.failures])
        self.assertGreaterEqual(len(report.results), 20)

    def test_audit_markdown_contains_source_and_warnings(self) -> None:
        markdown = render_audit_markdown(audit_calculations())

        self.assertIn("# Calculation Audit", markdown)
        self.assertIn("src/validation/formula_registry.py", markdown)
        self.assertIn("do not use AnySearch text numbers", markdown)

    def test_common_error_check_rejects_missing_inputs(self) -> None:
        with self.assertRaises(KeyError):
            calculate_formula("market_cap", {"price": 100})

    def test_negative_capex_sign_is_normalized(self) -> None:
        positive = calculate_formula("free_cash_flow", {"operating_cash_flow": 80, "capex": 20})
        negative = calculate_formula("free_cash_flow", {"operating_cash_flow": 80, "capex": -20})

        self.assertEqual(positive, negative)


if __name__ == "__main__":
    unittest.main()
