#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests>=2.31",
# ]
# ///
"""PubMed search for the AI/ML-PROMs-after-TJA systematic review.

Queries NCBI E-utilities (esearch + efetch) with the project's Boolean
string, restricted to the 2010-01-01..2026-05-20 publication-date window,
and writes one row per PMID to results_pubmed.csv.

No API key is required at this query volume (NCBI allows 3 req/s
unauthenticated). If an NCBI_API_KEY env var is set, it is sent along
and the rate limit is raised to 10 req/s.

Usage:
    uv run search_config.py
    uv run search_config.py --max-results 500 --output results_pubmed.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Boolean search string exactly as drafted for this review.
QUERY = (
    '("total knee arthroplasty"[tiab] OR "total hip arthroplasty"[tiab] '
    'OR "TKA"[tiab] OR "THA"[tiab] OR "knee replacement"[tiab] '
    'OR "hip replacement"[tiab]) AND ("machine learning"[tiab] '
    'OR "artificial intelligence"[tiab] OR "deep learning"[tiab] '
    'OR "random forest"[tiab] OR "neural network"[tiab] '
    'OR "gradient boosting"[tiab] OR "XGBoost"[tiab]) AND '
    '("patient-reported outcome"[tiab] OR "PROM"[tiab] OR "KOOS"[tiab] '
    'OR "HOOS"[tiab] OR "WOMAC"[tiab] OR "functional outcome"[tiab] '
    'OR "MCID"[tiab])'
)

DATE_MIN = "2010/01/01"
DATE_MAX = "2026/05/20"
DEFAULT_MAX_RESULTS = 500
FIELDNAMES = ["PMID", "Title", "Authors", "Year", "Journal", "Abstract"]
EFETCH_BATCH_SIZE = 200


def _request_delay(api_key: str | None) -> float:
    # NCBI: 3 req/s without a key, 10 req/s with one.
    return 0.11 if api_key else 0.35


def esearch_pmids(query: str, max_results: int, api_key: str | None) -> tuple[list[str], int]:
    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "mindate": DATE_MIN,
        "maxdate": DATE_MAX,
        "retmax": max_results,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key
    resp = requests.get(f"{EUTILS_BASE}/esearch.fcgi", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()["esearchresult"]
    total = int(data.get("count", 0))
    return data.get("idlist", []), total


def _text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def _parse_article(article_elem: ET.Element) -> dict[str, str]:
    pmid = _text(article_elem.find(".//PMID"))

    title = _text(article_elem.find(".//Article/ArticleTitle"))

    authors = []
    for author in article_elem.findall(".//AuthorList/Author"):
        last = _text(author.find("LastName"))
        initials = _text(author.find("Initials"))
        collective = _text(author.find("CollectiveName"))
        if last:
            authors.append(f"{last} {initials}".strip())
        elif collective:
            authors.append(collective)
    authors_str = "; ".join(authors)

    year = _text(article_elem.find(".//Article/Journal/JournalIssue/PubDate/Year"))
    if not year:
        medline_date = _text(article_elem.find(".//Article/Journal/JournalIssue/PubDate/MedlineDate"))
        year = medline_date[:4] if medline_date else ""

    journal = _text(article_elem.find(".//Article/Journal/Title"))
    if not journal:
        journal = _text(article_elem.find(".//Article/Journal/ISOAbbreviation"))

    abstract_parts = [_text(node) for node in article_elem.findall(".//Abstract/AbstractText")]
    abstract = " ".join(part for part in abstract_parts if part)

    return {
        "PMID": pmid,
        "Title": title,
        "Authors": authors_str,
        "Year": year,
        "Journal": journal,
        "Abstract": abstract,
    }


def efetch_records(pmids: list[str], api_key: str | None) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    delay = _request_delay(api_key)

    for start in range(0, len(pmids), EFETCH_BATCH_SIZE):
        batch = pmids[start : start + EFETCH_BATCH_SIZE]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
            "rettype": "abstract",
        }
        if api_key:
            params["api_key"] = api_key

        resp = requests.post(f"{EUTILS_BASE}/efetch.fcgi", data=params, timeout=60)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for article_elem in root.findall(".//PubmedArticle"):
            records.append(_parse_article(article_elem))

        time.sleep(delay)

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--output", default="results_pubmed.csv")
    args = parser.parse_args()

    api_key = os.environ.get("NCBI_API_KEY")
    output_path = Path(__file__).resolve().parent / args.output

    print("Searching PubMed (E-utilities esearch)...")
    pmids, total_found = esearch_pmids(QUERY, args.max_results, api_key)
    print(f"Total records matching query: {total_found}")
    print(f"Fetching details for {len(pmids)} PMIDs (retmax={args.max_results})...")

    if not pmids:
        with output_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()
        print(f"Wrote 0 records to {output_path}")
        print("Total record count: 0")
        return 0

    records = efetch_records(pmids, api_key)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {len(records)} records to {output_path}")
    print(f"Total record count: {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
