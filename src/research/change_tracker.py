"""Track changes between generated company memos.

The tracker compares structured memo snapshots rather than prose. This keeps
the "what changed" section deterministic and avoids treating Markdown wording
changes as investment-relevant changes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MemoSnapshot:
    """Structured state used to compare one memo run with the prior run."""

    ticker: str
    price: float
    valuation_multiples: dict[str, str]
    revenue_growth: float
    margin_trend: float
    free_cash_flow_trend: float
    bayesian_growth_probabilities: dict[str, float]
    tam_adjusted_peg_score: float
    gf_dma_health_score: float
    catalysts: tuple[str, ...]
    risks: tuple[str, ...]
    entry_price_zone: dict[str, float]


@dataclass(frozen=True)
class ChangeRecord:
    """Plain-English change summary for one tracked category."""

    category: str
    previous: str
    current: str
    summary: str


def compare_memo_snapshots(
    previous: MemoSnapshot | None,
    current: MemoSnapshot,
) -> tuple[ChangeRecord, ...]:
    """Compare the current memo snapshot with the previous one."""

    if previous is None:
        return (
            ChangeRecord(
                category="Baseline",
                previous="No previous memo snapshot",
                current="Current memo snapshot created",
                summary="This is the first tracked review for this ticker.",
            ),
        )

    return (
        _numeric_change("Price", previous.price, current.price, money=True),
        _mapping_change(
            "Valuation multiples",
            previous.valuation_multiples,
            current.valuation_multiples,
        ),
        _numeric_change("Revenue growth", previous.revenue_growth, current.revenue_growth),
        _numeric_change("Margin trend", previous.margin_trend, current.margin_trend),
        _numeric_change(
            "Free cash flow trend",
            previous.free_cash_flow_trend,
            current.free_cash_flow_trend,
        ),
        _probability_change(
            previous.bayesian_growth_probabilities,
            current.bayesian_growth_probabilities,
        ),
        _numeric_change(
            "TAM-adjusted PEG score",
            previous.tam_adjusted_peg_score,
            current.tam_adjusted_peg_score,
            suffix="x",
        ),
        _numeric_change(
            "GF-DMA health score",
            previous.gf_dma_health_score,
            current.gf_dma_health_score,
            suffix="/100",
        ),
        _list_change("Catalysts", previous.catalysts, current.catalysts),
        _list_change("Risks", previous.risks, current.risks),
        _entry_zone_change(previous.entry_price_zone, current.entry_price_zone),
    )


def load_memo_snapshot(ticker: str, snapshot_dir: Path) -> MemoSnapshot | None:
    """Load the prior memo snapshot for a ticker if one exists."""

    path = _snapshot_path(ticker, snapshot_dir)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return snapshot_from_dict(data)


def save_memo_snapshot(snapshot: MemoSnapshot, snapshot_dir: Path) -> Path:
    """Save the latest memo snapshot for future comparisons."""

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(snapshot.ticker, snapshot_dir)
    path.write_text(
        json.dumps(snapshot_to_dict(snapshot), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def snapshot_to_dict(snapshot: MemoSnapshot) -> dict[str, Any]:
    """Serialize a snapshot to JSON-compatible data."""

    data = asdict(snapshot)
    data["catalysts"] = list(snapshot.catalysts)
    data["risks"] = list(snapshot.risks)
    return data


def snapshot_from_dict(data: dict[str, Any]) -> MemoSnapshot:
    """Deserialize a snapshot from JSON-compatible data."""

    return MemoSnapshot(
        ticker=str(data["ticker"]),
        price=float(data["price"]),
        valuation_multiples={str(k): str(v) for k, v in data["valuation_multiples"].items()},
        revenue_growth=float(data["revenue_growth"]),
        margin_trend=float(data["margin_trend"]),
        free_cash_flow_trend=float(data["free_cash_flow_trend"]),
        bayesian_growth_probabilities={
            str(k): float(v) for k, v in data["bayesian_growth_probabilities"].items()
        },
        tam_adjusted_peg_score=float(data["tam_adjusted_peg_score"]),
        gf_dma_health_score=float(data["gf_dma_health_score"]),
        catalysts=tuple(str(item) for item in data["catalysts"]),
        risks=tuple(str(item) for item in data["risks"]),
        entry_price_zone={str(k): float(v) for k, v in data["entry_price_zone"].items()},
    )


def _snapshot_path(ticker: str, snapshot_dir: Path) -> Path:
    return snapshot_dir / f"{ticker.upper()}_latest.json"


def _numeric_change(
    category: str,
    previous: float,
    current: float,
    money: bool = False,
    suffix: str = "",
) -> ChangeRecord:
    previous_text = _format_number(previous, money=money, suffix=suffix)
    current_text = _format_number(current, money=money, suffix=suffix)
    delta = current - previous
    if abs(delta) < 0.000001:
        summary = f"{category} was unchanged."
    else:
        direction = "increased" if delta > 0 else "decreased"
        summary = (
            f"{category} {direction} by "
            f"{_format_number(abs(delta), money=money, suffix=suffix)}."
        )
    return ChangeRecord(category, previous_text, current_text, summary)


def _mapping_change(
    category: str,
    previous: dict[str, str],
    current: dict[str, str],
) -> ChangeRecord:
    previous_text = _format_mapping(previous)
    current_text = _format_mapping(current)
    if previous == current:
        summary = f"{category} were unchanged."
    else:
        changed_keys = sorted(
            key for key in set(previous) | set(current) if previous.get(key) != current.get(key)
        )
        summary = f"{category} changed for: {', '.join(changed_keys)}."
    return ChangeRecord(category, previous_text, current_text, summary)


def _probability_change(
    previous: dict[str, float],
    current: dict[str, float],
) -> ChangeRecord:
    previous_text = _format_probability_mapping(previous)
    current_text = _format_probability_mapping(current)
    changed_keys = sorted(
        key for key in set(previous) | set(current)
        if abs(previous.get(key, 0.0) - current.get(key, 0.0)) >= 0.000001
    )
    if not changed_keys:
        summary = "Bayesian growth probabilities were unchanged."
    else:
        largest_key = max(
            changed_keys,
            key=lambda key: abs(previous.get(key, 0.0) - current.get(key, 0.0)),
        )
        delta = current.get(largest_key, 0.0) - previous.get(largest_key, 0.0)
        direction = "increased" if delta > 0 else "decreased"
        summary = (
            f"Bayesian growth probabilities changed most in {largest_key}, "
            f"which {direction} by {abs(delta):.1%}."
        )
    return ChangeRecord(
        "Bayesian growth probabilities",
        previous_text,
        current_text,
        summary,
    )


def _list_change(
    category: str,
    previous: tuple[str, ...],
    current: tuple[str, ...],
) -> ChangeRecord:
    previous_set = set(previous)
    current_set = set(current)
    added = sorted(current_set - previous_set)
    removed = sorted(previous_set - current_set)
    previous_text = "; ".join(previous) if previous else "None"
    current_text = "; ".join(current) if current else "None"
    if not added and not removed:
        summary = f"{category} were unchanged."
    else:
        parts = []
        if added:
            parts.append("added " + ", ".join(added))
        if removed:
            parts.append("removed " + ", ".join(removed))
        summary = f"{category} " + "; ".join(parts) + "."
    return ChangeRecord(category, previous_text, current_text, summary)


def _entry_zone_change(
    previous: dict[str, float],
    current: dict[str, float],
) -> ChangeRecord:
    previous_text = _format_entry_zones(previous)
    current_text = _format_entry_zones(current)
    if previous == current:
        summary = "Entry-price zone was unchanged."
    else:
        summary = "Entry-price zone changed with the scenario-weighted fair value."
    return ChangeRecord("Entry-price zone", previous_text, current_text, summary)


def _format_number(value: float, money: bool = False, suffix: str = "") -> str:
    if money:
        return f"${value:,.2f}"
    if suffix:
        return f"{value:.2f}{suffix}"
    return f"{value:.1%}"


def _format_mapping(values: dict[str, str]) -> str:
    return "; ".join(f"{key}: {values[key]}" for key in sorted(values)) or "None"


def _format_probability_mapping(values: dict[str, float]) -> str:
    return "; ".join(f"{key}: {values[key]:.1%}" for key in sorted(values)) or "None"


def _format_entry_zones(values: dict[str, float]) -> str:
    return "; ".join(f"{key}: ${values[key]:,.2f}" for key in sorted(values)) or "None"
