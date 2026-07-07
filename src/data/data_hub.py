"""Canonical data hub facade for live research data collection."""

from __future__ import annotations

from src.config import AppConfig
from src.data.models import CompanyResearchDataset, DataPoint
from src.data.provider_router import ProviderDataBundle, collect_provider_data as _collect_provider_data


def collect_provider_data(
    ticker: str,
    config: AppConfig,
    use_source_cache: bool = False,
) -> ProviderDataBundle:
    """Collect live data and optional AnySearch source-cache evidence."""

    return _collect_provider_data(ticker, config, use_source_cache=use_source_cache)


def build_company_research_dataset(
    ticker: str,
    config: AppConfig,
    company_name: str = "",
    use_source_cache: bool = False,
) -> CompanyResearchDataset:
    """Build the clean dataset object consumed by research/report layers."""

    bundle = collect_provider_data(ticker, config, use_source_cache=use_source_cache)
    valuation = _valuation_datapoints(bundle)
    warnings = tuple(warning for warning in bundle.warnings if warning)
    return CompanyResearchDataset(
        ticker=ticker.upper(),
        company_name=company_name or ticker.upper(),
        market_data=_market_datapoints(bundle),
        financials=_financial_datapoints(bundle),
        valuation=valuation,
        macro=_macro_datapoints(bundle),
        news=bundle.news + bundle.anysearch,
        tracker=(),
        provider_status=bundle.statuses,
        warnings=warnings,
        data_quality_score=_data_quality_score(bundle, valuation),
    )


def _market_datapoints(bundle: ProviderDataBundle) -> dict[str, DataPoint]:
    market = bundle.market
    fields = {
        "latest_price": market.latest_price,
        "previous_close": market.previous_close,
        "open": market.open,
        "high": market.high,
        "low": market.low,
        "volume": market.volume,
        "market_cap": market.market_cap,
        "moving_average_20": market.moving_average_20,
        "moving_average_50": market.moving_average_50,
        "moving_average_100": market.moving_average_100,
        "moving_average_200": market.moving_average_200,
    }
    return {
        key: _datapoint(
            value,
            source_name=market.source_name,
            provider=market.source_name,
            source_url=market.source_url,
            retrieved_at=market.retrieved_at,
            as_of_date=market.price_timestamp,
            data_type="actual" if value is not None else "unavailable",
            confidence="medium" if value is not None else "low",
            warning=market.warning if value is None else "",
        )
        for key, value in fields.items()
    }


def _financial_datapoints(bundle: ProviderDataBundle) -> dict[str, DataPoint]:
    output: dict[str, DataPoint] = {}
    for name, metric in bundle.financial_metrics.items():
        output[name] = _datapoint(
            metric.value,
            source_name=metric.source_name,
            provider=metric.provider,
            source_url=metric.source_url,
            retrieved_at=metric.retrieved_at,
            fiscal_period=metric.fiscal_period,
            period=getattr(metric, "period", None),
            data_type=metric.data_type if metric.data_type in {"actual", "estimated", "model_generated", "unavailable", "fallback"} else "actual",
            confidence=metric.confidence if metric.confidence in {"high", "medium", "low"} else "medium",
            warning=metric.note,
        )
    required = (
        "revenue",
        "gross_profit",
        "operating_income",
        "ebitda",
        "net_income",
        "diluted_eps",
        "cash_and_equivalents",
        "total_debt",
        "operating_cash_flow",
        "capital_expenditure",
        "free_cash_flow",
        "shares_outstanding",
    )
    for name in required:
        output.setdefault(name, _unavailable_datapoint("Financial field unavailable after SEC, yfinance, yahooquery, and optional FMP attempts."))
    return output


def _macro_datapoints(bundle: ProviderDataBundle) -> dict[str, DataPoint]:
    output: dict[str, DataPoint] = {}
    for item in bundle.macro:
        output[item.name] = _datapoint(
            item.latest_value,
            source_name=item.source,
            provider=item.source,
            source_url="https://fred.stlouisfed.org/",
            retrieved_at=item.date,
            as_of_date=item.date,
            data_type="actual" if item.latest_value is not None else "unavailable",
            confidence="high" if item.latest_value is not None else "low",
            warning=item.warning,
        )
    return output


