"""Local configuration helpers."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from dataclasses import dataclass


REQUIRED_LIVE_KEYS = (
    "FMP_API_KEY",
    "EODHD_API_KEY",
    "POLYGON_API_KEY",
    "TIINGO_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "FRED_API_KEY",
    "ANYSEARCH_API_KEY",
    "SEC_USER_AGENT",
)


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from .env and environment variables."""

    alpha_vantage_api_key: str
    fmp_api_key: str
    eodhd_api_key: str
    polygon_api_key: str
    tiingo_api_key: str
    fred_api_key: str
    anysearch_api_key: str
    sec_user_agent: str

    @property
    def missing_keys(self) -> tuple[str, ...]:
        values = {
            "ALPHA_VANTAGE_API_KEY": self.alpha_vantage_api_key,
            "FMP_API_KEY": self.fmp_api_key,
            "EODHD_API_KEY": self.eodhd_api_key,
            "POLYGON_API_KEY": self.polygon_api_key,
            "TIINGO_API_KEY": self.tiingo_api_key,
            "FRED_API_KEY": self.fred_api_key,
            "ANYSEARCH_API_KEY": self.anysearch_api_key,
            "SEC_USER_AGENT": self.sec_user_agent,
        }
        return tuple(key for key, value in values.items() if not value)


@dataclass(frozen=True)
class CredentialDiagnostic:
    """One environment diagnostic row for live data readiness."""

    key: str
    category: str
    state: str
    requirement: str
    fallback: str
    expected_coverage: str


def diagnose_environment(config: AppConfig) -> tuple[CredentialDiagnostic, ...]:
    """Describe which live data categories can run with the current .env."""

    rows = (
        (
            "yfinance",
            "Market data and fallback financials",
            "installed" if importlib.util.find_spec("yfinance") else "",
            "primary free/no-key provider",
            "yahooquery",
            "latest available price, OHLCV, historical prices, moving averages, market cap where available, fallback financials",
        ),
        (
            "yahooquery",
            "Market data and fallback financials",
            "installed" if importlib.util.find_spec("yahooquery") else "",
            "backup free/no-key provider",
            "FMP optional",
            "price history, market fields, fallback financial statements, and news where available",
        ),
        (
            "SEC_USER_AGENT",
            "SEC filings and XBRL financials",
            config.sec_user_agent,
            "required for SEC",
            "none",
            "SEC submissions, 10-K/10-Q/8-K dates, company facts, and filing-backed financial fields",
        ),
        (
            "FMP_API_KEY",
            "Optional premium provider",
            config.fmp_api_key,
            "optional upgrade",
            "free/no-key yfinance and yahooquery first",
            "market data, fundamentals, ratios, estimates, earnings calendar, profile, and news where plan permits",
        ),
        (
            "FRED_API_KEY",
            "Macro data",
            config.fred_api_key,
            "optional",
            "FRED public CSV",
            "Treasury yield, fed funds, CPI, PCE, and unemployment where FRED public CSV is reachable",
        ),
        (
            "ANYSEARCH_API_KEY",
            "AnySearch Codex skill",
            config.anysearch_api_key,
            "optional",
            "source cache",
            "Codex skill discovery can be saved to outputs/source_cache/{TICKER}.json and read with --use-source-cache",
        ),
        (
            "outputs/source_cache/",
            "AnySearch source cache",
            "available" if Path("outputs/source_cache").exists() else "",
            "optional source-cache workflow",
            "company IR links",
            "recent developments, official source discovery, regulatory updates, catalysts, and tracker evidence",
        ),
        (
            "Mock data",
            "Offline fixtures",
            "available",
            "explicit --mock only",
            "never used silently in live mode",
            "unit tests and offline development",
        ),
    )
    return tuple(
        CredentialDiagnostic(
            key=key,
            category=category,
            state="configured" if value else "missing",
            requirement=requirement,
            fallback=fallback if fallback != "none" else "unavailable",
            expected_coverage=coverage if value or fallback != "none" else "unavailable",
        )
        for key, category, value, requirement, fallback, coverage in rows
    )


