"""Tests for report evidence and compliance rules."""

import unittest

from src.reports import (
    ClaimType,
    EvidenceClaim,
    validate_evidence_claims,
    validate_no_direct_investment_advice,
)


class ReportComplianceTests(unittest.TestCase):
    def test_non_mock_factual_claim_requires_source(self) -> None:
        result = validate_evidence_claims(
            claims=(
                EvidenceClaim(
                    claim_type=ClaimType.FACT,
                    text="Revenue grew year over year.",
                    value="10%",
                    source="",
                    confidence="High",
                    is_mock=False,
                ),
            ),
            report_is_mock=False,
        )

        self.assertFalse(result.is_valid)
        self.assertIn("missing a real source", result.errors[0])

    def test_non_mock_report_rejects_mock_claim(self) -> None:
        result = validate_evidence_claims(
            claims=(
                EvidenceClaim(
                    claim_type=ClaimType.ASSUMPTION,
                    text="Mock margin assumption.",
                    value="30%",
                    source="Mock fixture",
                    confidence="Low",
                    is_mock=True,
                ),
            ),
            report_is_mock=False,
        )

        self.assertFalse(result.is_valid)
        self.assertIn("includes mock claim", result.errors[0])

    def test_direct_buy_sell_advice_is_rejected(self) -> None:
        result = validate_no_direct_investment_advice("We recommend buy NVDA today.")

        self.assertFalse(result.is_valid)

    def test_no_advice_disclaimer_is_allowed(self) -> None:
        result = validate_no_direct_investment_advice(
            "This memo does not provide buy, sell, or hold advice."
        )

        self.assertTrue(result.is_valid)


if __name__ == "__main__":
    unittest.main()
