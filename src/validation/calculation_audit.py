"""Deterministic formula audit report generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ast

from src.validation.formula_registry import FORMULA_REGISTRY, FormulaDefinition, calculate_formula


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "calculation_cases.yaml"
DEFAULT_AUDIT_PATH = REPO_ROOT / "outputs" / "calculation_audit.md"


@dataclass(frozen=True)
class AuditCaseResult:
    formula_name: str
    formula_text: str
    input_values: dict[str, object]
    calculated_result: float | None
    expected_result: float | None
    passed: bool
    source_file: str
    source_function: str
    warnings: tuple[str, ...]
    error: str = ""


@dataclass(frozen=True)
class CalculationAuditReport:
    results: tuple[AuditCaseResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def failures(self) -> tuple[AuditCaseResult, ...]:
        return tuple(result for result in self.results if not result.passed)


def audit_calculations(fixture_path: Path = DEFAULT_FIXTURE_PATH) -> CalculationAuditReport:
    fixture = load_calculation_cases(fixture_path)
    results = []
    for formula_name, formula in FORMULA_REGISTRY.items():
        case_inputs, expected = _case_for_formula(formula_name, formula, fixture)
        if expected is None:
            continue
        results.append(_audit_formula(formula, case_inputs, expected))
    return CalculationAuditReport(tuple(results))


def write_audit_report(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    output_path: Path = DEFAULT_AUDIT_PATH,
) -> CalculationAuditReport:
    report = audit_calculations(fixture_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_audit_markdown(report), encoding="utf-8")
    return report


def render_audit_markdown(report: CalculationAuditReport) -> str:
    lines = [
        "# Calculation Audit",
        "",
        f"Overall status: {'PASS' if report.passed else 'FAIL'}",
        "",
        "| Formula | Formula text | Inputs | Calculated | Expected | Status | Source | Warnings |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for result in report.results:
        warnings = "<br>".join(result.warnings) if result.warnings else "None"
        calculated = "" if result.calculated_result is None else f"{result.calculated_result:.6g}"
        expected = "" if result.expected_result is None else f"{result.expected_result:.6g}"
        status = "PASS" if result.passed else f"FAIL: {result.error}"
        lines.append(
            "| "
            f"{result.formula_name} | "
            f"{result.formula_text} | "
            f"{_format_inputs(result.input_values)} | "
            f"{calculated} | "
            f"{expected} | "
            f"{status} | "
            f"{result.source_file}:{result.source_function} | "
            f"{warnings} |"
        )
    return "\n".join(lines) + "\n"


def load_calculation_cases(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, dict[str, dict[str, object]]]:
    """Load the repo's simple calculation fixture YAML subset."""

    cases: dict[str, dict[str, dict[str, object]]] = {}
    current_case = ""
    current_section = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and line.endswith(":"):
            current_case = line[:-1]
            cases[current_case] = {"inputs": {}, "expected": {}}
        elif indent == 2 and line.endswith(":"):
            current_section = line[:-1]
        elif indent == 4 and ":" in line:
            key, value = line.split(":", 1)
            cases[current_case][current_section][key.strip()] = _parse_scalar(value.strip())
    return cases


def _parse_scalar(value: str) -> object:
    if value == "":
        return ""
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        pass
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def _case_for_formula(
    formula_name: str,
    formula: FormulaDefinition,
    fixture: dict[str, dict[str, dict[str, object]]],
) -> tuple[dict[str, object], float | None]:
    for case in fixture.values():
        expected = case.get("expected", {})
        inputs = case.get("inputs", {})
        if formula_name in expected and all(name in inputs for name in formula.required_inputs):
            return {name: inputs[name] for name in formula.required_inputs}, float(expected[formula_name])
    return {}, None


def _audit_formula(
    formula: FormulaDefinition,
    inputs: dict[str, object],
    expected: float,
) -> AuditCaseResult:
    warnings = tuple(_common_warnings(formula, inputs))
    try:
        calculated = calculate_formula(formula.formula_name, inputs)
    except Exception as exc:  # pragma: no cover - still rendered in audit report
        return AuditCaseResult(
            formula.formula_name,
            formula.formula_text,
            inputs,
            None,
            expected,
            False,
            formula.source_file,
            formula.source_function,
            warnings,
            str(exc),
        )
    passed = abs(calculated - expected) <= 1e-4
    return AuditCaseResult(
        formula.formula_name,
        formula.formula_text,
        inputs,
        calculated,
        expected,
        passed,
        formula.source_file,
        formula.source_function,
        warnings,
        "" if passed else f"expected {expected}, got {calculated}",
    )


def _common_warnings(formula: FormulaDefinition, inputs: dict[str, object]) -> list[str]:
    warnings = list(formula.common_error_checks)
    for key, value in inputs.items():
        if key.endswith("growth") or "margin" in key or "factor" in key:
            numeric = _number(value)
            if numeric is not None and abs(numeric) > 2:
                warnings.append(f"{key} may be a percent/decimal mix-up: {value}")
        if key == "capex" and _number(value) is not None and float(value) < 0:
            warnings.append("capex is negative; audit formula normalizes capex with abs(capex)")
    currency_values = [
        abs(float(value))
        for key, value in inputs.items()
        if key not in {"price", "shares_outstanding", "n", "years", "eps_growth_percent"}
        and _number(value) is not None
        and abs(float(value)) > 0
    ]
    if len(currency_values) >= 2 and max(currency_values) / min(currency_values) > 1_000_000:
        warnings.append("possible millions vs billions mismatch")
    return warnings


def _number(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _format_inputs(inputs: dict[str, object]) -> str:
    return "<br>".join(f"{key}={value}" for key, value in inputs.items())
