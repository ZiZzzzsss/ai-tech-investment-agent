"""Evidence and report compliance schema.

The report layer should never let factual claims quietly blend into assumptions
or estimates. This module provides a small validation surface that mock reports
can use now and source-backed reports can enforce later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ClaimType(str, Enum):
    """Research claim categories."""

    FACT = "Fact"
    ASSUMPTION = "Assumption"
    ESTIMATE = "Estimate"
    INTERPRETATION = "Interpretation"


@dataclass(frozen=True)
class EvidenceClaim:
    """A classified report claim or input."""

    claim_type: ClaimType
    text: str
    value: str = ""
    source: str = ""
    confidence: str = "Low"
    is_mock: bool = True


@dataclass(frozen=True)
class ReportValidationResult:
    """Result of report compliance validation."""

    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


DIRECT_ADVICE_PATTERNS = (
    re.compile(r"\b(?:we\s+)?recommend\s+(?:to\s+)?(?:buy|sell)\b", re.IGNORECASE),
    re.compile(r"\b(?:you|investors?)\s+should\s+(?:buy|sell)\b", re.IGNORECASE),
    re.compile(r"\b(?:buy|sell)\s+rating\b", re.IGNORECASE),
    re.compile(r"^\s*(?:buy|sell)\s+[A-Z]{1,6}\b", re.IGNORECASE | re.MULTILINE),
)


def validate_evidence_claims(
    claims: tuple[EvidenceClaim, ...],
    report_is_mock: bool,
) -> ReportValidationResult:
    """Validate evidence claims for mock or source-backed reports."""

    errors: list[str] = []
    if not claims:
        errors.append("Report must include classified evidence claims.")

    for index, claim in enumerate(claims, start=1):
        if not claim.text.strip():
            errors.append(f"Claim {index} is missing text.")
        if not claim.confidence.strip():
            errors.append(f"Claim {index} is missing confidence.")
        if not report_is_mock and claim.claim_type is ClaimType.FACT:
            if not claim.source.strip() or claim.source.strip().upper().startswith("TODO"):
                errors.append(f"Non-mock factual claim {index} is missing a real source.")
        if not report_is_mock and claim.is_mock:
            errors.append(f"Non-mock report includes mock claim {index}.")

    return ReportValidationResult(errors=tuple(errors))


def validate_no_direct_investment_advice(report_text: str) -> ReportValidationResult:
    """Detect direct buy/sell recommendations."""

    errors = [
        f"Report appears to contain direct investment advice: {pattern.pattern}"
        for pattern in DIRECT_ADVICE_PATTERNS
        if pattern.search(report_text)
    ]
    return ReportValidationResult(errors=tuple(errors))


def validate_report_compliance(
    report_text: str,
    claims: tuple[EvidenceClaim, ...],
    report_is_mock: bool,
) -> ReportValidationResult:
    """Validate report text and claim evidence together."""

    evidence_result = validate_evidence_claims(claims, report_is_mock)
    advice_result = validate_no_direct_investment_advice(report_text)
    return ReportValidationResult(
        errors=evidence_result.errors + advice_result.errors
    )
