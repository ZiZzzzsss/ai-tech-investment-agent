"""Financial Modeling Prep connector and response mappers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from src.data.models import ProviderMetric

FMP_BASE_URL = "https://financialmodelingprep.com/api"


def fetch_fmp_market_bundle(ticker: str, api_key: str) -> dict[str, object]:
    """Fetch FMP quote, historical prices, metrics, estimates, earnings, profile, and news."""

    retrieved_at = datetime.now(UTC).isoformat()
    if not api_key:
        return {"warning": "Unavailable: FMP_API_KEY missing.", "retrieved_at": retrieved_at}
    quote_url = _url(f"/v3/quote/{ticker.upper()}", api_key)
    history_url = _url(f"/v3/historical-price-full/{ticker.upper()}", api_key)
    metrics_url = _url(f"/v3/key-metrics-ttm/{ticker.upper()}", api_key)
    estimates_url = _url(f"/v3/analyst-estimates/{ticker.upper()}", api_key)
    earnings_url = _url(f"/v3/historical/earning_calendar/{ticker.upper()}", api_key)
    profile_url = _url(f"/v3/profile/{ticker.upper()}", api_key)
    news_url = _url(f"/v3/stock_news", api_key, {"tickers": ticker.upper(), "limit": "10"})
    try:
        quote = _get_json(quote_url)
        history = _get_json(history_url)
        key_metrics = _get_json(metrics_url)
        estimates = _get_json(estimates_url)
        earnings = _get_json(earnings_url)
        profile = _get_json(profile_url)
        news = _get_json(news_url)
    except OSError as exc:
        return {"warning": f"Unavailable: FMP request failed: {exc}", "retrieved_at": retrieved_at}
    return {
        "quote": parse_fmp_quote(quote, quote_url, retrieved_at),
        "historical_prices": parse_fmp_historical_prices(history),
        "key_metrics": parse_fmp_key_metrics(key_metrics, metrics_url, retrieved_at),
        "analyst_estimates": parse_fmp_analyst_estimates(estimates, estimates_url, retrieved_at),
        "earnings_calendar": parse_fmp_earnings_calendar(earnings, earnings_url, retrieved_at),
        "profile": parse_fmp_profile(profile, profile_url, retrieved_at),
        "news": parse_fmp_news(news, news_url, retrieved_at),
        "retrieved_at": retrieved_at,
    }


def fetch_fmp_financials(ticker: str, api_key: str) -> dict[str, ProviderMetric]:
    """Fetch selected FMP financial-statement fields."""

    retrieved_at = datetime.now(UTC).isoformat()
    if not api_key:
        return {}
    income_url = _url(f"/v3/income-statement/{ticker.upper()}", api_key, {"limit": "1"})
    balance_url = _url(f"/v3/balance-sheet-statement/{ticker.upper()}", api_key, {"limit": "1"})
    cashflow_url = _url(f"/v3/cash-flow-statement/{ticker.upper()}", api_key, {"limit": "1"})
    try:
        income = _first(_get_json(income_url))
        balance = _first(_get_json(balance_url))
        cashflow = _first(_get_json(cashflow_url))
    except OSError:
        return {}
    return parse_fmp_financial_statements(income, balance, cashflow, income_url, retrieved_at)


def parse_fmp_quote(payload: object, source_url: str = "", retrieved_at: str = "") -> dict[str, ProviderMetric]:
    row = _first(payload)
    return {
        "latest_price": _metric(row.get("price"), source_url, retrieved_at),
        "previous_close": _metric(row.get("previousClose"), source_url, retrieved_at),
        "open": _metric(row.get("open"), source_url, retrieved_at),
        "high": _metric(row.get("dayHigh"), source_url, retrieved_at),
        "low": _metric(row.get("dayLow"), source_url, retrieved_at),
        "volume": _metric(row.get("volume"), source_url, retrieved_at),
        "market_cap": _metric(row.get("marketCap"), source_url, retrieved_at),
        "eps": _metric(row.get("eps"), source_url, retrieved_at),
    }


def parse_fmp_historical_prices(payload: object) -> list[dict[str, float | int | str]]:
    rows = payload.get("historical", []) if isinstance(payload, dict) else []
    return [
        {
            "date": str(row.get("date", "")),
            "open": _float(row.get("open")),
            "high": _float(row.get("high")),
            "low": _float(row.get("low")),
            "close": _float(row.get("close")),
            "volume": int(_float(row.get("volume")) or 0),
        }
        for row in rows
        if isinstance(row, dict) and _float(row.get("close")) is not None
    ]


def parse_fmp_key_metrics(payload: object, source_url: str = "", retrieved_at: str = "") -> dict[str, ProviderMetric]:
    row = _first(payload)
    return {
        "enterprise_value": _metric(row.get("enterpriseValueTTM"), source_url, retrieved_at),
        "ev_to_sales": _metric(row.get("evToSalesTTM"), source_url, retrieved_at),
        "ev_to_ebitda": _metric(row.get("enterpriseValueOverEBITDATTM"), source_url, retrieved_at),
        "pe_ratio": _metric(row.get("peRatioTTM"), source_url, retrieved_at),
        "pfcf_ratio": _metric(row.get("pfcfRatioTTM"), source_url, retrieved_at),
        "free_cash_flow_per_share": _metric(row.get("freeCashFlowPerShareTTM"), source_url, retrieved_at),
    }


def parse_fmp_financial_statements(
    income: dict[str, Any],
    balance: dict[str, Any],
    cashflow: dict[str, Any],
    source_url: str = "",
    retrieved_at: str = "",
) -> dict[str, ProviderMetric]:
    period = str(income.get("date", "") or cashflow.get("date", "") or balance.get("date", ""))
    ocf = _float(cashflow.get("operatingCashFlow") or cashflow.get("netCashProvidedByOperatingActivities"))
    capex = _float(cashflow.get("capitalExpenditure") or cashflow.get("investmentsInPropertyPlantAndEquipment"))
    fcf = ocf + capex if ocf is not None and capex is not None else None
    return {
        "revenue": _metric(income.get("revenue"), source_url, retrieved_at, period),
        "gross_profit": _metric(income.get("grossProfit"), source_url, retrieved_at, period),
        "operating_income": _metric(income.get("operatingIncome"), source_url, retrieved_at, period),
        "ebitda": _metric(income.get("ebitda"), source_url, retrieved_at, period),
        "net_income": _metric(income.get("netIncome"), source_url, retrieved_at, period),
        "cash_and_equivalents": _metric(balance.get("cashAndCashEquivalents"), source_url, retrieved_at, period),
        "total_debt": _metric(balance.get("totalDebt"), source_url, retrieved_at, period),
        "operating_cash_flow": _metric(ocf, source_url, retrieved_at, period),
        "capital_expenditure": _metric(capex, source_url, retrieved_at, period),
        "free_cash_flow": _metric(fcf, source_url, retrieved_at, period, "derived_calculation"),
        "shares_outstanding": _metric(income.get("weightedAverageShsOutDil"), source_url, retrieved_at, period),
        "diluted_eps": _metric(income.get("epsdiluted"), source_url, retrieved_at, period),
    }


def parse_fmp_analyst_estimates(payload: object, source_url: str = "", retrieved_at: str = "") -> dict[str, ProviderMetric]:
    row = _first(payload)
    return {
        "estimated_eps_avg": _metric(row.get("estimatedEpsAvg"), source_url, retrieved_at, str(row.get("date", "")), "estimated"),
        "estimated_revenue_avg": _metric(row.get("estimatedRevenueAvg"), source_url, retrieved_at, str(row.get("date", "")), "estimated"),
    }


def parse_fmp_earnings_calendar(payload: object, source_url: str = "", retrieved_at: str = "") -> dict[str, ProviderMetric]:
    row = _first(payload)
    return {"earnings_date": _metric(row.get("date"), source_url, retrieved_at, str(row.get("date", "")), "estimated")}


def parse_fmp_profile(payload: object, source_url: str = "", retrieved_at: str = "") -> dict[str, ProviderMetric]:
    row = _first(payload)
    return {
        "company_name": _metric(row.get("companyName"), source_url, retrieved_at),
        "exchange": _metric(row.get("exchangeShortName"), source_url, retrieved_at),
        "sector": _metric(row.get("sector"), source_url, retrieved_at),
    }


def parse_fmp_news(payload: object, source_url: str = "", retrieved_at: str = "") -> tuple[dict[str, str], ...]:
    rows = payload if isinstance(payload, list) else []
    return tuple(
        {
            "title": str(row.get("title", "")),
            "url": str(row.get("url", "")),
            "published_date": str(row.get("publishedDate", "")),
            "source_name": str(row.get("site", "FMP news")),
            "retrieved_at": retrieved_at,
        }
        for row in rows
        if isinstance(row, dict)
    )


def _metric(
    value: object,
    source_url: str,
    retrieved_at: str,
    fiscal_period: str = "",
    data_type: str = "actual",
    confidence: str = "medium",
) -> ProviderMetric:
    return ProviderMetric(
        value=_float(value) if isinstance(value, (int, float, str)) and _looks_number(value) else value,
        source_name="Financial Modeling Prep",
        source_url=source_url,
        provider="FMP",
        retrieved_at=retrieved_at,
        fiscal_period=fiscal_period,
        data_type=data_type,
        confidence=confidence,
        note="Structured financial data from FMP; not yet verified against SEC EDGAR.",
    )


def _url(path: str, api_key: str, extra: dict[str, str] | None = None) -> str:
    params = {"apikey": api_key}
    if extra:
        params.update(extra)
    return f"{FMP_BASE_URL}{path}?{urlencode(params)}"


def _get_json(url: str) -> object:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _first(payload: object) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        return payload
    return {}


def _looks_number(value: object) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
