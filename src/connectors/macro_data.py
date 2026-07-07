"""Official macro-data connector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import csv
import json


UNAVAILABLE = "Not available from current sources"


@dataclass(frozen=True)
class MacroIndicator:
    name: str
    latest_value: float | None
    previous_value: float | None
    date: str
    trend_direction: str
    source: str
    frequency: str
    relevance: str
    warning: str = ""
    historical_average: float | None = None
    historical_comparison: str = "Historical comparison unavailable"


def fetch_macro_indicators(fred_api_key: str = "") -> tuple[MacroIndicator, ...]:
    """Fetch selected macro indicators from FRED public CSV first, then API."""

    specs = (
        ("US 10-year treasury yield", "DGS10", "daily", "Higher rates may pressure AI and tech valuation multiples."),
        ("Federal funds rate", "FEDFUNDS", "monthly", "Policy rates affect discount rates and risk appetite."),
        ("CPI", "CPIAUCSL", "monthly", "Inflation affects rate expectations and valuation multiples."),
        ("PCE", "PCEPI", "monthly", "PCE is a Fed-relevant inflation measure."),
        ("Unemployment rate", "UNRATE", "monthly", "Labor conditions affect macro risk and demand expectations."),
    )
    indicators = tuple(_fetch_fred_csv_series(name, series_id, freq, relevance) for name, series_id, freq, relevance in specs)
    if fred_api_key and any(item.latest_value is None for item in indicators):
        api_indicators = tuple(_fetch_fred_series(name, series_id, freq, relevance, fred_api_key) for name, series_id, freq, relevance in specs)
        return tuple(api if csv_item.latest_value is None else csv_item for csv_item, api in zip(indicators, api_indicators))
    return indicators


def _fetch_fred_series(
    name: str,
    series_id: str,
    frequency: str,
    relevance: str,
    api_key: str,
) -> MacroIndicator:
    params = urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 2,
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"
    try:
        payload = _get_json(url)
    except OSError as exc:
        return MacroIndicator(name, None, None, UNAVAILABLE, "unknown", "FRED", frequency, relevance, f"FRED request failed: {exc}")
    observations = [obs for obs in payload.get("observations", []) if obs.get("value") not in (None, ".")]
    latest = observations[0] if observations else {}
    previous = observations[1] if len(observations) > 1 else {}
    latest_value = _float(latest.get("value"))
    previous_value = _float(previous.get("value"))
    historical_average = _recent_average_from_observations(observations, frequency)
    return MacroIndicator(
        name=name,
        latest_value=latest_value,
        previous_value=previous_value,
        date=str(latest.get("date", UNAVAILABLE)),
        trend_direction=_trend(latest_value, previous_value),
        source="FRED",
        frequency=frequency,
        relevance=relevance,
        historical_average=historical_average,
        historical_comparison=_historical_comparison(latest_value, historical_average),
    )


def _fetch_fred_csv_series(
    name: str,
    series_id: str,
    frequency: str,
    relevance: str,
) -> MacroIndicator:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        text = _get_text(url)
    except OSError as exc:
        return MacroIndicator(
            name,
            None,
            None,
            UNAVAILABLE,
            "unknown",
            "FRED public CSV",
            frequency,
            relevance,
            f"FRED_API_KEY is missing and FRED public CSV fallback failed: {exc}",
        )

    rows = [
        row
        for row in csv.DictReader(StringIO(text))
        if row.get(series_id) not in (None, "", ".")
    ]
    if not rows:
        return MacroIndicator(
            name,
            None,
            None,
            UNAVAILABLE,
            "unknown",
            "FRED public CSV",
            frequency,
            relevance,
            "FRED_API_KEY is missing and FRED public CSV fallback returned no usable values.",
        )
    latest = rows[-1]
    previous = rows[-2] if len(rows) > 1 else {}
    latest_value = _float(latest.get(series_id))
    previous_value = _float(previous.get(series_id))
    historical_average = _recent_average_from_rows(rows, series_id, frequency)
    return MacroIndicator(
        name=name,
        latest_value=latest_value,
        previous_value=previous_value,
        date=str(latest.get("observation_date", UNAVAILABLE)),
        trend_direction=_trend(latest_value, previous_value),
        source="FRED public CSV",
        frequency=frequency,
        relevance=relevance,
        warning="FRED_API_KEY is missing; using latest available FRED public CSV data.",
        historical_average=historical_average,
        historical_comparison=_historical_comparison(latest_value, historical_average),
    )


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


def _trend(latest: float | None, previous: float | None) -> str:
    if latest is None or previous is None:
        return "unknown"
    if latest > previous:
        return "up"
    if latest < previous:
        return "down"
    return "flat"


def _recent_average_from_rows(rows: list[dict[str, str]], series_id: str, frequency: str) -> float | None:
    values = [_float(row.get(series_id)) for row in rows[-_history_window(frequency):]]
    return _average([value for value in values if value is not None])


def _recent_average_from_observations(observations: list[dict[str, Any]], frequency: str) -> float | None:
    values = [_float(observation.get("value")) for observation in observations[:_history_window(frequency)]]
    return _average([value for value in values if value is not None])


def _history_window(frequency: str) -> int:
    return 252 if frequency == "daily" else 60


def _average(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    return sum(values) / len(values)


def _historical_comparison(latest: float | None, historical_average: float | None) -> str:
    if latest is None or historical_average in (None, 0):
        return "Historical comparison unavailable"
    difference = latest / historical_average - 1
    if abs(difference) < 0.01:
        return "near recent average"
    direction = "above" if difference > 0 else "below"
    return f"{direction} recent average by {abs(difference):.1%}"
