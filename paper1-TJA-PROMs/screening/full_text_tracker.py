#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openpyxl>=3.1",
#     "requests>=2.31",
# ]
# ///
"""Full-text screening tracker for the AI/ML-PROMs-after-TJA review.

Takes the final Include list exported from Rayyan (CSV) and builds an
Excel tracker for the full-text eligibility pass: one row per study,
with columns to confirm the record actually has an ML algorithm, a
PROM outcome, and a reported performance metric once someone has read
the full text (title/abstract screening only checked for these terms
being *mentioned*, not confirmed).

Records with no PubMed Central full-text link are pre-flagged "Needs
retrieval" in the Full Text Retrieved column, since there's no free
full text to click through from PubMed — someone has to source the
PDF some other way (publisher site, institutional access, ILL). PMC
availability is checked two ways: first the CSV's own `pmc_id` column
(free, no network) — but in practice this is usually blank for records
whose metadata came in via PubMed E-utilities rather than Rayyan's own
PubMed connector, since E-utilities esearch/efetch don't return PMC
IDs. So for any row without a `pmc_id`, this script also does a live
lookup via NCBI ELink (dbfrom=pubmed, db=pmc) on eutils.ncbi.nlm.nih.gov
— the same domain and request pattern search_config.py already uses
successfully. (An earlier version of this script used the PMC ID
Converter API on pmc.ncbi.nlm.nih.gov instead; that domain 403's
Python's requests client outright — looks like bot/WAF protection —
so it's not used here.) One ELink request per PMID, to avoid relying
on undocumented assumptions about how ELink batches/merges linksets
for multiple input IDs in one request. Use --no-network to skip the
live lookup and rely on the CSV's `pmc_id` column alone (faster, but
will over-flag).

Expects a standard Rayyan CSV export (key, title, year, journal,
pubmed_id, pmc_id, notes, url, ...). If `pubmed_id` is blank for a row,
falls back to parsing the PMID out of the `url` column.

If the input's `notes` column parses as containing RAYYAN-INCLUSION
data and any row's decision (for any reviewer) isn't "Included", prints
a warning — this script assumes you've already filtered to the final
include set before exporting, and an unfiltered export is a common
mistake.

Usage:
    uv run full_text_tracker.py --input rayyan_includes_export.csv
    uv run full_text_tracker.py --input rayyan_includes_export.csv --output fulltext_tracker.xlsx
    uv run full_text_tracker.py --input rayyan_includes_export.csv --no-network
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"

COLUMNS = [
    "PMID",
    "Title",
    "Journal",
    "Year",
    "Full Text Retrieved (Yes/No)",
    "ML Algorithm Confirmed",
    "PROM Confirmed",
    "Metric Confirmed",
    "Full Text Decision (Include/Exclude)",
    "Exclusion Reason",
    "Notes",
]

FULL_TEXT_OPTIONS = ["Yes", "No", "Needs retrieval"]
CONFIRMED_OPTIONS = ["Yes", "No"]
DECISION_OPTIONS = ["Include", "Exclude"]

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF")
WRAP_ALIGN = Alignment(wrap_text=True, vertical="top")

PMID_FROM_URL_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
RAYYAN_INCLUSION_RE = re.compile(r'RAYYAN-INCLUSION:\s*\{([^}]*)\}')
RAYYAN_PAIR_RE = re.compile(r'"([^"]+)"\s*=>\s*"([^"]*)"')


def _extract_pmid(row: dict[str, str]) -> str:
    pmid = (row.get("pubmed_id") or "").strip()
    if pmid:
        return pmid
    match = PMID_FROM_URL_RE.search(row.get("url", "") or "")
    return match.group(1) if match else ""


def _warn_if_not_all_included(rows: list[dict[str, str]]) -> None:
    non_included = 0
    checked = 0
    for row in rows:
        notes = row.get("notes", "") or ""
        match = RAYYAN_INCLUSION_RE.search(notes)
        if not match:
            continue
        for _, decision in RAYYAN_PAIR_RE.findall(match.group(1)):
            checked += 1
            if decision.strip() != "Included":
                non_included += 1
                break
    if checked and non_included:
        print(
            f"WARNING: {non_included} of {checked} rows with parseable Rayyan decisions "
            "are NOT marked 'Included' by every reviewer found. This script assumes the "
            "input is already filtered to the final include list — double-check you "
            "exported/filtered correctly in Rayyan before trusting this tracker."
        )


def check_pmc_availability(pmids: list[str]) -> dict[str, bool]:
    """Look up which PMIDs have a real PMC full-text link via NCBI ELink.

    One request per PMID rather than a batched multi-ID call: ELink's
    behavior when merging linksets for multiple input IDs in a single
    request isn't something to rely on without being able to verify it
    live, and getting a PMID-to-PMC mapping wrong silently is worse than
    373 slow-but-unambiguous requests.
    """
    api_key = os.environ.get("NCBI_API_KEY")
    delay = 0.11 if api_key else 0.35
    available: dict[str, bool] = {}

    for i, pmid in enumerate(pmids, start=1):
        params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "json"}
        if api_key:
            params["api_key"] = api_key

        resp = requests.get(ELINK_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        linksets = data.get("linksets", [])
        has_pmc = False
        if linksets:
            for linksetdb in linksets[0].get("linksetdbs", []):
                if linksetdb.get("dbto") == "pmc" and linksetdb.get("links"):
                    has_pmc = True
                    break
        available[pmid] = has_pmc

        if i % 50 == 0 or i == len(pmids):
            print(f"  ...checked {i}/{len(pmids)}")

        time.sleep(delay)

    return available


def load_records(input_path: Path, use_network: bool) -> list[dict[str, str]]:
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    _warn_if_not_all_included(rows)

    parsed = []
    for row in rows:
        parsed.append(
            {
                "PMID": _extract_pmid(row),
                "Title": row.get("title", ""),
                "Journal": row.get("journal", ""),
                "Year": row.get("year", ""),
                "has_pmc_id_in_csv": bool((row.get("pmc_id") or "").strip()),
            }
        )

    if use_network:
        lookup_pmids = [r["PMID"] for r in parsed if not r["has_pmc_id_in_csv"] and r["PMID"]]
        if lookup_pmids:
            print(f"Checking PMC full-text availability for {len(lookup_pmids)} PMIDs via NCBI ELink (one request per PMID, this may take a few minutes)...")
            try:
                pmc_available = check_pmc_availability(lookup_pmids)
            except requests.exceptions.RequestException as exc:
                print(f"WARNING: PMC availability lookup failed ({exc}); falling back to CSV pmc_id only.")
                pmc_available = {}
        else:
            pmc_available = {}
    else:
        pmc_available = {}

    records = []
    for r in parsed:
        has_pmc = r["has_pmc_id_in_csv"] or pmc_available.get(r["PMID"], False)
        records.append(
            {
                "PMID": r["PMID"],
                "Title": r["Title"],
                "Journal": r["Journal"],
                "Year": r["Year"],
                "needs_retrieval": not has_pmc,
            }
        )
    return records


def _autofit_columns(ws, headers: list[str], min_width: int = 12, max_width: int = 42) -> None:
    for idx, header in enumerate(headers, start=1):
        width = max(min_width, min(max_width, len(header) + 4))
        ws.column_dimensions[get_column_letter(idx)].width = width


def build_workbook(records: list[dict[str, str]]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Full Text Tracker"

    for col_idx, header in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")

    ws.freeze_panes = "A2"
    _autofit_columns(ws, COLUMNS)
    ws.row_dimensions[1].height = 32

    col = {name: idx + 1 for idx, name in enumerate(COLUMNS)}

    for row_idx, record in enumerate(records, start=2):
        ws.cell(row=row_idx, column=col["PMID"], value=record["PMID"])
        ws.cell(row=row_idx, column=col["Title"], value=record["Title"])
        ws.cell(row=row_idx, column=col["Journal"], value=record["Journal"])
        ws.cell(row=row_idx, column=col["Year"], value=record["Year"])
        if record["needs_retrieval"]:
            ws.cell(row=row_idx, column=col["Full Text Retrieved (Yes/No)"], value="Needs retrieval")
        for c in range(1, len(COLUMNS) + 1):
            ws.cell(row=row_idx, column=c).alignment = WRAP_ALIGN

    last_row = len(records) + 1

    def add_dropdown(column_name: str, options: list[str]) -> None:
        col_letter = get_column_letter(col[column_name])
        dv = DataValidation(
            type="list",
            formula1=f'"{",".join(options)}"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="Invalid entry",
            error=f"Choose one of: {', '.join(options)}",
        )
        ws.add_data_validation(dv)
        dv.add(f"{col_letter}2:{col_letter}{last_row}")

    add_dropdown("Full Text Retrieved (Yes/No)", FULL_TEXT_OPTIONS)
    add_dropdown("ML Algorithm Confirmed", CONFIRMED_OPTIONS)
    add_dropdown("PROM Confirmed", CONFIRMED_OPTIONS)
    add_dropdown("Metric Confirmed", CONFIRMED_OPTIONS)
    add_dropdown("Full Text Decision (Include/Exclude)", DECISION_OPTIONS)

    return wb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="Rayyan CSV export filtered to the final Include list")
    parser.add_argument("--output", default="fulltext_tracker.xlsx")
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Skip the live NCBI PMC lookup; rely on the CSV's pmc_id column alone (will over-flag if it's blank)",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / args.input
    output_path = base_dir / args.output

    records = load_records(input_path, use_network=not args.no_network)
    needs_retrieval_count = sum(1 for r in records if r["needs_retrieval"])

    wb = build_workbook(records)
    wb.save(output_path)

    print(f"Loaded {len(records)} records from {input_path}")
    print(f"Flagged 'Needs retrieval' (no PMC full-text link): {needs_retrieval_count}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
