"""EODHD connector and response mappers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from src.data.models import ProviderMetric


EODHD_BASE_URL = "https://eodhd.com/api"


def fetch_eodhd_market_bundle(ticker: str, api_key: str, exchange_suffix: str = "US") -> dict[str, object]:
    """Fetch EODHD price history and fundamentals where configured."""

    retrieved_at = datetime.now(UTC).isoformat()
    if not api_key:
        return {"warning": "Unavailable: EODHD_API_KEY missing.", "retrieved_at": retrieved_at}
    symbol = f"{ticker.upper()}.{exchange_suffix}"
    history_url = _url(f"/eod/{symbol}", api_key, {"fmt": "json", "period": "d"})
    fundamentals_url = _url(f"/fundamentals/{symbol}", api_key, {"fmt": "json"})
    try:
        history = _get_json(history_url)
        fundamentals = _get_json(fundamentals_url)
    except OSError as exc:
        return {"warning": f"Unavailable: EODHD request failed: {exc}", "retrieved_at": retrieved_at}
    return {
        "historical_prices": parse_eodhd_historical_prices(history),
        "fundamentals": parse_eodhd_fundamentals(fundamentals, fundamentals_url, retrieved_at),
        "retrieved_at": retrieved_at,
    }


def parse_eodhd_historical_prices(payload: object) -> list[dict[str, float | int | str]]:
    rows = payload if isinstance(payload, list) else []
    return [
        {
            "date": str(row.get("date", "")),
            "open": _float(row.get("open")),
            "high": _float(row.get("high")),
            "low": _float(row.get("low")),
            "close": _float(row.get("adjusted_close") or row.get("close")),
            "volume": int(_float(row.get("volume")) or 0),
        }
        for row in reversed(rows)
        if isinstance(row, dict) and _float(row.get("adjusted_close") or row.get("close")) is not None
    ]


def parse_eodhd_fundamentals(payload: object, source_url: str = "", retrieved_at: str = "") -> dict[str, ProviderMetric]:
    data = payload if isinstance(payload, dict) else {}
    highlights = data.get("Highlights", {}) if isinstance(data.get("Highlights", {}), dict) else {}
    valuation = data.get("Valuation", {}) if isinstance(data.get("Valuation", {}), dict) else {}
    shares = data.get("SharesStats", {}) if isinstance(data.get("SharesStats", {}), dict) else {}
    financials = data.get("Financials", {}) if isinstance(data.get("Financials", {}), dict) else {}
    income = _latest_statement(financials, "Income_Statement")
    balance = _latest_statement(financials, "Balance_Sheet")
    cashflow = _latest_statement(financials, "Cash_Flow")
    ocf = _float(cashflow.get("totalCashFromOperatingActivities"))
    capex = _float(cashflow.get("capitalExpenditures"))
    fcf = ocf + capex if ocf is not None and capex is not None else None
    period = str(income.get("date", "") or cashflow.get("date", ""))
    return {
        "latest_price": _metric(highlights.get("PreviousClose"), source_url, retrieved_at),
        "market_cap": _metric(highlights.get("MarketCapitalization"), source_url, retrieved_at),
        "enterprise_value": _metric(valuation.get("EnterpriseValue"), source_url, retrieved_at),
        "revenue": _metric(income.get("totalRevenue"), source_url, retrieved_at, period),
        "ebitda": _metric(income.get("ebitda"), source_url, retrieved_at, period),
        "net_income": _metric(income.get("netIncome"), source_url, retrieved_at, period),
        "cash_and_equivalents": _metric(balance.get("cash"), source_url, retrieved_at, period),
        "total_debt": _metric(balance.get("shortLongTermDebtTotal"), source_url, retrieved_at, period),
        "operating_cash_flow": _metric(ocf, source_url, retrieved_at, period),
        "capital_expenditure": _metric(capex, source_url, retrieved_at, period),
        "free_cash_flow": _metric(fcf, source_url, retrieved_at, period, "derived_calculation"),
        "shares_outstanding": _metric(shares.get("SharesOutstanding"), source_url, retrieved_at, period),
        "diluted_eps": _metric(highlights.get("DilutedEpsTTM"), source_url, retrieved_at, period),
        "pe_ratio": _metric(highlights.get("PERatio"), source_url, retrieved_at),
    }


def _latest_statement(financials: dict[str, Any], statement_name: str) -> dict[str, Any]:
    statement = financials.get(statement_name, {})
    yearly = statement.get("yearly", {}) if isinstance(statement, dict) else {}
    if isinstance(yearly, dict) and yearly:
        key = sorted(yearly)[-1]
        row = yearly.get(key, {})
        if isinstance(row, dict):
            row = dict(row)
            row.setdefault("date", key)
            return row
    return {}


def _metric(
    value: object,
    source_url: str,
    retrieved_at: str,
    fiscal_period: str = "",
    data_type: str = "actual",
) -> ProviderMetric:
    return ProviderMetric(
        value=_float(value) if _looks_number(value) else value,
        source_name="EODHD",
        source_url=source_url,
        provider="EODHD",
        retrieved_at=retrieved_at,
        fiscal_period=fiscal_period,
        data_type=data_type,
        confidence="medium",
        note="Structured financial data from EODHD; not yet verified against SEC EDGAR.",
    )


def _url(path: str, api_key: str, extra: dict[str, str] | None = None) -> str:
    params = {"api_token": api_key}
    if extra:
        params.update(extra)
    return f"{EODHD_BASE_URL}{path}?{urlencode(params)}"


def _get_json(url: str) -> object:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


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
