"""Table-rendering functions for manuscript/manuscript.qmd.

Each function reads from analysis/results/coded_papers.csv (via the
authoritative results directory) and prints a Markdown table.  When
coded_papers.csv does not yet exist the function prints a placeholder
so the manuscript still renders at any pipeline stage.

Call signature: table_*(s) where s = build_stats() — the stats dict
is accepted for API consistency even when a function doesn't use it.
"""

from __future__ import annotations

import csv
import re
import textwrap
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CODED = _ROOT / "analysis" / "results" / "coded_papers.csv"

_PLACEHOLDER = "*Awaiting screening and coding data.*"

# PROBAST rating abbreviations for compact table columns
_PROBAST_ABBR = {"Low": "L", "High": "H", "Unclear": "U", "": "—"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_coded() -> list[dict]:
    if not _CODED.exists():
        return []
    with open(_CODED, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _get(row: dict, col: str, default: str = "—") -> str:
    v = (row.get(col) or "").strip()
    return v if v else default


def _short(text: str, n: int = 40) -> str:
    return textwrap.shorten(text, width=n, placeholder="…")


def _probast_cell(row: dict, col: str) -> str:
    raw = (row.get(col) or "").strip()
    for full, abbr in _PROBAST_ABBR.items():
        if raw.lower() == full.lower():
            return abbr
    return raw[:1] or "—"


def _study_label(row: dict) -> str:
    """Return 'AuthorYear' from item_key or bbt_key."""
    key = _get(row, "item_key") or _get(row, "bbt_key")
    # BBT keys are typically AuthorYYYYword; strip trailing word
    m = re.match(r"([A-Za-z]+\d{4})", key)
    return m.group(1) if m else key


def _auc_from_metric(text: str) -> str:
    m = re.search(r"(?:AUC|C-statistic)[:\s]+([\d.]+)", text, re.I)
    return m.group(1) if m else "—"


def _filter_joint(rows: list[dict], joint: str) -> list[dict]:
    """Return rows whose joint_type contains `joint` (not the other)."""
    if joint == "TKA":
        return [r for r in rows if "TKA" in _get(r, "joint_type")
                and "THA" not in _get(r, "joint_type")]
    if joint == "THA":
        return [r for r in rows if "THA" in _get(r, "joint_type")
                and "TKA" not in _get(r, "joint_type")]
    return rows


def _md_table(headers: list[str], rows: list[list[str]]) -> None:
    sep = ["-" * max(4, len(h)) for h in headers]
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(sep) + " |")
    for row in rows:
        cells = [str(c).replace("|", "\\|") for c in row]
        print("| " + " | ".join(cells) + " |")


# ---------------------------------------------------------------------------
# Public table functions
# ---------------------------------------------------------------------------

def table_study_characteristics(s: dict) -> None:  # noqa: ARG001
    """Table 1 — study characteristics for all included studies."""
    rows = _load_coded()
    if not rows:
        print(_PLACEHOLDER)
        return

    headers = [
        "Study", "Country", "Design", "N", "Joint",
        "AI method", "Outcome (PROM)", "Follow-up (mo)",
    ]
    data = []
    for r in rows:
        data.append([
            _study_label(r),
            _short(_get(r, "country"), 20),
            _short(_get(r, "study_design"), 20),
            _get(r, "sample_size"),
            _get(r, "joint_type"),
            _short(_get(r, "ai_method"), 30),
            _short(_get(r, "outcome_measure"), 30),
            _get(r, "follow_up_months"),
        ])
    _md_table(headers, data)


def table_probast_tka(s: dict) -> None:  # noqa: ARG001
    """Table 2 — PROBAST risk of bias for TKA studies."""
    rows = _filter_joint(_load_coded(), "TKA")
    if not rows:
        print(_PLACEHOLDER)
        return

    headers = ["Study", "D1 Participants", "D2 Predictors",
               "D3 Outcome", "D4 Analysis", "Overall"]
    data = []
    for r in rows:
        data.append([
            _study_label(r),
            _probast_cell(r, "probast_participants"),
            _probast_cell(r, "probast_predictors"),
            _probast_cell(r, "probast_outcome"),
            _probast_cell(r, "probast_analysis"),
            _probast_cell(r, "probast_overall"),
        ])
    _md_table(headers, data)
    print("")
    print("*L = Low risk; H = High risk; U = Unclear.*")


def table_probast_tha(s: dict) -> None:  # noqa: ARG001
    """Table 3 — PROBAST risk of bias for THA studies."""
    rows = _filter_joint(_load_coded(), "THA")
    if not rows:
        print(_PLACEHOLDER)
        return

    headers = ["Study", "D1 Participants", "D2 Predictors",
               "D3 Outcome", "D4 Analysis", "Overall"]
    data = []
    for r in rows:
        data.append([
            _study_label(r),
            _probast_cell(r, "probast_participants"),
            _probast_cell(r, "probast_predictors"),
            _probast_cell(r, "probast_outcome"),
            _probast_cell(r, "probast_analysis"),
            _probast_cell(r, "probast_overall"),
        ])
    _md_table(headers, data)
    print("")
    print("*L = Low risk; H = High risk; U = Unclear.*")


def table_model_performance_tka(s: dict) -> None:  # noqa: ARG001
    """Table 4 — model performance for TKA studies, sorted by AUC desc."""
    rows = _filter_joint(_load_coded(), "TKA")
    if not rows:
        print(_PLACEHOLDER)
        return

    headers = [
        "Study", "Best model", "Validation", "Primary metric",
        "AUC / C-stat", "PROM", "Prediction target",
    ]
    data = []
    for r in rows:
        pm = _get(r, "performance_metric")
        data.append([
            _study_label(r),
            _short(_get(r, "best_performing_model"), 25),
            _short(_get(r, "validation_method"), 25),
            _short(pm, 35),
            _auc_from_metric(pm),
            _short(_get(r, "outcome_measure"), 20),
            _short(_get(r, "prediction_target"), 25),
        ])
    # Sort by AUC descending; non-numeric values go to end
    def _sort_key(row: list[str]) -> float:
        try:
            return -float(row[4])
        except (ValueError, IndexError):
            return 1.0
    data.sort(key=_sort_key)
    _md_table(headers, data)


def table_model_performance_tha(s: dict) -> None:  # noqa: ARG001
    """Table 5 — model performance for THA studies, sorted by AUC desc."""
    rows = _filter_joint(_load_coded(), "THA")
    if not rows:
        print(_PLACEHOLDER)
        return

    headers = [
        "Study", "Best model", "Validation", "Primary metric",
        "AUC / C-stat", "PROM", "Prediction target",
    ]
    data = []
    for r in rows:
        pm = _get(r, "performance_metric")
        data.append([
            _study_label(r),
            _short(_get(r, "best_performing_model"), 25),
            _short(_get(r, "validation_method"), 25),
            _short(pm, 35),
            _auc_from_metric(pm),
            _short(_get(r, "outcome_measure"), 20),
            _short(_get(r, "prediction_target"), 25),
        ])

    def _sort_key(row: list[str]) -> float:
        try:
            return -float(row[4])
        except (ValueError, IndexError):
            return 1.0
    data.sort(key=_sort_key)
    _md_table(headers, data)
