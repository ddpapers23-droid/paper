"""Europe PMC — abstract and PDF via the Europe PMC REST API.

Europe PMC (https://europepmc.org/) indexes biomedical and life science
literature from PubMed, PubMed Central, and 30+ other sources. No API
key required; providing a `mailto` header is polite-pool etiquette.

Abstract: REST search endpoint (`abstractText` field).
PDF: PMC fulltext render endpoint — only available for PMC Open Access
papers (those with a `pmcid` in the Europe PMC record).
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from pathlib import Path

from fetchers.base import AbstractFetcher, PdfFetcher

logger = logging.getLogger(__name__)

_SEARCH_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_PDF_BASE = "https://europepmc.org/backend/ptpmcrender.fcgi"


def _doi_safe(doi: str) -> str:
    return doi.replace("/", "_").replace(":", "_")


def _cache_pdf_path(cache_dir: str | Path, doi: str) -> Path:
    return Path(cache_dir) / f"{_doi_safe(doi)}.pdf"


class EuropePmcSource(AbstractFetcher, PdfFetcher):
    name = "europe_pmc"

    def _mailto(self) -> str:
        return (
            getattr(self.config, "crossref_mailto", None)
            or os.environ.get("CROSSREF_MAILTO", "")
        )

    def _search(self, doi: str) -> dict | None:
        """Query Europe PMC for a DOI; returns the first result dict."""
        query = urllib.parse.quote(f'DOI:"{doi}"', safe="")
        url = (
            f"{_SEARCH_BASE}/search?query={query}"
            "&resultType=core&format=json&pageSize=1"
        )
        headers: dict[str, str] = {}
        mailto = self._mailto()
        if mailto:
            headers["User-Agent"] = f"academic-research (mailto:{mailto})"
        try:
            resp = self.http.get(url, headers=headers, timeout=30)
        except Exception as e:
            logger.debug("europepmc search %s failed: %s", doi, e)
            return None
        if resp.status_code != 200:
            return None
        data = resp.json() or {}
        results = (data.get("resultList") or {}).get("result") or []
        if not results:
            return None
        return results[0]

    def fetch_abstract(self, doi: str, *, title=None, cache_dir=None) -> str | None:
        result = self._search(doi)
        if not result:
            return None
        abstract = (result.get("abstractText") or "").strip()
        return abstract if len(abstract) > 50 else None

    def fetch_pdf(
        self, doi: str, *, cache_dir, bypass_prefix_filter: bool = False,
    ) -> tuple[Path, str] | None:
        del bypass_prefix_filter
        path = _cache_pdf_path(cache_dir, doi)
        if path.exists():
            return path, f"cache://{path}"

        result = self._search(doi)
        if not result:
            return None
        pmcid = (result.get("pmcid") or "").strip()
        if not pmcid:
            return None

        pdf_url = f"{_PDF_BASE}?accid={pmcid}&blobtype=pdf"
        try:
            resp = self.http.get(pdf_url, timeout=60)
        except Exception as e:
            logger.debug("europepmc PDF %s (%s) failed: %s", doi, pmcid, e)
            return None
        if resp.status_code != 200 or resp.content[:4] != b"%PDF":
            return None

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return path, pdf_url
