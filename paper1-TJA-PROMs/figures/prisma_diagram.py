#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "matplotlib>=3.8",
# ]
# ///
"""PRISMA 2020 flow diagram for the AI/ML-PROMs-after-TJA review.

Renders the standard PRISMA 2020 identification -> screening ->
eligibility -> included flow, as boxes with exclusion side-branches.
Every count is a CLI flag; whichever ones you don't pass render as
"TBD" so the diagram is honest about what's actually known yet rather
than guessing.

The identification-stage numbers (identified / duplicates removed /
screened) are already final — they come from search_config.py --version
v2 + dedup.py and don't change. Everything from --excluded-screening
onward is NOT the same thing as the PRELIM_INCLUDE/PRELIM_EXCLUDE/
NEEDS_REVIEW split in screening_config.py's output — those are an
automated triage aid, not the actual reviewer decision. Fill in
--excluded-screening only once the real two-reviewer Rayyan screen
(and kappa_calculator.py-checked adjudication) has produced final
include/exclude decisions.

Usage:
    uv run prisma_diagram.py
    uv run prisma_diagram.py --excluded-screening 420 --sought-retrieval 291
    uv run prisma_diagram.py --assessed-eligibility 180 --excluded-eligibility 95 \\
        --eligibility-reasons "No AUC/performance metric reported (n=38); Wrong outcome (n=25); Not full text available (n=17); Other (n=15)" \\
        --included 85 --output prisma_flow_diagram_final.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.patches import FancyArrowPatch


def _fmt(value: int | None) -> str:
    return str(value) if value is not None else "TBD"


def _box(ax, x: float, y: float, w: float, h: float, text: str, facecolor: str = "#eaf1fb") -> None:
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.06,rounding_size=0.08",
        linewidth=1.1,
        edgecolor="#2c3e50",
        facecolor=facecolor,
    )
    ax.add_patch(box)
    ax.text(x, y, text, ha="center", va="center", fontsize=9, wrap=True)


def _down_arrow(ax, x: float, y_from: float, y_to: float) -> None:
    ax.add_patch(FancyArrowPatch((x, y_from), (x, y_to), arrowstyle="-|>", mutation_scale=14, color="#2c3e50", linewidth=1.1))


def _right_arrow(ax, x_from: float, x_to: float, y: float) -> None:
    ax.add_patch(FancyArrowPatch((x_from, y), (x_to, y), arrowstyle="-|>", mutation_scale=14, color="#2c3e50", linewidth=1.1))


def build_diagram(args: argparse.Namespace) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 13))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 15)
    ax.axis("off")

    main_x, main_w = 3.4, 5.6
    side_x, side_w = 9.4, 4.4

    rows_y = {"identified": 14, "dedup": 12, "screened": 9.6, "sought": 7.2, "assessed": 4.8, "included": 1.6}

    ax.text(0.2, 14.9, "Identification", fontsize=11, fontweight="bold")
    ax.text(0.2, 10.5, "Screening", fontsize=11, fontweight="bold")
    ax.text(0.2, 5.7, "Eligibility", fontsize=11, fontweight="bold")
    ax.text(0.2, 2.5, "Included", fontsize=11, fontweight="bold")

    _box(ax, main_x, rows_y["identified"], main_w, 1.3, f"Records identified from:\nPubMed (n = {_fmt(args.identified)})")
    _down_arrow(ax, main_x, rows_y["identified"] - 0.65, rows_y["dedup"] + 0.65)
    _box(
        ax,
        main_x,
        rows_y["dedup"],
        main_w,
        1.3,
        f"Records removed before screening:\nDuplicate records removed (n = {_fmt(args.duplicates_removed)})",
        facecolor="#fdeeea",
    )

    _down_arrow(ax, main_x, rows_y["dedup"] - 0.65, rows_y["screened"] + 0.65)
    _box(ax, main_x, rows_y["screened"], main_w, 1.3, f"Records screened\n(n = {_fmt(args.screened)})")
    _right_arrow(ax, main_x + main_w / 2, side_x - side_w / 2, rows_y["screened"])
    _box(ax, side_x, rows_y["screened"], side_w, 1.3, f"Records excluded\n(n = {_fmt(args.excluded_screening)})", facecolor="#fdeeea")

    _down_arrow(ax, main_x, rows_y["screened"] - 0.65, rows_y["sought"] + 0.65)
    _box(ax, main_x, rows_y["sought"], main_w, 1.3, f"Reports sought for retrieval\n(n = {_fmt(args.sought_retrieval)})")
    _right_arrow(ax, main_x + main_w / 2, side_x - side_w / 2, rows_y["sought"])
    _box(ax, side_x, rows_y["sought"], side_w, 1.3, f"Reports not retrieved\n(n = {_fmt(args.not_retrieved)})", facecolor="#fdeeea")

    _down_arrow(ax, main_x, rows_y["sought"] - 0.65, rows_y["assessed"] + 0.65)
    _box(ax, main_x, rows_y["assessed"], main_w, 1.3, f"Reports assessed for eligibility\n(n = {_fmt(args.assessed_eligibility)})")
    _right_arrow(ax, main_x + main_w / 2, side_x - side_w / 2, rows_y["assessed"])
    reasons = args.eligibility_reasons.replace(";", "\n").strip() if args.eligibility_reasons else "TBD"
    _box(
        ax,
        side_x,
        rows_y["assessed"],
        side_w,
        1.9,
        f"Reports excluded (n = {_fmt(args.excluded_eligibility)}):\n{reasons}",
        facecolor="#fdeeea",
    )

    _down_arrow(ax, main_x, rows_y["assessed"] - 0.65, rows_y["included"] + 0.65)
    _box(ax, main_x, rows_y["included"], main_w, 1.3, f"Studies included in review\n(n = {_fmt(args.included)})", facecolor="#e8f5e9")

    fig.suptitle("PRISMA 2020 Flow Diagram\nAI/ML Prediction of PROMs after TKA/THA", fontsize=12, y=0.99)
    fig.tight_layout()
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--identified", type=int, default=713, help="PubMed v2 raw records (final)")
    parser.add_argument("--duplicates-removed", type=int, default=2, help="Duplicates removed by dedup.py (final)")
    parser.add_argument("--screened", type=int, default=711, help="Records entering title/abstract screening (final)")
    parser.add_argument("--excluded-screening", type=int, default=None, help="Final Rayyan dual-reviewer exclusions, NOT the PRELIM_EXCLUDE auto-triage count")
    parser.add_argument("--sought-retrieval", type=int, default=None)
    parser.add_argument("--not-retrieved", type=int, default=None)
    parser.add_argument("--assessed-eligibility", type=int, default=None)
    parser.add_argument("--excluded-eligibility", type=int, default=None)
    parser.add_argument("--eligibility-reasons", default=None, help='Semicolon-separated, e.g. "No AUC reported (n=8); Wrong outcome (n=4)"')
    parser.add_argument("--included", type=int, default=None)
    parser.add_argument("--output", default="prisma_flow_diagram.png")
    args = parser.parse_args()

    output_path = Path(__file__).resolve().parent / args.output
    fig = build_diagram(args)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
