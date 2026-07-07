"""SEC EDGAR connector for filings and company facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.request import Request, urlopen
import gzip
import json


UNAVAILABLE = "Not available from current sources"


@dataclass(frozen=True)
class FilingMetadata:
    form: str
    filing_date: str
    accession_number: str
    report_date: str = ""


@dataclass(frozen=True)
class SecFinancialsResult:
    ticker: str
    cik: str
    latest_10k: FilingMetadata | None
    latest_10q: FilingMetadata | None
    latest_8k: FilingMetadata | None
    metrics: dict[str, dict[str, str | float | None]]
    source_name: str
    source_url: str
    retrieved_at: str
    warning: str = ""
    metrics_history: dict[str, tuple[dict[str, str | float | None], ...]] = field(default_factory=dict)


def fetch_sec_financials(
    ticker: str,
    sec_user_agent: str = "",
    ticker_cik_map: dict[str, str] | None = None,
) -> SecFinancialsResult:
    """Fetch SEC submission metadata and selected XBRL company facts."""

    retrieved_at = datetime.now(UTC).isoformat()
    if not sec_user_agent:
        return unavailable_sec_financials(
            ticker,
            "SEC financial data unavailable because SEC_USER_AGENT is not configured. Add SEC_USER_AGENT=AIInvestmentResearchAgent/0.1 your-email@example.com to .env.",
            retrieved_at,
        )

    cik = (ticker_cik_map or DEFAULT_TICKER_CIK).get(ticker.upper(), "")
    if not cik:
        return unavailable_sec_financials(ticker, "Ticker to CIK mapping is unavailable.", retrieved_at)
    padded_cik = cik.zfill(10)
    submissions_url = f"https://data.sec.gov/submissions/CIK{padded_cik}.json"
    facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json"
    headers = {"User-Agent": sec_user_agent, "Accept-Encoding": "gzip, deflate"}

    try:
        submissions = _get_json(submissions_url, headers)
    except OSError as exc:
        return unavailable_sec_financials(ticker, f"SEC request failed: {exc}", retrieved_at)
    facts_warning = ""
    try:
        facts = _get_json(facts_url, headers)
    except OSError as exc:
        facts = {}
        facts_warning = f"SEC company facts unavailable while submissions worked: {exc}"

    recent = submissions.get("filings", {}).get("recent", {})
    latest_10k = _latest_form(recent, "10-K")
    latest_10q = _latest_form(recent, "10-Q")
    latest_8k = _latest_form(recent, "8-K")
    metrics = _extract_company_facts(facts)
    metrics_history = _extract_company_fact_histories(facts)
    missing_metrics = [name for name, value in metrics.items() if value.get("classification") == "unavailable"]
    return SecFinancialsResult(
        ticker=ticker.upper(),
        cik=cik,
        latest_10k=latest_10k,
        latest_10q=latest_10q,
        latest_8k=latest_8k,
        metrics=metrics,
        source_name="SEC EDGAR",
        source_url=submissions_url,
        retrieved_at=retrieved_at,
        warning=facts_warning or ("" if not missing_metrics else "Unavailable SEC metrics: " + ", ".join(missing_metrics)),
        metrics_history=metrics_history,
    )


def unavailable_sec_financials(
    ticker: str,
    warning: str,
    retrieved_at: str | None = None,
) -> SecFinancialsResult:
    return SecFinancialsResult(
        ticker=ticker.upper(),
        cik="",
        latest_10k=None,
        latest_10q=None,
        latest_8k=None,
        metrics={},
        source_name="SEC EDGAR",
        source_url="https://data.sec.gov/",
        retrieved_at=retrieved_at or datetime.now(UTC).isoformat(),
        warning=warning,
    )


def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip" or raw.startswith(b"\x1f\x8b"):
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


def _latest_form(recent: dict[str, list[str]], form_name: str) -> FilingMetadata | None:
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    report_dates = recent.get("reportDate", [])
    for idx, form in enumerate(forms):
        if form == form_name:
            return FilingMetadata(
                form=form,
                filing_date=_list_get(filing_dates, idx),
                accession_number=_list_get(accessions, idx),
                report_date=_list_get(report_dates, idx),
            )
    return None


def _extract_company_facts(facts: dict[str, Any]) -> dict[str, dict[str, str | float | None]]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    mapping = {
        "revenue": ("Revenues", "SalesRevenueNet"),
        "gross_profit": ("GrossProfit",),
        "operating_income": ("OperatingIncomeLoss",),
        "net_income": ("NetIncomeLoss",),
        "cash_and_equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
        "total_debt": ("LongTermDebtAndFinanceLeaseObligations", "LongTermDebt"),
        "total_assets": ("Assets",),
        "total_liabilities": ("Liabilities",),
        "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
        "capital_expenditure": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquirePropertyAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ),
        "shares_outstanding": ("EntityCommonStockSharesOutstanding",),
        "diluted_eps": ("EarningsPerShareDiluted",),
    }
    output: dict[str, dict[str, str | float | None]] = {}
    for metric, tags in mapping.items():
        output[metric] = _latest_fact(us_gaap, tags)
    ocf_metric = output.get("operating_cash_flow", {})
    capex_metric = output.get("capital_expenditure", {})
    ocf = ocf_metric.get("value")
    capex = capex_metric.get("value")
    if (
        isinstance(ocf, (int, float))
        and isinstance(capex, (int, float))
        and ocf_metric.get("period") == capex_metric.get("period")
    ):
        output["free_cash_flow"] = {
            "value": ocf - abs(capex),
            "period": output["operating_cash_flow"].get("period"),
            "filed": output["operating_cash_flow"].get("filed"),
            "source": "SEC EDGAR company facts",
            "classification": "derived_calculation",
        }
    else:
        missing = "operating cash flow" if not isinstance(ocf, (int, float)) else "matching-period capital expenditure"
        output["free_cash_flow"] = {
            "value": None,
            "source": f"Unavailable: {missing} XBRL tag not found; free cash flow cannot be calculated.",
            "classification": "unavailable",
        }
    shares = output.get("shares_outstanding", {}).get("value")
    net_income_metric = output.get("net_income", {})
    eps_metric = output.get("diluted_eps", {})
    net_income = net_income_metric.get("value")
    diluted_eps = eps_metric.get("value")
    if (
        shares is None
        and isinstance(net_income, (int, float))
        and isinstance(diluted_eps, (int, float))
        and diluted_eps != 0
        and net_income_metric.get("period") == eps_metric.get("period")
    ):
        output["shares_outstanding"] = {
            "value": net_income / diluted_eps,
            "period": net_income_metric.get("period"),
            "filed": net_income_metric.get("filed"),
            "source": "Derived from SEC EDGAR net income divided by diluted EPS",
            "classification": "derived_calculation",
            "form": net_income_metric.get("form", ""),
            "fp": net_income_metric.get("fp", ""),
            "frame": net_income_metric.get("frame", ""),
        }
    return output


def _extract_company_fact_histories(facts: dict[str, Any]) -> dict[str, tuple[dict[str, str | float | None], ...]]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    mapping = {
        "revenue": ("Revenues", "SalesRevenueNet"),
        "gross_profit": ("GrossProfit",),
        "operating_income": ("OperatingIncomeLoss",),
        "net_income": ("NetIncomeLoss",),
        "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
        "capital_expenditure": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquirePropertyAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ),
        "diluted_eps": ("EarningsPerShareDiluted",),
    }
    return {metric: _fact_history(us_gaap, tags) for metric, tags in mapping.items()}


def _latest_fact(us_gaap: dict[str, Any], tags: tuple[str, ...]) -> dict[str, str | float | None]:
    for tag in tags:
        units = us_gaap.get(tag, {}).get("units", {})
        for unit_values in units.values():
            if not isinstance(unit_values, list):
                continue
            candidates = [item for item in unit_values if "val" in item and item.get("filed")]
            if candidates:
                latest = sorted(candidates, key=lambda item: str(item.get("filed", "")), reverse=True)[0]
                return {
                    "value": latest.get("val"),
                    "period": latest.get("end", ""),
                    "filed": latest.get("filed", ""),
                    "form": latest.get("form", ""),
                    "fp": latest.get("fp", ""),
                    "frame": latest.get("frame", ""),
                    "source": f"SEC EDGAR company facts tag {tag}",
                    "classification": "actual",
                }
    return {
        "value": None,
        "source": "Unavailable: XBRL tag not found (" + ", ".join(tags) + ")",
        "classification": "unavailable",
    }


def _fact_history(us_gaap: dict[str, Any], tags: tuple[str, ...]) -> tuple[dict[str, str | float | None], ...]:
    for tag in tags:
        units = us_gaap.get(tag, {}).get("units", {})
        rows: list[dict[str, str | float | None]] = []
        for unit_values in units.values():
            if not isinstance(unit_values, list):
                continue
            for item in unit_values:
                if "val" not in item or not item.get("end"):
                    continue
                rows.append(
                    {
                        "value": item.get("val"),
                        "period": item.get("end", ""),
                        "filed": item.get("filed", ""),
                        "form": item.get("form", ""),
                        "fp": item.get("fp", ""),
                        "frame": item.get("frame", ""),
                        "source": f"SEC EDGAR company facts tag {tag}",
                        "classification": "actual",
                    }
                )
        if rows:
            return tuple(sorted(rows, key=lambda row: str(row.get("period", "")))[-8:])
    return ()


def _list_get(values: list[str], idx: int) -> str:
    return values[idx] if idx < len(values) else ""


DEFAULT_TICKER_CIK = {
    "NVDA": "1045810",
    "AMD": "2488",
    "MSFT": "789019",
    "GOOGL": "1652044",
    "AMZN": "1018724",
    "META": "1326801",
    "ORCL": "1341439",
    "PLTR": "1321655",
    "MU": "723125",
}
