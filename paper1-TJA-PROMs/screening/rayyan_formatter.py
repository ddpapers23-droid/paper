#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reformat the preliminary screen into Rayyan bulk-import CSV format.

Rayyan's CSV importer expects (among others) the columns: key, title,
authors, journal, year, volume, pages, abstract, url. Volume and pages
are not collected by search_config.py (PubMed esearch/efetch fields are
PMID/Title/Authors/Year/Journal/Abstract only), so those two columns are
written blank rather than fabricated. PRELIM_DECISION is carried over as
a Rayyan label-friendly "notes" style column is intentionally NOT added
here — Rayyan's own inclusion/exclusion tagging is the source of truth
for the human screen; the preliminary decision stays in prelim_screen.csv.

Usage:
    uv run rayyan_formatter.py
    uv run rayyan_formatter.py --input prelim_screen.csv --output rayyan_import.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

RAYYAN_FIELDNAMES = ["key", "title", "authors", "journal", "year", "volume", "pages", "abstract", "url"]

PUBMED_URL_TEMPLATE = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="prelim_screen.csv")
    parser.add_argument("--output", default="rayyan_import.csv")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / args.input
    output_path = base_dir / args.output

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    rayyan_rows = []
    for row in records:
        pmid = row.get("PMID", "").strip()
        rayyan_rows.append(
            {
                "key": pmid,
                "title": row.get("Title", ""),
                "authors": row.get("Authors", ""),
                "journal": row.get("Journal", ""),
                "year": row.get("Year", ""),
                "volume": "",
                "pages": "",
                "abstract": row.get("Abstract", ""),
                "url": PUBMED_URL_TEMPLATE.format(pmid=pmid) if pmid else "",
            }
        )

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAYYAN_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rayyan_rows)

    print(f"Converted {len(rayyan_rows)} records to Rayyan bulk-import format.")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
