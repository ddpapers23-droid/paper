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
and writes one row per PMID to a CSV.

Two query versions are available via --version:
    v1 - original string ([tiab] only). Default output: results_pubmed.csv
    v2 - wider-sensitivity string: adds MeSH terms for the joint/ML
         blocks, and expands the PROM and ML/AI term blocks (Oxford
         scores, EQ5D, SF-36, pain/satisfaction/QoL/VAS terms;
         prediction/classification/supervised-learning/NLP terms).
         Default output: results_pubmed_v2.csv

No API key is required at this query volume (NCBI allows 3 req/s
unauthenticated). If an NCBI_API_KEY env var is set, it is sent along
and the rate limit is raised to 10 req/s.

Usage:
    uv run search_config.py
    uv run search_config.py --version v2
    uv run search_config.py --version v2 --max-results 1000 --output results_pubmed_v2.csv
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

# Boolean search string exactly as originally drafted for this review.
QUERY_V1 = (
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

# Wider-sensitivity string: v1's three blocks, each expanded with MeSH
# terms and/or additional [tiab] synonyms, joined with the same AND
# structure as v1.
QUERY_V2 = (
    '("total knee arthroplasty"[tiab] OR "total hip arthroplasty"[tiab] '
    'OR "TKA"[tiab] OR "THA"[tiab] OR "knee replacement"[tiab] '
    'OR "hip replacement"[tiab] OR "arthroplasty, replacement, knee"[MeSH] '
    'OR "arthroplasty, replacement, hip"[MeSH]) AND '
    '("machine learning"[tiab] OR "artificial intelligence"[tiab] '
    'OR "deep learning"[tiab] OR "random forest"[tiab] '
    'OR "neural network"[tiab] OR "gradient boosting"[tiab] '
    'OR "XGBoost"[tiab] OR "machine learning"[MeSH] '
    'OR "artificial intelligence"[MeSH] OR "prediction model"[tiab] '
    'OR "predictive model"[tiab] OR "logistic regression"[tiab] '
    'OR "classification model"[tiab] OR "supervised learning"[tiab] '
    'OR "ensemble learning"[tiab] OR "natural language processing"[tiab] '
    'OR "NLP"[tiab]) AND '
    '("patient-reported outcome"[tiab] OR "PROM"[tiab] OR "KOOS"[tiab] '
    'OR "HOOS"[tiab] OR "WOMAC"[tiab] OR "functional outcome"[tiab] '
    'OR "MCID"[tiab] OR "Oxford knee score"[tiab] '
    'OR "Oxford hip score"[tiab] OR "EQ5D"[tiab] OR "SF-36"[tiab] '
    'OR "pain score"[tiab] OR "patient satisfaction"[tiab] '
    'OR "quality of life"[tiab] OR "VAS"[tiab] '
    'OR "visual analogue scale"[tiab])'
)

QUERIES = {"v1": QUERY_V1, "v2": QUERY_V2}
DEFAULT_OUTPUTS = {"v1": "results_pubmed.csv", "v2": "results_pubmed_v2.csv"}

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
    parser.add_argument("--version", choices=["v1", "v2"], default="v1")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    query = QUERIES[args.version]
    output_name = args.output or DEFAULT_OUTPUTS[args.version]

    api_key = os.environ.get("NCBI_API_KEY")
    output_path = Path(__file__).resolve().parent / output_name

    print(f"Searching PubMed (E-utilities esearch) — query {args.version}...")
    pmids, total_found = esearch_pmids(query, args.max_results, api_key)
    print(f"Total records matching query: {total_found}")
    if total_found > args.max_results:
        print(
            f"WARNING: {total_found} records matched but only {args.max_results} were "
            f"fetched (--max-results). Re-run with --max-results {total_found} to capture "
            "the full set."
        )
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
