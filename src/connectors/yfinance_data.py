"""yfinance connector for free/no-key market and financial data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import importlib.util

from src.data.models import ProviderMetric


YFINANCE_SOURCE_URL = "https://pypi.org/project/yfinance/"


def is_yfinance_installed() -> bool:
    """Return whether yfinance is importable in the current Python runtime."""

    return importlib.util.find_spec("yfinance") is not None


def fetch_yfinance_market_data(ticker: str, retrieved_at: str | None = None):
    """Fetch yfinance market data and map it to MarketDataResult."""

    from src.connectors.market_data import (
        MarketDataResult,
        _divergence,
        _float,
        _moving_average,
        unavailable_market_data,
    )

    now = retrieved_at or datetime.now(UTC).isoformat()
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return unavailable_market_data(ticker, "Unavailable: yfinance is not installed.", now)

    try:
        yf_ticker = yf.Ticker(ticker.upper())
        history_frame = yf_ticker.history(period="1y", interval="1d", auto_adjust=False)
        info = getattr(yf_ticker, "fast_info", None) or getattr(yf_ticker, "info", {}) or {}
    except Exception as exc:  # pragma: no cover - defensive against provider behavior
        return unavailable_market_data(ticker, f"Unavailable: yfinance request failed: {exc}", now)

    history = _history_frame_to_records(history_frame)
    if not history:
        return unavailable_market_data(ticker, "Unavailable: yfinance returned no usable price history.", now)

    latest = history[0]
    previous = history[1] if len(history) > 1 else {}
    closes = [float(day["close"]) for day in history if day.get("close") is not None]
    latest_price = _float(_info_get(info, "last_price", "lastPrice")) or _float(latest.get("close"))
    ma20 = _moving_average(closes, 20)
    ma50 = _moving_average(closes, 50)
    ma100 = _moving_average(closes, 100)
    ma200 = _moving_average(closes, 200)
    return MarketDataResult(
        ticker=ticker.upper(),
        latest_price=latest_price,
        price_timestamp=str(latest.get("date", "")),
        previous_close=_float(_info_get(info, "previous_close", "previousClose")) or _float(previous.get("close")),
        open=_float(latest.get("open")),
        high=_float(latest.get("high")),
        low=_float(latest.get("low")),
        volume=int(_float(latest.get("volume")) or 0),
        market_cap=_float(_info_get(info, "market_cap", "marketCap")),
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
        source_name="yfinance",
        source_url=YFINANCE_SOURCE_URL,
        retrieved_at=now,
        warning="Fallback: latest available daily close used from yfinance.",
        latest_available_label="latest available close",
    )


def fetch_yfinance_financials(ticker: str) -> dict[str, ProviderMetric]:
    """Fetch yfinance financial statement fields where available."""

    retrieved_at = datetime.now(UTC).isoformat()
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return {}
    try:
        yf_ticker = yf.Ticker(ticker.upper())
        info = getattr(yf_ticker, "info", {}) or {}
        financials = getattr(yf_ticker, "financials", None)
        balance_sheet = getattr(yf_ticker, "balance_sheet", None)
        cashflow = getattr(yf_ticker, "cashflow", None)
    except Exception:
        return {}

    metrics: dict[str, ProviderMetric] = {}
    _add(metrics, "revenue", _frame_value(financials, "Total Revenue"), retrieved_at)
    _add(metrics, "gross_profit", _frame_value(financials, "Gross Profit"), retrieved_at)
    _add(metrics, "operating_income", _frame_value(financials, "Operating Income"), retrieved_at)
    _add(metrics, "ebitda", _frame_value(financials, "EBITDA"), retrieved_at)
    _add(metrics, "net_income", _frame_value(financials, "Net Income"), retrieved_at)
    _add(metrics, "cash_and_equivalents", _frame_value(balance_sheet, "Cash And Cash Equivalents"), retrieved_at)
    debt = _frame_value(balance_sheet, "Total Debt") or _frame_value(balance_sheet, "Long Term Debt")
    _add(metrics, "total_debt", debt, retrieved_at)
    _add(metrics, "operating_cash_flow", _frame_value(cashflow, "Operating Cash Flow"), retrieved_at)
    capex = _frame_value(cashflow, "Capital Expenditure")
    _add(metrics, "capital_expenditure", capex, retrieved_at)
    ocf = metrics.get("operating_cash_flow")
    if ocf and ocf.value is not None and capex is not None:
        _add(metrics, "free_cash_flow", float(ocf.value) + float(capex), retrieved_at)
    _add(metrics, "shares_outstanding", _info_get(info, "sharesOutstanding", "shares_outstanding"), retrieved_at)
    _add(metrics, "diluted_eps", _info_get(info, "trailingEps", "trailing_eps"), retrieved_at)
    return metrics


def _history_frame_to_records(frame: Any) -> list[dict[str, float | int | str]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    records: list[dict[str, float | int | str]] = []
    sorted_frame = frame.sort_index(ascending=False)
    for index, row in sorted_frame.iterrows():
        date = getattr(index, "date", lambda: index)()
        records.append(
            {
                "date": str(date),
                "open": _safe_float(row.get("Open")),
                "high": _safe_float(row.get("High")),
                "low": _safe_float(row.get("Low")),
                "close": _safe_float(row.get("Close")),
                "volume": int(_safe_float(row.get("Volume")) or 0),
            }
        )
    return records


def _frame_value(frame: Any, row_name: str) -> float | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        if row_name not in frame.index:
            return None
        series = frame.loc[row_name].dropna()
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
        source_name="yfinance",
        source_url=YFINANCE_SOURCE_URL,
        provider="yfinance",
        retrieved_at=retrieved_at,
        data_type="fallback",
        confidence="medium",
        note="Fallback financial field from yfinance.",
    )


def _info_get(info: object, *keys: str) -> object:
    for key in keys:
        try:
            value = info[key]  # type: ignore[index]
        except Exception:
            value = getattr(info, key, None)
        if value is not None:
            return value
    return None


def _safe_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
