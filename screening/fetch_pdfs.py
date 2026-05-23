#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31"]
# ///
"""Try to download open-access PDFs for all included papers.

Sources tried in order:
  1. Unpaywall API (oa_url / best_oa_location)
  2. Semantic Scholar Graph API (openAccessPdf)
  3. Europe PMC (for PMC-indexed articles)

Downloads to screening/pdfs/<doi_slug>.pdf
Already-downloaded files are skipped.

Usage:
    uv run screening/fetch_pdfs.py
    uv run screening/fetch_pdfs.py --email you@example.com
"""
from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parent.parent
_SCREENING = _ROOT / "screening"
_PDF_DIR = _SCREENING / "pdfs"
_INCLUDE_CSV = _SCREENING / "fulltext_review.csv"

UNPAYWALL = "https://api.unpaywall.org/v2/{doi}?email={email}"
S2_PAPER  = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf"
EPMC      = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{doi}&format=json&resultType=core"


def _doi_slug(doi: str) -> str:
    return re.sub(r"[^\w.-]", "_", doi)[:120]


def _download(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "systematic-review-bot/1.0"})
        if r.status_code == 200 and b"%PDF" in r.content[:8]:
            dest.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def _try_unpaywall(doi: str, email: str, dest: Path) -> bool:
    try:
        r = requests.get(UNPAYWALL.format(doi=doi, email=email), timeout=15)
        if r.status_code != 200:
            return False
        data = r.json()
        # Try best_oa_location first, then oa_url
        best = data.get("best_oa_location") or {}
        url = best.get("url_for_pdf") or data.get("oa_url")
        if url and _download(url, dest):
            return True
        # Try all OA locations
        for loc in data.get("oa_locations", []):
            url = loc.get("url_for_pdf")
            if url and _download(url, dest):
                return True
    except Exception:
        pass
    return False


def _try_s2(doi: str, dest: Path) -> bool:
    try:
        r = requests.get(S2_PAPER.format(doi=doi), timeout=15)
        if r.status_code != 200:
            return False
        url = (r.json().get("openAccessPdf") or {}).get("url")
        if url:
            return _download(url, dest)
    except Exception:
        pass
    return False


def _try_epmc(doi: str, dest: Path) -> bool:
    try:
        r = requests.get(EPMC.format(doi=doi), timeout=15)
        if r.status_code != 200:
            return False
        results = r.json().get("resultList", {}).get("result", [])
        for hit in results:
            pmcid = hit.get("pmcid")
            if pmcid:
                url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
                if _download(url, dest):
                    return True
    except Exception:
        pass
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="ddpapers23@gmail.com",
                        help="Email for Unpaywall API (required by their ToS)")
    args = parser.parse_args()

    _PDF_DIR.mkdir(parents=True, exist_ok=True)

    # Load included papers from fulltext_review.csv
    papers = []
    with open(_INCLUDE_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doi = (row.get("doi") or "").strip().lower()
            doi = re.sub(r"https?://(?:dx\.)?doi\.org/", "", doi)
            if doi:
                papers.append({"num": row["#"], "title": row["title"][:60], "doi": doi})

    print(f"Papers with DOI: {len(papers)}")
    got, skipped, failed = 0, 0, 0

    for p in papers:
        doi = p["doi"]
        slug = _doi_slug(doi)
        dest = _PDF_DIR / f"{slug}.pdf"

        if dest.exists():
            skipped += 1
            continue

        print(f"  #{p['num']} {p['title'][:55]}...", end=" ", flush=True)

        if _try_unpaywall(doi, args.email, dest):
            print("✓ Unpaywall")
            got += 1
        elif _try_s2(doi, dest):
            print("✓ S2")
            got += 1
        elif _try_epmc(doi, dest):
            print("✓ EPMC")
            got += 1
        else:
            print("✗ not OA")
            failed += 1

        time.sleep(0.3)

    print(f"\nDownloaded: {got}  |  Already had: {skipped}  |  Not OA: {failed}")
    print(f"PDFs saved to: {_PDF_DIR}")
    print(f"\nFor papers not downloaded, get the PDF via your institution")
    print(f"and save as: screening/pdfs/<any-name>.pdf")
    print(f"The extractor matches by DOI embedded in the filename or PDF metadata.")


if __name__ == "__main__":
    main()
