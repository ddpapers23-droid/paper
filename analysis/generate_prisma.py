"""Generate the PRISMA 2020 flow diagram from pipeline artefacts.

Run:
    python3 analysis/generate_prisma.py

Output: analysis/results/prisma_flow.svg  (also .png via cairosvg if installed)

All counts come from manuscript_stats.build_stats() — never hand-typed.
The diagram is Figure 1 in the manuscript.

Requires:
    pip install matplotlib
    pip install cairosvg   (optional — for PNG export)
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "analysis"))

from manuscript_stats import build_stats  # noqa: E402

_RESULTS = _ROOT / "analysis" / "results"


def _box(ax, x: float, y: float, w: float, h: float,
         text: str, fontsize: float = 9, color: str = "#dce8f5") -> None:
    import matplotlib.patches as mpatches
    rect = mpatches.FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02",
        facecolor=color, edgecolor="#555", linewidth=0.8,
    )
    ax.add_patch(rect)
    ax.text(x, y, text, ha="center", va="center",
            fontsize=fontsize, wrap=True,
            multialignment="center", linespacing=1.4)


def _arrow(ax, x1: float, y1: float, x2: float, y2: float) -> None:
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color="#555", lw=0.8),
    )


def generate(s: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping PRISMA diagram generation")
        return

    # Pull counts
    total      = s.get("search.unique_records") or 0
    abs_inc    = s.get("screen.abstract.n_include") or 0
    abs_bord   = s.get("screen.abstract.n_borderline") or 0
    abs_excl   = s.get("screen.abstract.n_exclude") or 0
    ft_inc     = s.get("screen.fulltext.n_include") or 0
    ft_excl    = s.get("screen.fulltext.n_exclude") or 0

    ft_screened = abs_inc + abs_bord
    # Per-database counts for identification box
    db_lines = []
    for db in ("pubmed", "embase", "cochrane", "scopus", "wos",
               "openalex", "semantic_scholar"):
        n = s.get(f"search.hits.{db}")
        if n:
            db_lines.append(f"{db.title().replace('_', ' ')}: {n:,}")
    db_text = "\n".join(db_lines) if db_lines else "(searches pending)"

    fig, ax = plt.subplots(figsize=(8, 11))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis("off")

    # ── Row 1: Identification ──────────────────────────────────────────────
    _box(ax, 3, 13, 5, 1.4,
         f"Records identified from databases\n(n = {total:,})\n{db_text}",
         fontsize=8)
    _box(ax, 8, 13, 3, 1.4,
         "Records removed before screening\n(duplicates, n = ?)", fontsize=8,
         color="#f5e8dc")

    # ── Row 2: Screening ───────────────────────────────────────────────────
    _arrow(ax, 3, 12.3, 3, 11.7)
    _box(ax, 3, 11.2, 5, 1.0,
         f"Records screened (title/abstract)\n(n = {total:,})", fontsize=9)
    _arrow(ax, 5.5, 11.2, 6.5, 11.2)
    _box(ax, 8, 11.2, 3, 1.0,
         f"Records excluded\n(n = {abs_excl:,})", fontsize=9, color="#f5e8dc")

    # ── Row 3: Eligibility ─────────────────────────────────────────────────
    _arrow(ax, 3, 10.7, 3, 10.1)
    _box(ax, 3, 9.6, 5, 1.0,
         f"Full texts assessed for eligibility\n(n = {ft_screened:,})", fontsize=9)
    _arrow(ax, 5.5, 9.6, 6.5, 9.6)
    _box(ax, 8, 9.6, 3, 1.0,
         f"Full texts excluded\n(n = {ft_excl:,})\n(reasons listed in text)",
         fontsize=8, color="#f5e8dc")

    # ── Row 4: Included ────────────────────────────────────────────────────
    _arrow(ax, 3, 9.1, 3, 8.5)
    _box(ax, 3, 8.0, 5, 1.0,
         f"Studies included in review\n(n = {ft_inc:,})", fontsize=9,
         color="#d5e8d4")

    ax.set_title("Figure 1. PRISMA 2020 Flow Diagram",
                 fontsize=11, fontweight="bold", pad=8)

    out_svg = _RESULTS / "prisma_flow.svg"
    fig.savefig(out_svg, bbox_inches="tight", dpi=150)
    print(f"Written → {out_svg}")

    try:
        import cairosvg
        out_png = _RESULTS / "prisma_flow.png"
        cairosvg.svg2png(url=str(out_svg), write_to=str(out_png), dpi=300)
        print(f"Written → {out_png}")
    except ImportError:
        pass

    plt.close(fig)


if __name__ == "__main__":
    _RESULTS.mkdir(parents=True, exist_ok=True)
    s = build_stats()
    generate(s)
