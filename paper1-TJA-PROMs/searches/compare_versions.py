#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compare the v1 (original) and v2 (sensitivity-expanded) PubMed searches.

Reads the raw / deduped / screened CSVs for both query versions and
prints a funnel comparison, plus which PMIDs v2 turned up that v1's
deduped set didn't ("net new" — the whole point of widening the query).

Does not modify any files. Run this after search_config.py --version v2,
dedup.py, and screening_config.py have all been run against the v2
outputs.

Usage:
    uv run compare_versions.py
    uv run compare_versions.py --v1-raw results_pubmed.csv --v2-raw results_pubmed_v2.csv ...
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _count_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def _pmid_set(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["PMID"].strip() for row in csv.DictReader(f) if row.get("PMID", "").strip()}


def _prelim_include_pmids(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as f:
        return {
            row["PMID"].strip()
            for row in csv.DictReader(f)
            if row.get("PRELIM_DECISION") == "PRELIM_INCLUDE" and row.get("PMID", "").strip()
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base_dir = Path(__file__).resolve().parent
    screening_dir = base_dir.parent / "screening"

    parser.add_argument("--v1-raw", default=str(base_dir / "results_pubmed.csv"))
    parser.add_argument("--v1-deduped", default=str(base_dir / "results_deduped.csv"))
    parser.add_argument("--v1-screened", default=str(screening_dir / "prelim_screen.csv"))
    parser.add_argument("--v2-raw", default=str(base_dir / "results_pubmed_v2.csv"))
    parser.add_argument("--v2-deduped", default=str(base_dir / "results_deduped_v2.csv"))
    parser.add_argument("--v2-screened", default=str(screening_dir / "prelim_screen_v2.csv"))
    args = parser.parse_args()

    v1_raw, v1_deduped, v1_screened = Path(args.v1_raw), Path(args.v1_deduped), Path(args.v1_screened)
    v2_raw, v2_deduped, v2_screened = Path(args.v2_raw), Path(args.v2_deduped), Path(args.v2_screened)

    for p in (v1_raw, v1_deduped, v1_screened, v2_raw, v2_deduped, v2_screened):
        if not p.exists():
            print(f"ERROR: expected file not found: {p}")
            print("Run search_config.py / dedup.py / screening_config.py for both versions first.")
            return 1

    v1_total = _count_rows(v1_raw)
    v1_unique = _count_rows(v1_deduped)
    v1_include = len(_prelim_include_pmids(v1_screened))

    v2_total = _count_rows(v2_raw)
    v2_unique = _count_rows(v2_deduped)
    v2_include = len(_prelim_include_pmids(v2_screened))

    v1_pmids = _pmid_set(v1_deduped)
    v2_pmids = _pmid_set(v2_deduped)
    net_new_pmids = v2_pmids - v1_pmids
    net_new_include_pmids = net_new_pmids & _prelim_include_pmids(v2_screened)

    print(f"v1: {v1_total} total -> {v1_unique} unique -> {v1_include} PRELIM_INCLUDE")
    print(f"v2: {v2_total} total -> {v2_unique} unique -> {v2_include} PRELIM_INCLUDE")
    print(f"Net new records added by v2: {len(net_new_pmids)}")
    print(f"  of which PRELIM_INCLUDE: {len(net_new_include_pmids)}")
    if net_new_pmids:
        preview = ", ".join(sorted(net_new_pmids)[:20])
        suffix = ", ..." if len(net_new_pmids) > 20 else ""
        print(f"  net-new PMIDs: {preview}{suffix}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
