"""Stats dictionary for the AI/ML PROM arthroplasty systematic review.

Run:
    python3 analysis/manuscript_stats.py

Output: analysis/results/manuscript_stats.json

Every prose number and methodological fact in manuscript/manuscript.qmd
must come from s['key'] — never a hand-typed literal. Add derived values
here and re-run to regenerate the JSON. This script is project-owned:
extend build_stats() as new pipeline artefacts appear.

KAPPA VALUES must be entered manually (lines marked ← UPDATE) after
the reviewers complete each agreement meeting.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCREENING_DIR = _ROOT / "screening"
_RESULTS_DIR = _ROOT / "analysis" / "results"

# ---------------------------------------------------------------------------
# Inter-rater agreement — fill in after each reviewer meeting.
# ---------------------------------------------------------------------------
# Abstract stage: Cohen's kappa computed from the kappa worksheet (screening/kappa.xlsx).
KAPPA_ABSTRACT: float | None = None          # ← UPDATE after abstract agreement meeting
# Full-text stage: same; computed after dual full-text review.
KAPPA_FULLTEXT: float | None = None          # ← UPDATE after full-text agreement meeting


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config(name: str, path: Path):
    """Load a project config module by file path."""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _last_per_key(rows: list[dict], key_col: str = "item_key") -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        k = (row.get(key_col) or "").strip()
        if k:
            result[k] = row
    return result


def _auc_range(rows: list[dict]) -> tuple[str, str]:
    """Extract min/max AUC values from performance_metric field."""
    aucs: list[float] = []
    for r in rows:
        pm = r.get("performance_metric") or ""
        for m in re.findall(r"(?:AUC|C-statistic)\s+([\d.]+)", pm, re.I):
            try:
                aucs.append(float(m))
            except ValueError:
                pass
    if not aucs:
        return "—", "—"
    return f"{min(aucs):.2f}", f"{max(aucs):.2f}"


def _most_common_prom(rows: list[dict]) -> str:
    counts: Counter = Counter()
    prom_order = ["KOOS", "HOOS", "OKS", "OHS", "WOMAC", "EQ-5D", "SF-36", "PROMIS"]
    for r in rows:
        om = r.get("outcome_measure") or ""
        for prom in prom_order:
            if prom in om:
                counts[prom] += 1
    if not counts:
        return "—"
    return counts.most_common(1)[0][0]


def _count_countries(rows: list[dict]) -> int:
    countries: set[str] = set()
    for r in rows:
        raw = (r.get("country") or "").strip()
        if not raw:
            continue
        for part in re.split(r"[,;]", raw):
            part = re.sub(r"\(.*?\)", "", part).strip(" -—")
            if part:
                countries.add(part)
    return len(countries)


_EXT_VAL_RE = re.compile(r"external|separate institution|separate cohort", re.I)
_INT_VAL_RE = re.compile(r"internal|k-fold|cross-val|random split|temporal split", re.I)


# ---------------------------------------------------------------------------
# build_stats
# ---------------------------------------------------------------------------

def build_stats() -> dict:
    # -- Config files --
    search_cfg = _load_config("search_config", _ROOT / "search_config.py")
    screen_cfg = _load_config("screening_config", _ROOT / "screening_config.py")

    from_year = getattr(search_cfg, "FROM_YEAR", 2010)
    to_year   = getattr(search_cfg, "TO_YEAR", 2026)
    search_hits: dict = getattr(search_cfg, "SEARCH_HITS", {})

    abs_model   = getattr(screen_cfg, "ABSTRACT_SCREENING_MODEL", "—")
    abs_pv      = getattr(screen_cfg, "ABSTRACT_SCREENING_PROMPT_VERSION", "—")
    ft_model    = getattr(screen_cfg, "FULLTEXT_CODING_MODEL", "—")
    ft_pv       = getattr(screen_cfg, "FULLTEXT_CODING_PROMPT_VERSION", "—")

    # -- Pipeline artefacts --
    meta = _safe_json(_ROOT / "search_metadata.json")
    run  = _safe_json(_ROOT / "search_run.json")

    abstract_rows = _safe_csv(_SCREENING_DIR / "abstract_screening.csv")
    fulltext_rows = _safe_csv(_SCREENING_DIR / "fulltext_screening.csv")
    coded_rows    = _safe_csv(_RESULTS_DIR / "coded_papers.csv")

    abstract_last = _last_per_key(abstract_rows)
    fulltext_last = _last_per_key(fulltext_rows)

    # -- Search counts --
    total_hits = sum(v for v in search_hits.values() if isinstance(v, int))
    unique_records = (
        run.get("unique_dois")
        or meta.get("total_unique_records")
        or (total_hits if total_hits else 0)
    )
    search_date = meta.get("search_date_end") or to_year

    # -- Abstract screening --
    n_abs_include    = sum(1 for r in abstract_last.values() if r.get("decision") == "include")
    n_abs_borderline = sum(1 for r in abstract_last.values() if r.get("decision") == "borderline")
    n_abs_exclude    = sum(1 for r in abstract_last.values() if r.get("decision") == "exclude")

    # -- Fulltext screening --
    n_ft_include = sum(1 for r in fulltext_last.values() if r.get("decision") == "include")
    n_ft_exclude = sum(1 for r in fulltext_last.values() if r.get("decision") == "exclude")

    # coded_papers.csv contains only included studies
    n_included = len(coded_rows)
    # Prefer fulltext log count if coded_papers not yet populated
    if n_included == 0 and n_ft_include:
        n_included = n_ft_include

    # -- Study breakdown by joint --
    tka_rows  = [r for r in coded_rows if "TKA" in (r.get("joint_type") or "")]
    tha_rows  = [r for r in coded_rows if "THA" in (r.get("joint_type") or "") and "TKA" not in (r.get("joint_type") or "")]
    both_rows = [r for r in coded_rows if "TKA and THA" in (r.get("joint_type") or "")]

    # -- Validation --
    ext_val_all = [r for r in coded_rows if _EXT_VAL_RE.search(r.get("validation_method") or "")]
    n_ext_val   = len(ext_val_all)
    pct_ext_val = round(n_ext_val / n_included * 100) if n_included else 0

    tka_int_val = sum(1 for r in tka_rows if _INT_VAL_RE.search(r.get("validation_method") or ""))
    tka_ext_val = sum(1 for r in tka_rows if _EXT_VAL_RE.search(r.get("validation_method") or ""))

    # -- PROBAST --
    n_low_overall = sum(
        1 for r in coded_rows
        if (r.get("probast_overall") or "").strip().lower() == "low"
    )
    n_no_metric = sum(
        1 for r in coded_rows
        if (r.get("performance_metric_flag") or "").strip().upper() == "FLAGGED"
    )

    # -- AUC ranges --
    tka_auc_min, tka_auc_max = _auc_range(tka_rows)
    tha_auc_min, tha_auc_max = _auc_range(tha_rows)

    # -- Kappa --
    kappa_abs = KAPPA_ABSTRACT if KAPPA_ABSTRACT is not None else "[pending]"
    kappa_ft  = KAPPA_FULLTEXT if KAPPA_FULLTEXT is not None else "[pending]"

    return {
        # Search provenance
        "search.from_year":             from_year,
        "search.to_year":               to_year,
        "search.date":                  search_date,
        "search.unique_records":        unique_records,
        "search.hits.scopus":           search_hits.get("scopus"),
        "search.hits.wos":              search_hits.get("wos"),
        "search.hits.openalex":         search_hits.get("openalex"),
        "search.hits.semantic_scholar": search_hits.get("semantic_scholar"),
        "search.hits.pubmed":           search_hits.get("pubmed"),
        "search.hits.embase":           search_hits.get("embase"),
        "search.hits.cochrane":         search_hits.get("cochrane"),
        "search.hits.total":            total_hits or None,
        # Screening model provenance
        "provenance.abstract.model":          abs_model,
        "provenance.abstract.prompt_version": abs_pv,
        "provenance.fulltext.model":          ft_model,
        "provenance.fulltext.prompt_version": ft_pv,
        # Abstract screening
        "screen.abstract.n_total":      len(abstract_last),
        "screen.abstract.n_include":    n_abs_include,
        "screen.abstract.n_borderline": n_abs_borderline,
        "screen.abstract.n_exclude":    n_abs_exclude,
        # Fulltext screening
        "screen.fulltext.n_include":    n_included,
        "screen.fulltext.n_exclude":    n_ft_exclude,
        # Inter-rater agreement
        "kappa.abstract":               kappa_abs,
        "kappa.fulltext":               kappa_ft,
        # Top-level results
        "results.n_studies":            n_included,
        "results.n_studies_tka":        len(tka_rows),
        "results.n_studies_tha":        len(tha_rows),
        "results.n_studies_both":       len(both_rows),
        "results.n_countries":          _count_countries(coded_rows) or "—",
        "results.n_external_val":       n_ext_val,
        "results.pct_external_val":     pct_ext_val,
        # TKA results
        "results.tka.n_studies":        len(tka_rows),
        "results.tka.auc_min":          tka_auc_min,
        "results.tka.auc_max":          tka_auc_max,
        "results.tka.most_common_prom": _most_common_prom(tka_rows),
        "results.tka.n_internal_val":   tka_int_val,
        "results.tka.n_external_val":   tka_ext_val,
        # THA results
        "results.tha.n_studies":        len(tha_rows),
        "results.tha.auc_min":          tha_auc_min,
        "results.tha.auc_max":          tha_auc_max,
        # PROBAST
        "probast.n_low_overall":            n_low_overall,
        "probast.n_no_performance_metric":  n_no_metric,
    }


if __name__ == "__main__":
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stats = build_stats()
    out = _RESULTS_DIR / "manuscript_stats.json"
    out.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    print(f"Written {len(stats)} keys → {out}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v!r}")
