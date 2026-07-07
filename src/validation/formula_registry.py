"""Central registry of audited calculation formulas."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


Number = float | int


@dataclass(frozen=True)
class FormulaDefinition:
    formula_name: str
    formula_text: str
    required_inputs: tuple[str, ...]
    calculation_function: Callable[..., float]
    expected_units: str
    rounding_rule: str
    unavailable_rule: str
    common_error_checks: tuple[str, ...]
    source_file: str
    source_function: str


def _positive(value: Number, label: str) -> None:
    if float(value) <= 0:
        raise ValueError(f"{label} must be positive.")


def market_cap(price: Number, shares_outstanding: Number) -> float:
    return float(price) * float(shares_outstanding)


def enterprise_value(market_cap: Number, total_debt: Number, cash: Number) -> float:
    return float(market_cap) + float(total_debt) - float(cash)


def ev_sales(enterprise_value: Number, revenue: Number) -> float:
    _positive(revenue, "revenue")
    return float(enterprise_value) / float(revenue)


def ev_ebitda(enterprise_value: Number, ebitda: Number) -> float:
    _positive(ebitda, "EBITDA")
    return float(enterprise_value) / float(ebitda)


def pe_ratio(market_cap: Number, net_income: Number) -> float:
    _positive(net_income, "net income")
    return float(market_cap) / float(net_income)


def p_fcf(market_cap: Number, free_cash_flow: Number) -> float:
    _positive(free_cash_flow, "free cash flow")
    return float(market_cap) / float(free_cash_flow)


def ps_ratio(market_cap: Number, revenue: Number) -> float:
    _positive(revenue, "revenue")
    return float(market_cap) / float(revenue)


def gross_margin(gross_profit: Number, revenue: Number) -> float:
    _positive(revenue, "revenue")
    return float(gross_profit) / float(revenue)


def operating_margin(operating_income: Number, revenue: Number) -> float:
    _positive(revenue, "revenue")
    return float(operating_income) / float(revenue)


def net_margin(net_income: Number, revenue: Number) -> float:
    _positive(revenue, "revenue")
    return float(net_income) / float(revenue)


def free_cash_flow(operating_cash_flow: Number, capex: Number) -> float:
    return float(operating_cash_flow) - abs(float(capex))


def fcf_margin(free_cash_flow: Number, revenue: Number) -> float:
    _positive(revenue, "revenue")
    return float(free_cash_flow) / float(revenue)


def ttm_sum(q1: Number, q2: Number, q3: Number, q4: Number) -> float:
    return float(q1) + float(q2) + float(q3) + float(q4)


def ttm_free_cash_flow(operating_cash_flow_ttm: Number, capex_ttm: Number) -> float:
    return float(operating_cash_flow_ttm) - abs(float(capex_ttm))


def revenue_growth_yoy(current_period_revenue: Number, prior_year_same_period_revenue: Number) -> float:
    _positive(prior_year_same_period_revenue, "prior-year same-period revenue")
    return float(current_period_revenue) / float(prior_year_same_period_revenue) - 1


def revenue_growth_qoq(current_quarter_revenue: Number, previous_quarter_revenue: Number) -> float:
    _positive(previous_quarter_revenue, "previous-quarter revenue")
    return float(current_quarter_revenue) / float(previous_quarter_revenue) - 1


def cagr(beginning_value: Number, ending_value: Number, years: Number) -> float:
    _positive(beginning_value, "beginning value")
    _positive(ending_value, "ending value")
    _positive(years, "years")
    return (float(ending_value) / float(beginning_value)) ** (1 / float(years)) - 1


def moving_average_n(closing_prices: tuple[Number, ...], n: Number) -> float:
    period = int(n)
    if period <= 0:
        raise ValueError("moving-average period must be positive.")
    if len(closing_prices) < period:
        raise ValueError("not enough closing prices for moving average.")
    values = [float(value) for value in closing_prices[-period:]]
    return sum(values) / period


def price_dma_divergence(current_price: Number, moving_average: Number) -> float:
    _positive(moving_average, "moving average")
    return float(current_price) / float(moving_average) - 1


def probability_weighted_value(scenario_values: tuple[Number, ...], scenario_probabilities: tuple[Number, ...]) -> float:
    if len(scenario_values) != len(scenario_probabilities):
        raise ValueError("scenario values and probabilities must have the same length.")
    probability_sum = sum(float(probability) for probability in scenario_probabilities)
    if probability_sum <= 0:
        raise ValueError("scenario probabilities must sum to a positive value.")
    return sum(float(value) * float(probability) for value, probability in zip(scenario_values, scenario_probabilities)) / probability_sum


def conservative_entry(base_case_value: Number, margin_of_safety_factor: Number) -> float:
    factor = float(margin_of_safety_factor)
    if factor < 0 or factor >= 1:
        raise ValueError("margin of safety factor must be between 0 and 1.")
    return float(base_case_value) * (1 - factor)


def traditional_peg(pe_ratio: Number, eps_growth_percent: Number) -> float:
    _positive(eps_growth_percent, "EPS growth percent")
    return float(pe_ratio) / float(eps_growth_percent)


def tam_adjusted_peg(
    traditional_peg: Number,
    tam_multiplier: Number,
    quality_multiplier: Number,
    risk_multiplier: Number,
) -> float:
    return float(traditional_peg) * float(tam_multiplier) * float(quality_multiplier) * float(risk_multiplier)


def gf_dma_escape_ratio(current_price: Number, dma_200: Number, fundamental_support_score: Number = 50) -> float:
    _positive(dma_200, "200DMA")
    raw_ratio = float(current_price) / float(dma_200)
    support_adjustment = 1 + max(0.0, min(50.0, float(fundamental_support_score) - 50.0)) / 200
    return raw_ratio / support_adjustment


def data_quality_score(
    missing_count: Number,
    stale_count: Number,
    inconsistent_count: Number,
    impossible_count: Number,
    mock_data_used: Number,
) -> float:
    penalty = (
        float(missing_count) * 8
        + float(stale_count) * 4
        + float(inconsistent_count) * 8
        + float(impossible_count) * 20
        + (25 if float(mock_data_used) else 0)
    )
    return max(0.0, 100.0 - penalty)


def calculate_formula(formula_name: str, inputs: dict[str, object]) -> float:
    formula = FORMULA_REGISTRY[formula_name]
    kwargs = {name: inputs[name] for name in formula.required_inputs}
    return formula.calculation_function(**kwargs)


def _formula(
    name: str,
    text: str,
    inputs: tuple[str, ...],
    fn: Callable[..., float],
    units: str,
    checks: tuple[str, ...],
) -> FormulaDefinition:
    return FormulaDefinition(
        formula_name=name,
        formula_text=text,
        required_inputs=inputs,
        calculation_function=fn,
        expected_units=units,
        rounding_rule="round for display only; tests compare with tolerance 1e-4",
        unavailable_rule="if any required input is missing, stale, nonnumeric, or denominator is <= 0, mark metric unavailable with warning",
        common_error_checks=checks,
        source_file="src/validation/formula_registry.py",
        source_function=fn.__name__,
    )


COMMON_UNITS = (
    "check millions vs billions mismatch",
    "reject missing or stale values without warning",
    "do not use AnySearch text numbers as structured financial inputs",
)

FORMULA_REGISTRY: dict[str, FormulaDefinition] = {
    "market_cap": _formula("market_cap", "market_cap = price * shares_outstanding", ("price", "shares_outstanding"), market_cap, "currency", ("do not use price alone as market cap", *COMMON_UNITS)),
    "enterprise_value": _formula("enterprise_value", "enterprise_value = market_cap + total_debt - cash", ("market_cap", "total_debt", "cash"), enterprise_value, "currency", ("do not use market cap when EV is required", *COMMON_UNITS)),
    "ev_sales": _formula("ev_sales", "ev_sales = enterprise_value / revenue", ("enterprise_value", "revenue"), ev_sales, "multiple", ("use enterprise value, not market cap", *COMMON_UNITS)),
    "ev_ebitda": _formula("ev_ebitda", "ev_ebitda = enterprise_value / EBITDA", ("enterprise_value", "ebitda"), ev_ebitda, "multiple", ("use EBITDA, not net income", *COMMON_UNITS)),
    "pe_ratio": _formula("pe_ratio", "pe_ratio = market_cap / net_income", ("market_cap", "net_income"), pe_ratio, "multiple", ("use market cap, not price", *COMMON_UNITS)),
    "p_fcf": _formula("p_fcf", "p_fcf = market_cap / free_cash_flow", ("market_cap", "free_cash_flow"), p_fcf, "multiple", ("calculate FCF after capex sign normalization", *COMMON_UNITS)),
    "ps_ratio": _formula("ps_ratio", "ps_ratio = market_cap / revenue", ("market_cap", "revenue"), ps_ratio, "multiple", ("use market cap, not enterprise value", *COMMON_UNITS)),
    "gross_margin": _formula("gross_margin", "gross_margin = gross_profit / revenue", ("gross_profit", "revenue"), gross_margin, "decimal percent", ("percentages must be decimals, e.g. 0.25 not 25", *COMMON_UNITS)),
    "operating_margin": _formula("operating_margin", "operating_margin = operating_income / revenue", ("operating_income", "revenue"), operating_margin, "decimal percent", ("percentages must be decimals, e.g. 0.25 not 25", *COMMON_UNITS)),
    "net_margin": _formula("net_margin", "net_margin = net_income / revenue", ("net_income", "revenue"), net_margin, "decimal percent", ("percentages must be decimals, e.g. 0.25 not 25", *COMMON_UNITS)),
    "free_cash_flow": _formula("free_cash_flow", "free_cash_flow = operating_cash_flow - abs(capex)", ("operating_cash_flow", "capex"), free_cash_flow, "currency", ("normalize negative capex sign", *COMMON_UNITS)),
    "fcf_margin": _formula("fcf_margin", "fcf_margin = free_cash_flow / revenue", ("free_cash_flow", "revenue"), fcf_margin, "decimal percent", ("calculate FCF before margin", *COMMON_UNITS)),
    "ttm_sum": _formula("ttm_sum", "TTM = q1 + q2 + q3 + q4", ("q1", "q2", "q3", "q4"), ttm_sum, "currency", ("must use four comparable fiscal quarters", *COMMON_UNITS)),
    "ttm_free_cash_flow": _formula("ttm_free_cash_flow", "TTM FCF = TTM operating cash flow - abs(TTM capex)", ("operating_cash_flow_ttm", "capex_ttm"), ttm_free_cash_flow, "currency", ("normalize capex as positive cash outflow", *COMMON_UNITS)),
    "revenue_growth_yoy": _formula("revenue_growth_yoy", "revenue_growth_yoy = current_period_revenue / prior_year_same_period_revenue - 1", ("current_period_revenue", "prior_year_same_period_revenue"), revenue_growth_yoy, "decimal percent", ("do not use prior quarter for YoY", *COMMON_UNITS)),
    "revenue_growth_qoq": _formula("revenue_growth_qoq", "revenue_growth_qoq = current_quarter_revenue / previous_quarter_revenue - 1", ("current_quarter_revenue", "previous_quarter_revenue"), revenue_growth_qoq, "decimal percent", ("do not use prior-year period for QoQ", *COMMON_UNITS)),
    "cagr": _formula("cagr", "cagr = (ending_value / beginning_value) ** (1 / years) - 1", ("beginning_value", "ending_value", "years"), cagr, "decimal percent", ("years must match period length", *COMMON_UNITS)),
    "moving_average_n": _formula("moving_average_n", "moving_average_n = average(last_n_closing_prices)", ("closing_prices", "n"), moving_average_n, "currency", ("use last n closes in chronological order", *COMMON_UNITS)),
    "price_dma_divergence": _formula("price_dma_divergence", "price_dma_divergence = current_price / moving_average - 1", ("current_price", "moving_average"), price_dma_divergence, "decimal percent", ("do not subtract moving average without dividing by it", *COMMON_UNITS)),
    "probability_weighted_value": _formula("probability_weighted_value", "probability_weighted_value = sum(scenario_value * scenario_probability) / sum(probabilities)", ("scenario_values", "scenario_probabilities"), probability_weighted_value, "currency/share", ("probabilities must sum to a positive value", *COMMON_UNITS)),
    "conservative_entry": _formula("conservative_entry", "conservative_entry = base_case_value * (1 - margin_of_safety_factor)", ("base_case_value", "margin_of_safety_factor"), conservative_entry, "currency/share", ("margin of safety must be decimal", *COMMON_UNITS)),
    "traditional_peg": _formula("traditional_peg", "traditional_peg = pe_ratio / eps_growth_percent", ("pe_ratio", "eps_growth_percent"), traditional_peg, "multiple", ("EPS growth is percentage-point value, e.g. 25 for 25%", *COMMON_UNITS)),
    "tam_adjusted_peg": _formula("tam_adjusted_peg", "tam_adjusted_peg = traditional_peg * tam_multiplier * quality_multiplier * risk_multiplier", ("traditional_peg", "tam_multiplier", "quality_multiplier", "risk_multiplier"), tam_adjusted_peg, "multiple", ("risk multiplier should penalize higher risk", *COMMON_UNITS)),
    "gf_dma_escape_ratio": _formula("gf_dma_escape_ratio", "gf_dma_escape_ratio = (current_price / dma_200) / fundamental_support_adjustment", ("current_price", "dma_200", "fundamental_support_score"), gf_dma_escape_ratio, "ratio", ("this is trend health only, not intrinsic value", *COMMON_UNITS)),
    "data_quality_score": _formula("data_quality_score", "data_quality_score = max(0, 100 - missing*8 - stale*4 - inconsistent*8 - impossible*20 - mock_penalty)", ("missing_count", "stale_count", "inconsistent_count", "impossible_count", "mock_data_used"), data_quality_score, "score 0-100", ("mock data penalty must be explicit", "missing values must be disclosed")),
}
