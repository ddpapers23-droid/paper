#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rapidfuzz>=3.6",
# ]
# ///
"""Deduplicate PubMed search results.

Pass 1: exact PMID match (keep first occurrence).
Pass 2: fuzzy title match on the PMID-deduplicated set, using a
normalized-title similarity threshold of 90% (rapidfuzz token_sort_ratio,
falling back to difflib.SequenceMatcher if rapidfuzz is unavailable).

Usage:
    uv run dedup.py
    uv run dedup.py --input results_pubmed.csv --output results_deduped.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    from rapidfuzz import fuzz

    def _title_similarity(a: str, b: str) -> float:
        return fuzz.token_sort_ratio(a, b)

except ImportError:  # pragma: no cover - exercised only without rapidfuzz installed
    from difflib import SequenceMatcher

    def _title_similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100

FUZZY_THRESHOLD = 90.0


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def dedup_by_pmid(records: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    kept = []
    for row in records:
        pmid = row.get("PMID", "").strip()
        if pmid and pmid in seen:
            continue
        if pmid:
            seen.add(pmid)
        kept.append(row)
    return kept


def dedup_by_fuzzy_title(records: list[dict[str, str]]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    kept_norm_titles: list[str] = []

    for row in records:
        norm_title = normalize_title(row.get("Title", ""))
        is_dup = False
        if norm_title:
            for existing in kept_norm_titles:
                if _title_similarity(norm_title, existing) >= FUZZY_THRESHOLD:
                    is_dup = True
                    break
        if not is_dup:
            kept.append(row)
            kept_norm_titles.append(norm_title)

    return kept


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="results_pubmed.csv")
    parser.add_argument("--output", default="results_deduped.csv")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / args.input
    output_path = base_dir / args.output

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        records = list(reader)

    total_input = len(records)

    after_pmid = dedup_by_pmid(records)
    after_fuzzy = dedup_by_fuzzy_title(after_pmid)

    duplicates_removed = total_input - len(after_fuzzy)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(after_fuzzy)

    print(f"Total input records: {total_input}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Unique records remaining: {len(after_fuzzy)}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
