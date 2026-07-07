"""yahooquery connector fallback for no-key market and financial data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import importlib.util

from src.data.models import ProviderMetric


YAHOOQUERY_SOURCE_URL = "https://pypi.org/project/yahooquery/"


def is_yahooquery_installed() -> bool:
    """Return whether yahooquery is importable in the current Python runtime."""

    return importlib.util.find_spec("yahooquery") is not None


def fetch_yahooquery_market_data(ticker: str, retrieved_at: str | None = None):
    """Fetch yahooquery market data and map it to MarketDataResult."""

    from src.connectors.market_data import (
        MarketDataResult,
        _divergence,
        _float,
        _moving_average,
        unavailable_market_data,
    )

    now = retrieved_at or datetime.now(UTC).isoformat()
    try:
        from yahooquery import Ticker  # type: ignore
    except ImportError:
        return unavailable_market_data(ticker, "Unavailable: yahooquery is not installed.", now)

    try:
        yq_ticker = Ticker(ticker.upper())
        history_frame = yq_ticker.history(period="1y", interval="1d")
        summary = _ticker_payload(getattr(yq_ticker, "summary_detail", {}), ticker)
        price = _ticker_payload(getattr(yq_ticker, "price", {}), ticker)
    except Exception as exc:  # pragma: no cover - defensive against provider behavior
        return unavailable_market_data(ticker, f"Unavailable: yahooquery request failed: {exc}", now)

    history = _history_frame_to_records(history_frame, ticker)
    if not history:
        return unavailable_market_data(ticker, "Unavailable: yahooquery returned no usable price history.", now)
    latest = history[0]
    previous = history[1] if len(history) > 1 else {}
    closes = [float(day["close"]) for day in history if day.get("close") is not None]
    latest_price = _float(price.get("regularMarketPrice")) or _float(latest.get("close"))
    ma20 = _moving_average(closes, 20)
    ma50 = _moving_average(closes, 50)
    ma100 = _moving_average(closes, 100)
    ma200 = _moving_average(closes, 200)
    return MarketDataResult(
        ticker=ticker.upper(),
        latest_price=latest_price,
        price_timestamp=str(latest.get("date", "")),
        previous_close=_float(summary.get("previousClose")) or _float(previous.get("close")),
        open=_float(latest.get("open")),
        high=_float(latest.get("high")),
        low=_float(latest.get("low")),
        volume=int(_float(latest.get("volume")) or 0),
        market_cap=_float(price.get("marketCap")),
        daily_historical_prices=tuple(history),
        moving_average_20=ma20,
        moving_average_50=ma50,
        moving_average_100=ma100,
        moving_average_200=ma200,
        price_divergence_from_moving_averages={
            "20dma": _divergence(latest_price, ma20),
            "50dma": _divergence(latest_price, ma50),
            "100dma": _divergence(latest_price, ma100),
            "200dma": _divergence(latest_price, ma200),
        },
        relative_performance_vs_benchmark=None,
        source_name="yahooquery",
        source_url=YAHOOQUERY_SOURCE_URL,
        retrieved_at=now,
        warning="Fallback: latest available daily close used from yahooquery.",
        latest_available_label="latest available close",
    )


def fetch_yahooquery_financials(ticker: str) -> dict[str, ProviderMetric]:
    """Fetch yahooquery financial fields where available."""

    retrieved_at = datetime.now(UTC).isoformat()
    try:
        from yahooquery import Ticker  # type: ignore
    except ImportError:
        return {}
    try:
        yq_ticker = Ticker(ticker.upper())
        financial_data = _ticker_payload(getattr(yq_ticker, "financial_data", {}), ticker)
        key_stats = _ticker_payload(getattr(yq_ticker, "key_stats", {}), ticker)
        cash_flow = getattr(yq_ticker, "cash_flow", trailing=False)
        income_statement = getattr(yq_ticker, "income_statement", trailing=False)
        balance_sheet = getattr(yq_ticker, "balance_sheet", trailing=False)
    except Exception:
        return {}

    metrics: dict[str, ProviderMetric] = {}
    _add(metrics, "revenue", _statement_value(income_statement, "TotalRevenue"), retrieved_at)
    _add(metrics, "gross_profit", _statement_value(income_statement, "GrossProfit"), retrieved_at)
    _add(metrics, "operating_income", _statement_value(income_statement, "OperatingIncome"), retrieved_at)
    _add(metrics, "ebitda", financial_data.get("ebitda"), retrieved_at)
    _add(metrics, "net_income", _statement_value(income_statement, "NetIncome"), retrieved_at)
    _add(metrics, "cash_and_equivalents", _statement_value(balance_sheet, "CashAndCashEquivalents"), retrieved_at)
    _add(metrics, "total_debt", financial_data.get("totalDebt") or _statement_value(balance_sheet, "TotalDebt"), retrieved_at)
    _add(metrics, "operating_cash_flow", _statement_value(cash_flow, "OperatingCashFlow"), retrieved_at)
    capex = _statement_value(cash_flow, "CapitalExpenditure")
    _add(metrics, "capital_expenditure", capex, retrieved_at)
    ocf = metrics.get("operating_cash_flow")
    if ocf and ocf.value is not None and capex is not None:
        _add(metrics, "free_cash_flow", float(ocf.value) + float(capex), retrieved_at)
    _add(metrics, "shares_outstanding", key_stats.get("sharesOutstanding"), retrieved_at)
    _add(metrics, "diluted_eps", key_stats.get("trailingEps"), retrieved_at)
    return metrics


def _ticker_payload(payload: object, ticker: str) -> dict[str, Any]:
    if isinstance(payload, dict):
        value = payload.get(ticker.upper()) or payload.get(ticker.lower()) or payload
        return value if isinstance(value, dict) else {}
    return {}


def _history_frame_to_records(frame: Any, ticker: str) -> list[dict[str, float | int | str]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    data = frame
    try:
        if "symbol" in data.columns:
            data = data[data["symbol"].str.upper() == ticker.upper()]
        data = data.sort_index(ascending=False)
    except Exception:
        pass
    records: list[dict[str, float | int | str]] = []
    for index, row in data.iterrows():
        date = row.get("date") if hasattr(row, "get") else ""
        if not date and isinstance(index, tuple):
            date = index[-1]
        elif not date:
            date = index
        records.append(
            {
                "date": str(date),
                "open": _safe_float(row.get("open")),
                "high": _safe_float(row.get("high")),
                "low": _safe_float(row.get("low")),
                "close": _safe_float(row.get("close")),
                "volume": int(_safe_float(row.get("volume")) or 0),
            }
        )
    return records


def _statement_value(frame: Any, field: str) -> float | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        sorted_frame = frame.sort_values(by="asOfDate", ascending=False) if "asOfDate" in frame.columns else frame
        if field not in sorted_frame.columns:
            return None
        series = sorted_frame[field].dropna()
        if series.empty:
            return None
        return _safe_float(series.iloc[0])
    except Exception:
        return None


def _add(metrics: dict[str, ProviderMetric], name: str, value: object, retrieved_at: str) -> None:
    amount = _safe_float(value)
    if amount is None:
        return
    metrics[name] = ProviderMetric(
        value=amount,
        source_name="yahooquery",
        source_url=YAHOOQUERY_SOURCE_URL,
        provider="yahooquery",
        retrieved_at=retrieved_at,
        data_type="fallback",
        confidence="medium",
        note="Fallback financial field from yahooquery.",
    )


def _safe_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
