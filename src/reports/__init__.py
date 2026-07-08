"""Report rendering utilities."""

from src.reports.markdown import REQUIRED_SECTIONS, render_company_memo
from src.reports.markdown_report import (
    MANDATORY_SECTIONS,
    BuySideMemoInput,
    build_live_buy_side_memo_input,
    build_mock_buy_side_memo_input,
    build_mock_memo_snapshot,
    render_buy_side_memo,
    render_mock_buy_side_memo,
)
from src.reports.html_report import (
    HTML_MANDATORY_SECTIONS,
    render_html_memo,
    render_index,
)
from src.reports.report_schema import (
    ClaimType,
    EvidenceClaim,
    ReportValidationResult,
    validate_evidence_claims,
    validate_no_direct_investment_advice,
    validate_report_compliance,
)

__all__ = [
    "BuySideMemoInput",
    "build_mock_buy_side_memo_input",
    "build_live_buy_side_memo_input",
    "build_mock_memo_snapshot",
    "ClaimType",
    "EvidenceClaim",
    "HTML_MANDATORY_SECTIONS",
    "MANDATORY_SECTIONS",
    "REQUIRED_SECTIONS",
    "ReportValidationResult",
    "render_buy_side_memo",
    "render_company_memo",
    "render_html_memo",
    "render_index",
    "render_mock_buy_side_memo",
    "validate_evidence_claims",
    "validate_no_direct_investment_advice",
    "validate_report_compliance",
]