def _valuation_datapoints(bundle: ProviderDataBundle) -> dict[str, DataPoint]:
    market = bundle.market
    financials = bundle.financial_metrics
    market_cap = market.market_cap
    revenue = _metric_number(financials, "revenue")
    ebitda = _metric_number(financials, "ebitda")
    net_income = _metric_number(financials, "net_income")
    free_cash_flow = _metric_number(financials, "free_cash_flow")
    cash = _metric_number(financials, "cash_and_equivalents")
    debt = _metric_number(financials, "total_debt")
    ev = market_cap + debt - cash if None not in (market_cap, debt, cash) else None
    return {
        "market_cap": _valuation_point(market_cap, market, "Market cap unavailable from current market provider."),
        "enterprise_value": _valuation_point(ev, market, "Enterprise value unavailable: market cap, debt, or cash missing."),
        "ev_sales": _ratio_point(ev, revenue, "EV/Sales unavailable: enterprise value or revenue missing.", market),
        "ev_ebitda": _ratio_point(ev, ebitda, "EV/EBITDA unavailable: enterprise value or EBITDA missing.", market),
        "pe": _ratio_point(market_cap, net_income, "P/E unavailable: market cap or net income missing.", market),
        "p_fcf": _ratio_point(market_cap, free_cash_flow, "P/FCF unavailable: market cap or free cash flow missing.", market),
        "p_sales": _ratio_point(market_cap, revenue, "P/S unavailable: market cap or revenue missing.", market),
    }


def _ratio_point(numerator: float | None, denominator: float | None, warning: str, market: object) -> DataPoint:
    value = numerator / denominator if numerator is not None and denominator not in (None, 0) else None
    return _valuation_point(value, market, warning)


def _valuation_point(value: float | None, market: object, warning: str) -> DataPoint:
    return _datapoint(
        value,
        source_name="Internal calculation",
        provider="valuation",
        source_url=getattr(market, "source_url", ""),
        retrieved_at=getattr(market, "retrieved_at", ""),
        data_type="model_generated" if value is not None else "unavailable",
        confidence="medium" if value is not None else "low",
        warning="" if value is not None else warning,
    )


def _datapoint(
    value: object,
    source_name: str,
    provider: str,
    source_url: str,
    retrieved_at: str,
    as_of_date: str = "",
    fiscal_period: str = "",
    period: object = None,
    data_type: str = "actual",
    confidence: str = "medium",
    warning: str = "",
) -> DataPoint:
    return DataPoint(
        value=value,
        source_name=source_name,
        provider=provider,
        source_url=source_url,
        retrieved_at=retrieved_at,
        as_of_date=as_of_date,
        fiscal_period=fiscal_period,
        period=period,
        data_type=data_type,
        confidence=confidence,
        warning=warning,
    )


def _unavailable_datapoint(warning: str) -> DataPoint:
    return _datapoint(
        None,
        source_name="Not available from current sources",
        provider="unavailable",
        source_url="",
        retrieved_at="",
        data_type="unavailable",
        confidence="low",
        warning=warning,
    )


def _metric_number(metrics: dict[str, object], key: str) -> float | None:
    metric = metrics.get(key)
    value = getattr(metric, "value", None)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _data_quality_score(bundle: ProviderDataBundle, valuation: dict[str, DataPoint]) -> float:
    total = 0
    available = 0
    for collection in (_market_datapoints(bundle), _financial_datapoints(bundle), _macro_datapoints(bundle), valuation):
        for point in collection.values():
            total += 1
            if point.value is not None:
                available += 1
    return 100.0 if total == 0 else round((available / total) * 100, 1)


__all__ = ["CompanyResearchDataset", "DataPoint", "ProviderDataBundle", "build_company_research_dataset", "collect_provider_data"]
