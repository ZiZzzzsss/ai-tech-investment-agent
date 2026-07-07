"""Local static dashboard helper."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from src.config import load_config
from src.connectors.mock_data import get_mock_company
from src.reports import build_live_buy_side_memo_input, build_mock_buy_side_memo_input, render_html_memo, render_index
from src.research import load_memo_snapshot, save_memo_snapshot
from src.reports import build_mock_memo_snapshot


DEFAULT_TICKERS = ("NVDA", "AMD", "ASML", "TSM", "ARM", "MU", "AVGO", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "PLTR", "NBIS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the local static dashboard.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live source connectors. This is the default.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock fixtures for offline development.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    site_dir = Path("local_site")
    memo_dir = site_dir / "company_memos"
    snapshot_dir = Path("outputs") / "raw_data" / ("mock_snapshots" if args.mock else "live_snapshots")
    memo_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    _copy_local_assets(site_dir)

    index_entries = []
    for ticker in DEFAULT_TICKERS:
        previous_snapshot = load_memo_snapshot(ticker, snapshot_dir)
        if args.mock:
            try:
                company = get_mock_company(ticker)
            except ValueError:
                continue
            memo_input = build_mock_buy_side_memo_input(
                company,
                previous_snapshot=previous_snapshot,
            )
            company_name = company.name
            save_memo_snapshot(build_mock_memo_snapshot(company), snapshot_dir)
        else:
            memo_input = build_live_buy_side_memo_input(
                ticker,
                config,
                previous_snapshot=previous_snapshot,
            )
            company_name = memo_input.company_name
        output_path = memo_dir / f"{memo_input.ticker}.html"
        output_path.write_text(render_html_memo(memo_input), encoding="utf-8")
        index_entries.append((memo_input.ticker, company_name, output_path.name))

    (site_dir / "index.html").write_text(render_index(tuple(index_entries)), encoding="utf-8")
    print(f"Generated local dashboard: {site_dir / 'index.html'}")
    return 0


def _copy_local_assets(site_dir: Path) -> None:
    asset_dir = site_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    source_dir = Path(__file__).parent / "src" / "reports" / "static"
    for filename in ("styles.css", "app.js"):
        shutil.copyfile(source_dir / filename, asset_dir / filename)


if __name__ == "__main__":
    raise SystemExit(main())
