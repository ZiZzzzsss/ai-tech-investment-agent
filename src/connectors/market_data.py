"""Structured market-data connector.

Live reports should use this connector, not web snippets or news, for price,
OHLCV, volume, moving averages, and technical indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import csv
import json

from src.connectors.yahooquery_data import fetch_yahooquery_market_data
from src.connectors.yfinance_data import fetch_yfinance_market_data


UNAVAILABLE = "Not available from current sources"


@dataclass(frozen=True)
class MarketDataResult:
    ticker: str
    latest_price: float | None
    price_timestamp: str
    previous_close: float | None
    open: float | None
    high: float | None
    low: float | None
    volume: int | None
    market_cap: float | None
    daily_historical_prices: tuple[dict[str, float | int | str], ...]
    moving_average_20: float | None
    moving_average_50: float | None
    moving_average_100: float | None
    moving_average_200: float | None
    price_divergence_from_moving_averages: dict[str, float | None]
    relative_performance_vs_benchmark: float | None
    source_name: str
    source_url: str
    retrieved_at: str
    warning: str = ""
    latest_available_label: str = "latest available"


def fetch_market_data(
    ticker: str,
    alpha_vantage_api_key: str = "",
    fmp_api_key: str = "",
    eodhd_api_key: str = "",
    polygon_api_key: str = "",
    tiingo_api_key: str = "",
) -> MarketDataResult:
    """Fetch market data in approved provider order.

    Free/no-key providers are tried first. FMP is an optional premium upgrade
    and a missing FMP key is not treated as a blocking live-data error.
    """

    retrieved_at = datetime.now(UTC).isoformat()
    warnings: list[str] = []

    yfinance = fetch_yfinance_market_data(ticker, retrieved_at)
    if yfinance.latest_price is not None:
        return yfinance
    warnings.append(yfinance.warning)

    yahooquery = fetch_yahooquery_market_data(ticker, retrieved_at)
    if yahooquery.latest_price is not None:
        return yahooquery
    warnings.append(yahooquery.warning)

    if fmp_api_key:
        fmp = fetch_fmp_market_data(ticker, fmp_api_key, retrieved_at)
        if fmp.latest_price is not None:
            return fmp
        warnings.append(fmp.warning)
    elif fmp_api_key == "__diagnostic_missing__":
        warnings.append("Optional premium provider unavailable: FMP_API_KEY missing.")

    if eodhd_api_key:
        eodhd = fetch_eodhd_market_data(ticker, eodhd_api_key, retrieved_at)
        if eodhd.latest_price is not None:
            return eodhd
        warnings.append(eodhd.warning)

    if polygon_api_key:
        polygon = fetch_polygon_market_data(ticker, polygon_api_key, retrieved_at)
        if polygon.latest_price is not None:
            return polygon
        warnings.append(polygon.warning)

    if tiingo_api_key:
        tiingo = fetch_tiingo_market_data(ticker, tiingo_api_key, retrieved_at)
        if tiingo.latest_price is not None:
            return tiingo
        warnings.append(tiingo.warning)

    if alpha_vantage_api_key:
        alpha = fetch_alpha_vantage_market_data(ticker, alpha_vantage_api_key, retrieved_at)
        if alpha.latest_price is not None:
            return alpha
        warnings.append(alpha.warning)

    return unavailable_market_data(ticker, "; ".join(warnings), retrieved_at)


def fetch_alpha_vantage_market_data(
    ticker: str,
    alpha_vantage_api_key: str,
    retrieved_at: str | None = None,
) -> MarketDataResult:
    """Fetch latest available daily market data from Alpha Vantage."""

    now = retrieved_at or datetime.now(UTC).isoformat()
    params = urlencode(
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker.upper(),
            "outputsize": "compact",
            "apikey": alpha_vantage_api_key,
        }
    )
    url = f"https://www.alphavantage.co/query?{params}"
    try:
        payload = _get_json(url)
    except OSError as exc:
        return unavailable_market_data(ticker, f"Unavailable: Alpha Vantage request failed: {exc}", now, source_url=url)

    series = payload.get("Time Series (Daily)", {})
    if not isinstance(series, dict) or not series:
        note = payload.get("Note") or payload.get("Error Message") or UNAVAILABLE
        return unavailable_market_data(ticker, f"Unavailable: Alpha Vantage returned no usable daily series: {note}", now, source_url=url)

    history = []
    for day, values in sorted(series.items(), reverse=True):
        if not isinstance(values, dict):
            continue
        history.append(
            {
                "date": day,
                "open": _float(values.get("1. open")),
                "high": _float(values.get("2. high")),
                "low": _float(values.get("3. low")),
                "close": _float(values.get("4. close")),
                "volume": int(_float(values.get("6. volume")) or 0),
            }
        )
    latest = history[0]
    previous = history[1] if len(history) > 1 else {}
    closes = [float(day["close"]) for day in history if day.get("close") is not None]
    ma20 = _moving_average(closes, 20)
    ma50 = _moving_average(closes, 50)
    ma100 = _moving_average(closes, 100)
    ma200 = _moving_average(closes, 200)
    latest_price = float(latest["close"]) if latest.get("close") is not None else None
    return MarketDataResult(
        ticker=ticker.upper(),
        latest_price=latest_price,
        price_timestamp=str(latest["date"]),
        previous_close=_float(previous.get("close")),
        open=_float(latest.get("open")),
        high=_float(latest.get("high")),
        low=_float(latest.get("low")),
        volume=int(latest.get("volume") or 0),
        market_cap=None,
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
        source_name="Alpha Vantage",
        source_url=url,
        retrieved_at=now,
        warning="Fallback: latest available daily close used.",
        latest_available_label="latest available close",
    )


def fetch_fmp_market_data(
    ticker: str,
    fmp_api_key: str,
    retrieved_at: str | None = None,
) -> MarketDataResult:
    """Fetch latest available daily market data from Financial Modeling Prep."""

    now = retrieved_at or datetime.now(UTC).isoformat()
    quote_url = f"https://financialmodelingprep.com/api/v3/quote/{ticker.upper()}?{urlencode({'apikey': fmp_api_key})}"
    history_url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker.upper()}?{urlencode({'apikey': fmp_api_key})}"
    try:
        quote_payload = _get_json(quote_url)
        history_payload = _get_json(history_url)
    except OSError as exc:
        return unavailable_market_data(ticker, f"Unavailable: FMP request failed: {exc}", now, source_url=quote_url)
    quote = _first_payload_row(quote_payload)
    rows = history_payload.get("historical", []) if isinstance(history_payload, dict) else []
    history = [
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
    if not history:
        return unavailable_market_data(ticker, "Unavailable: FMP returned no usable daily prices.", now, source_url=history_url)
    result = _market_result_from_history(
        ticker,
        history,
        "Financial Modeling Prep",
        history_url,
        now,
        "Fallback: latest available daily close used.",
        "latest available close",
        market_cap=_float(quote.get("marketCap")),
    )
    quote_price = _float(quote.get("price"))
    if quote_price is None:
        return result
    return MarketDataResult(
        **{
            **result.__dict__,
            "latest_price": quote_price,
            "source_url": quote_url,
            "warning": "FMP quote used for latest price; historical daily prices used for moving averages.",
        }
    )


def fetch_eodhd_market_data(
    ticker: str,
    eodhd_api_key: str,
    retrieved_at: str | None = None,
) -> MarketDataResult:
    """Fetch latest available daily market data from EODHD."""

    now = retrieved_at or datetime.now(UTC).isoformat()
    symbol = f"{ticker.upper()}.US"
    params = urlencode({"api_token": eodhd_api_key, "fmt": "json", "period": "d"})
    url = f"https://eodhd.com/api/eod/{symbol}?{params}"
    try:
        payload = _get_json(url)
    except OSError as exc:
        return unavailable_market_data(ticker, f"Unavailable: EODHD request failed: {exc}", now, source_url=url)
    rows = payload if isinstance(payload, list) else []
    history = [
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
    if not history:
        return unavailable_market_data(ticker, "Unavailable: EODHD returned no usable daily prices.", now, source_url=url)
    return _market_result_from_history(
        ticker,
        history,
        "EODHD",
        url,
        now,
        "Fallback: latest available daily close used from EODHD.",
        "latest available close",
    )


def fetch_polygon_market_data(
    ticker: str,
    polygon_api_key: str,
    retrieved_at: str | None = None,
) -> MarketDataResult:
    """Fetch latest available daily market data from Polygon aggregates."""

    now_dt = datetime.now(UTC)
    now = retrieved_at or now_dt.isoformat()
    start = (now_dt - timedelta(days=430)).date().isoformat()
    end = now_dt.date().isoformat()
    params = urlencode({"adjusted": "true", "sort": "desc", "limit": "260", "apiKey": polygon_api_key})
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/1/day/{start}/{end}?{params}"
    try:
        payload = _get_json(url)
    except OSError as exc:
        return unavailable_market_data(ticker, f"Unavailable: Polygon request failed: {exc}", now, source_url=url)
    rows = payload.get("results", []) if isinstance(payload, dict) else []
    history = [
        {
            "date": datetime.fromtimestamp(int(row.get("t", 0)) / 1000, UTC).date().isoformat(),
            "open": _float(row.get("o")),
            "high": _float(row.get("h")),
            "low": _float(row.get("l")),
            "close": _float(row.get("c")),
            "volume": int(_float(row.get("v")) or 0),
        }
        for row in rows
        if isinstance(row, dict) and _float(row.get("c")) is not None
    ]
    if not history:
        message = payload.get("message", "Polygon returned no usable daily prices.") if isinstance(payload, dict) else "Polygon returned no usable daily prices."
        return unavailable_market_data(ticker, f"Unavailable: {message}", now, source_url=url)
    return _market_result_from_history(
        ticker,
        history,
        "Polygon",
        url,
        now,
        "Fallback: latest available daily close used.",
        "latest available close",
    )


def unavailable_market_data(
    ticker: str,
    warning: str,
    retrieved_at: str | None = None,
    source_url: str = "",
) -> MarketDataResult:
    now = retrieved_at or datetime.now(UTC).isoformat()
    return MarketDataResult(
        ticker=ticker.upper(),
        latest_price=None,
        price_timestamp=UNAVAILABLE,
        previous_close=None,
        open=None,
        high=None,
        low=None,
        volume=None,
        market_cap=None,
        daily_historical_prices=(),
        moving_average_20=None,
        moving_average_50=None,
        moving_average_100=None,
        moving_average_200=None,
        price_divergence_from_moving_averages={},
        relative_performance_vs_benchmark=None,
        source_name="Market data connector",
        source_url=source_url,
        retrieved_at=now,
        warning=warning,
    )


def fetch_tiingo_market_data(
    ticker: str,
    tiingo_api_key: str,
    retrieved_at: str | None = None,
) -> MarketDataResult:
    """Fetch latest available daily market data from Tiingo."""

    now = retrieved_at or datetime.now(UTC).isoformat()
    start = (datetime.now(UTC) - timedelta(days=430)).date().isoformat()
    url = f"https://api.tiingo.com/tiingo/daily/{ticker.lower()}/prices?{urlencode({'startDate': start, 'token': tiingo_api_key})}"
    try:
        payload = _get_json(url)
    except OSError as exc:
        return unavailable_market_data(ticker, f"Unavailable: Tiingo request failed: {exc}", now, source_url=url)
    rows = payload if isinstance(payload, list) else []
    history = [
        {
            "date": str(row.get("date", ""))[:10],
            "open": _float(row.get("adjOpen") or row.get("open")),
            "high": _float(row.get("adjHigh") or row.get("high")),
            "low": _float(row.get("adjLow") or row.get("low")),
            "close": _float(row.get("adjClose") or row.get("close")),
            "volume": int(_float(row.get("adjVolume") or row.get("volume")) or 0),
        }
        for row in reversed(rows)
        if isinstance(row, dict) and _float(row.get("adjClose") or row.get("close")) is not None
    ]
    if not history:
        return unavailable_market_data(ticker, "Unavailable: Tiingo returned no usable daily prices.", now, source_url=url)
    return _market_result_from_history(
        ticker,
        history,
        "Tiingo",
        url,
        now,
        "Fallback: latest available daily close used from Tiingo.",
        "latest available close",
    )


def fetch_stooq_daily_market_data(
    ticker: str,
    retrieved_at: str | None = None,
) -> MarketDataResult:
    """Fetch latest available daily OHLCV from Stooq CSV as a structured fallback."""

    now = retrieved_at or datetime.now(UTC).isoformat()
    text = ""
    source_url = ""
    errors = []
    for symbol in _stooq_symbols(ticker):
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        try:
            text = _get_text(url)
            source_url = url
            break
        except OSError as exc:
            errors.append(f"{symbol}: {exc}")
    if not text:
        return unavailable_market_data(
            ticker,
            "Unavailable: Stooq unsupported ticker or request failed: " + "; ".join(errors),
            now,
            source_url=f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d",
        )

    rows = [row for row in csv.DictReader(StringIO(text)) if row.get("Close") not in (None, "", "N/D")]
    if not rows:
        return unavailable_market_data(
            ticker,
            "Unavailable: Stooq fallback returned no usable rows.",
            now,
            source_url=source_url,
        )

    history = [
        {
            "date": row.get("Date", ""),
            "open": _float(row.get("Open")),
            "high": _float(row.get("High")),
            "low": _float(row.get("Low")),
            "close": _float(row.get("Close")),
            "volume": int(_float(row.get("Volume")) or 0),
        }
        for row in reversed(rows)
    ]
    latest = history[0]
    previous = history[1] if len(history) > 1 else {}
    closes = [float(day["close"]) for day in history if day.get("close") is not None]
    ma20 = _moving_average(closes, 20)
    ma50 = _moving_average(closes, 50)
    ma100 = _moving_average(closes, 100)
    ma200 = _moving_average(closes, 200)
    latest_price = _float(latest.get("close"))

    return MarketDataResult(
        ticker=ticker.upper(),
        latest_price=latest_price,
        price_timestamp=str(latest["date"]),
        previous_close=_float(previous.get("close")),
        open=_float(latest.get("open")),
        high=_float(latest.get("high")),
        low=_float(latest.get("low")),
        volume=int(latest.get("volume") or 0),
        market_cap=None,
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
        source_name="Stooq daily CSV",
        source_url=source_url,
        retrieved_at=now,
        warning="Fallback: latest available daily close used from Stooq.",
        latest_available_label="latest available close",
    )


def fetch_yahoo_chart_market_data(
    ticker: str,
    retrieved_at: str | None = None,
) -> MarketDataResult:
    """Fetch latest available daily OHLCV from Yahoo Finance chart JSON."""

    now = retrieved_at or datetime.now(UTC).isoformat()
    symbol = ticker.upper().replace(".", "-")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
    try:
        payload = _get_json(url)
    except OSError as exc:
        message = f"Unavailable: Yahoo fallback returned rate limit: {exc}" if "429" in str(exc) else f"Unavailable: Yahoo Finance chart fallback failed: {exc}"
        return unavailable_market_data(
            ticker,
            message,
            now,
            source_url=url,
        )

    chart = payload.get("chart", {}) if isinstance(payload, dict) else {}
    results = chart.get("result", []) if isinstance(chart, dict) else []
    if not results:
        return unavailable_market_data(
            ticker,
            "Unavailable: Yahoo Finance chart fallback returned no usable result.",
            now,
            source_url=url,
        )
    result = results[0]
    timestamps = result.get("timestamp", [])
    quote = (result.get("indicators", {}).get("quote", [{}]) or [{}])[0]
    meta = result.get("meta", {})
    history = []
    for idx, timestamp in enumerate(timestamps):
        close = _list_float(quote.get("close", []), idx)
        if close is None:
            continue
        history.append(
            {
                "date": datetime.fromtimestamp(int(timestamp), UTC).date().isoformat(),
                "open": _list_float(quote.get("open", []), idx),
                "high": _list_float(quote.get("high", []), idx),
                "low": _list_float(quote.get("low", []), idx),
                "close": close,
                "volume": int(_list_float(quote.get("volume", []), idx) or 0),
            }
        )
    history.reverse()
    if not history:
        return unavailable_market_data(
            ticker,
            "Unavailable: Yahoo Finance chart fallback returned no usable prices.",
            now,
            source_url=url,
        )

    latest = history[0]
    previous = history[1] if len(history) > 1 else {}
    closes = [float(day["close"]) for day in history if day.get("close") is not None]
    ma20 = _moving_average(closes, 20)
    ma50 = _moving_average(closes, 50)
    ma100 = _moving_average(closes, 100)
    ma200 = _moving_average(closes, 200)
    latest_price = _float(meta.get("regularMarketPrice")) or _float(latest.get("close"))

    return MarketDataResult(
        ticker=ticker.upper(),
        latest_price=latest_price,
        price_timestamp=str(latest["date"]),
        previous_close=_float(previous.get("close")),
        open=_float(latest.get("open")),
        high=_float(latest.get("high")),
        low=_float(latest.get("low")),
        volume=int(latest.get("volume") or 0),
        market_cap=_float(meta.get("marketCap")),
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
        source_name="Yahoo Finance chart API",
        source_url=url,
        retrieved_at=now,
        warning="Fallback: latest available daily close used from Yahoo Finance chart API.",
        latest_available_label="latest available close",
    )


def _market_result_from_history(
    ticker: str,
    history: list[dict[str, float | int | str]],
    source_name: str,
    source_url: str,
    retrieved_at: str,
    warning: str,
    latest_available_label: str,
    market_cap: float | None = None,
) -> MarketDataResult:
    latest = history[0]
    previous = history[1] if len(history) > 1 else {}
    closes = [float(day["close"]) for day in history if day.get("close") is not None]
    ma20 = _moving_average(closes, 20)
    ma50 = _moving_average(closes, 50)
    ma100 = _moving_average(closes, 100)
    ma200 = _moving_average(closes, 200)
    latest_price = _float(latest.get("close"))
    return MarketDataResult(
        ticker=ticker.upper(),
        latest_price=latest_price,
        price_timestamp=str(latest.get("date", UNAVAILABLE)),
        previous_close=_float(previous.get("close")),
        open=_float(latest.get("open")),
        high=_float(latest.get("high")),
        low=_float(latest.get("low")),
        volume=int(latest.get("volume") or 0),
        market_cap=market_cap,
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
        source_name=source_name,
        source_url=source_url,
        retrieved_at=retrieved_at,
        warning=warning,
        latest_available_label=latest_available_label,
    )


def _stooq_symbols(ticker: str) -> tuple[str, ...]:
    base = ticker.lower().replace("-", ".")
    if base.endswith(".us"):
        return (base,)
    return (f"{base}.us", base)


def _list_float(values: object, idx: int) -> float | None:
    if not isinstance(values, list) or idx >= len(values):
        return None
    return _float(values[idx])


def _first_payload_row(payload: object) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        return payload
    return {}


def _get_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str) -> str:
    with urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[:window]) / window


def _divergence(price: float | None, average: float | None) -> float | None:
    if price is None or average in (None, 0):
        return None
    return (price / average) - 1
