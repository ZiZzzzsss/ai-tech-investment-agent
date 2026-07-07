"""Command-line entry point for generating investment research memos.

Live mode is the default. Mock mode is available only for tests, offline
development, and explicit --mock use.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from src.config import load_config, render_data_diagnostics
from src.connectors.mock_data import available_tickers, get_mock_company
from src.reports import (
    build_live_buy_side_memo_input,
    build_mock_buy_side_memo_input,
    build_mock_memo_snapshot,
    render_buy_side_memo,
    render_html_memo,
    render_index,
)
from src.research import load_memo_snapshot, save_memo_snapshot
from src.validation.calculation_audit import DEFAULT_AUDIT_PATH, write_audit_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a live-source AI technology investment research memo."
    )
    parser.add_argument(
        "--ticker",
        required=False,
        help="Ticker to report on. Supported mock tickers: "
        + ", ".join(available_tickers())
            + ". Nebius can also be requested as NEBIUS.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "html", "both"),
        default="markdown",
        help="Output format to generate.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live source connectors. This is the default.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock fixtures for tests or offline development. Never used silently.",
    )
    parser.add_argument(
        "--diagnose-data",
        action="store_true",
        help="Show live data-source readiness diagnostics and exit.",
    )
    parser.add_argument(
        "--use-source-cache",
        action="store_true",
        help="Read AnySearch Codex skill results from outputs/source_cache/{TICKER}.json.",
    )
    parser.add_argument(
        "--audit-calculations",
        action="store_true",
        help="Run deterministic formula audit and write outputs/calculation_audit.md.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    if args.audit_calculations:
        audit = write_audit_report(output_path=DEFAULT_AUDIT_PATH)
        print(f"Calculation audit {'passed' if audit.passed else 'failed'}: outputs/calculation_audit.md")
        return 0 if audit.passed else 1
    if args.diagnose_data:
        print(render_data_diagnostics(config))
        return 0
    if not args.ticker:
        raise SystemExit("--ticker is required unless --diagnose-data or --audit-calculations is used.")
    ticker = args.ticker.upper()
    use_mock = args.mock

    markdown_dir = Path("outputs") / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = Path("outputs") / "raw_data" / ("mock_snapshots" if use_mock else "live_snapshots")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    previous_snapshot = load_memo_snapshot(ticker, snapshot_dir)
    if use_mock:
        company = get_mock_company(ticker)
        memo_input = build_mock_buy_side_memo_input(
            company,
            previous_snapshot=previous_snapshot,
        )
    else:
        memo_input = build_live_buy_side_memo_input(
            ticker,
            config,
            previous_snapshot=previous_snapshot,
            use_source_cache=args.use_source_cache,
        )

    generated_paths: list[Path] = []
    if args.format in ("markdown", "both"):
        report = render_buy_side_memo(memo_input)
        output_path = markdown_dir / f"{memo_input.ticker}.md"
        output_path.write_text(report, encoding="utf-8")
        generated_paths.append(output_path)

    if args.format in ("html", "both"):
        site_dir = Path("local_site")
        html_dir = site_dir / "company_memos"
        html_dir.mkdir(parents=True, exist_ok=True)
        _copy_local_assets(site_dir)
        html_path = html_dir / f"{memo_input.ticker}.html"
        html_path.write_text(render_html_memo(memo_input), encoding="utf-8")
        _write_index(site_dir)
        generated_paths.append(html_path)

    if use_mock:
        save_memo_snapshot(build_mock_memo_snapshot(company), snapshot_dir)

    for path in generated_paths:
        print(f"Generated {'mock' if use_mock else 'live'} report: {path}")
    return 0


def _write_index(site_dir: Path) -> None:
    memo_dir = site_dir / "company_memos"
    memos = []
    for path in memo_dir.glob("*.html"):
        ticker = path.stem.upper()
        try:
            company = get_mock_company(ticker)
            company_name = company.name
        except ValueError:
            company_name = ticker
        memos.append((ticker, company_name, path.name))
    (site_dir / "index.html").write_text(render_index(tuple(memos)), encoding="utf-8")


def _copy_local_assets(site_dir: Path) -> None:
    asset_dir = site_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    source_dir = Path(__file__).parent / "src" / "reports" / "static"
    for filename in ("styles.css", "app.js"):
        shutil.copyfile(source_dir / filename, asset_dir / filename)


if __name__ == "__main__":
    raise SystemExit(main())
