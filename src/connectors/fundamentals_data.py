"""Structured fundamentals connector router helpers."""

from __future__ import annotations

from src.connectors.eodhd_data import fetch_eodhd_market_bundle
from src.connectors.fmp_data import fetch_fmp_financials
from src.connectors.sec_edgar import SecFinancialsResult
from src.connectors.yahooquery_data import fetch_yahooquery_financials
from src.connectors.yfinance_data import fetch_yfinance_financials
from src.data.models import ProviderMetric


def normalize_sec_metrics(sec: SecFinancialsResult) -> dict[str, ProviderMetric]:
    """Convert SEC connector metrics to provider metrics."""

    output: dict[str, ProviderMetric] = {}
    for name, item in sec.metrics.items():
        if item.get("value") is None:
            continue
        output[name] = ProviderMetric(
            value=item.get("value"),
            source_name="SEC EDGAR",
            source_url=sec.source_url,
            provider="SEC",
            retrieved_at=sec.retrieved_at,
            fiscal_period=str(item.get("period", "")),
            data_type=str(item.get("classification", "actual")),
            confidence="high",
            note="Official SEC EDGAR company facts / XBRL data.",
        )
    return output


def fetch_fundamentals_with_fallbacks(
    ticker: str,
    sec: SecFinancialsResult,
    fmp_api_key: str = "",
    eodhd_api_key: str = "",
) -> tuple[dict[str, ProviderMetric], tuple[str, ...]]:
    """Use SEC first, then yfinance, yahooquery, and optional premium fallbacks."""

    warnings: list[str] = []
    metrics = normalize_sec_metrics(sec)
    if sec.warning:
        warnings.append(sec.warning)

    yfinance_metrics = fetch_yfinance_financials(ticker)
    for key, metric in yfinance_metrics.items():
        if key not in metrics and metric.value is not None:
            metrics[key] = metric
    if not yfinance_metrics:
        warnings.append("Unavailable: yfinance financials returned no usable fields or package is not installed.")

    yahooquery_metrics = fetch_yahooquery_financials(ticker)
    for key, metric in yahooquery_metrics.items():
        if key not in metrics and metric.value is not None:
            metrics[key] = metric
    if not yahooquery_metrics:
        warnings.append("Unavailable: yahooquery financials returned no usable fields or package is not installed.")

    fmp_metrics = fetch_fmp_financials(ticker, fmp_api_key) if fmp_api_key else {}
    for key, metric in fmp_metrics.items():
        if key not in metrics and metric.value is not None:
            metrics[key] = metric

    if eodhd_api_key:
        eodhd_bundle = fetch_eodhd_market_bundle(ticker, eodhd_api_key)
        eodhd_metrics = eodhd_bundle.get("fundamentals", {})
        if isinstance(eodhd_metrics, dict):
            for key, metric in eodhd_metrics.items():
                if key not in metrics and getattr(metric, "value", None) is not None:
                    metrics[key] = metric

    return metrics, tuple(warnings)
