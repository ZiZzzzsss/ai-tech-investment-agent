"""Tests for memo change tracking."""

import tempfile
import unittest
from pathlib import Path

from src.research import (
    MemoSnapshot,
    compare_memo_snapshots,
    load_memo_snapshot,
    save_memo_snapshot,
)


def make_snapshot(
    price: float = 100.0,
    revenue_growth: float = 0.20,
    catalysts: tuple[str, ...] = ("Earnings update",),
) -> MemoSnapshot:
    return MemoSnapshot(
        ticker="MOCK",
        price=price,
        valuation_multiples={"P/E": "Mock elevated"},
        revenue_growth=revenue_growth,
        margin_trend=0.05,
        free_cash_flow_trend=0.04,
        bayesian_growth_probabilities={"H0": 0.05, "H1": 0.10, "H2": 0.25, "H3": 0.40, "H4": 0.15, "H5": 0.05},
        tam_adjusted_peg_score=1.5,
        gf_dma_health_score=80.0,
        catalysts=catalysts,
        risks=("Valuation compression",),
        entry_price_zone={
            "conservative_entry_max": 75.0,
            "reasonable_accumulation_min": 75.0,
            "reasonable_accumulation_max": 95.0,
            "expensive_wait_min": 95.0,
        },
    )


class ChangeTrackerTests(unittest.TestCase):
    def test_first_snapshot_returns_baseline_change(self) -> None:
        changes = compare_memo_snapshots(None, make_snapshot())

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].category, "Baseline")

    def test_detects_numeric_and_list_changes(self) -> None:
        previous = make_snapshot()
        current = make_snapshot(
            price=110.0,
            revenue_growth=0.25,
            catalysts=("Earnings update", "New product launch"),
        )

        changes = compare_memo_snapshots(previous, current)
        summaries = {change.category: change.summary for change in changes}

        self.assertIn("increased", summaries["Price"])
        self.assertIn("increased", summaries["Revenue growth"])
        self.assertIn("added New product launch", summaries["Catalysts"])

    def test_snapshot_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            original = make_snapshot()

            save_memo_snapshot(original, snapshot_dir)
            loaded = load_memo_snapshot("MOCK", snapshot_dir)

        self.assertEqual(loaded, original)


if __name__ == "__main__":
    unittest.main()