def render_data_diagnostics(config: AppConfig) -> str:
    """Render startup live-data diagnostics for the CLI."""

    rows = diagnose_environment(config)
    lines = [
        "Live data diagnostics",
        "",
        "| Key | Category | State | Requirement | Fallback | Expected coverage |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {row.key} | {row.category} | {row.state} | {row.requirement} | {row.fallback} | {row.expected_coverage} |"
        for row in rows
    )
    lines.extend(
        [
            "",
            "Summary:",
            "- SEC financials require SEC_USER_AGENT and are unavailable without it.",
            "- Market data uses provider order: yfinance, yahooquery, optional FMP, configured legacy providers, unavailable.",
            "- Financial data uses provider order: SEC EDGAR, yfinance, yahooquery, optional FMP, unavailable.",
            "- FMP is optional and missing FMP_API_KEY should not block live reports.",
            "- Macro data can work through FRED public CSV fallback when FRED_API_KEY is missing.",
            "- Missing fields are reported as unavailable; live mode never silently substitutes mock data.",
        ]
    )
    return "\n".join(lines)


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs from .env without external dependencies."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: Path = Path(".env")) -> AppConfig:
    """Load local runtime configuration without hardcoding credentials."""

    load_dotenv(path)
    return AppConfig(
        alpha_vantage_api_key=_env_value("ALPHA_VANTAGE_API_KEY"),
        fmp_api_key=_env_value("FMP_API_KEY"),
        eodhd_api_key=_env_value("EODHD_API_KEY"),
        polygon_api_key=_env_value("POLYGON_API_KEY"),
        tiingo_api_key=_env_value("TIINGO_API_KEY"),
        fred_api_key=_env_value("FRED_API_KEY"),
        anysearch_api_key=_env_value("ANYSEARCH_API_KEY"),
        sec_user_agent=_env_value("SEC_USER_AGENT"),
    )


def _env_value(key: str) -> str:
    """Return configured value, treating common placeholders as missing."""

    value = os.environ.get(key, "").strip()
    lowered = value.lower()
    placeholder_fragments = (
        "your_",
        "_here",
        "replace_me",
        "changeme",
        "placeholder",
        "api_key_here",
    )
    if any(fragment in lowered for fragment in placeholder_fragments):
        return ""
    return value


def missing_key_warnings(config: AppConfig) -> tuple[str, ...]:
    """Return user-facing warnings for missing live connector credentials."""

    messages = {
        "FRED_API_KEY": "FRED_API_KEY is not configured; the macro connector will try FRED public CSV fallback and otherwise mark macro data unavailable.",
        "ANYSEARCH_API_KEY": "ANYSEARCH_API_KEY is not configured; Codex AnySearch can still use anonymous access, but reports only read saved outputs/source_cache/{TICKER}.json when --use-source-cache is used.",
        "SEC_USER_AGENT": "SEC financial data unavailable because SEC_USER_AGENT is not configured. Add SEC_USER_AGENT=AIInvestmentResearchAgent/0.1 your-email@example.com to .env.",
    }
    return tuple(
        messages[key]
        for key in config.missing_keys
        if key in messages
    )


def load_official_ir_urls(
    ticker: str,
    path: Path = Path("data_sources.yaml"),
) -> tuple[str, ...]:
    """Load official IR URLs for a ticker from data_sources.yaml.

    This intentionally supports the simple repository YAML shape without adding
    a third-party YAML dependency.
    """

    if not path.exists():
        return ()
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    in_ir_block = False
    in_ticker_block = False
    urls: list[str] = []
    wanted = ticker.strip().upper()

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if not stripped or stripped.startswith("#"):
            continue
        if indent == 0:
            in_ir_block = stripped == "official_ir_urls:"
            in_ticker_block = False
            continue
        if not in_ir_block:
            continue
        if indent == 2 and stripped.endswith(":"):
            in_ticker_block = stripped[:-1].strip().upper() == wanted
            continue
        if in_ticker_block and indent == 4 and stripped.startswith("- "):
            urls.append(stripped[2:].strip())

    return tuple(urls)
