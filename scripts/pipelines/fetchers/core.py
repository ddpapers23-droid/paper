"""CORE — abstract and PDF via the CORE Aggregate API (v3).

CORE (https://core.ac.uk/) aggregates open-access research outputs from
thousands of repositories and journals. The v3 API provides full-text
metadata including abstracts and PDF download URLs.

Set `CORE_API_KEY` for 100 req/min authenticated access; unauthenticated
requests are accepted but rate-limited to ~10 req/min.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from pathlib import Path

from fetchers.base import AbstractFetcher, PdfFetcher

logger = logging.getLogger(__name__)

_API_BASE = "https://api.core.ac.uk/v3"


def _doi_safe(doi: str) -> str:
    return doi.replace("/", "_").replace(":", "_")


def _cache_pdf_path(cache_dir: str | Path, doi: str) -> Path:
    return Path(cache_dir) / f"{_doi_safe(doi)}.pdf"


class CoreSource(AbstractFetcher, PdfFetcher):
    name = "core"

    def _api_key(self) -> str:
        return (
            getattr(self.config, "core_api_key", None)
            or os.environ.get("CORE_API_KEY", "")
        )

    def _headers(self) -> dict[str, str]:
        api_key = self._api_key()
        if api_key:
            return {"Authorization": f"Bearer {api_key}"}
        return {}

    def _search_work(self, doi: str) -> dict | None:
        """Search CORE for a work by DOI; returns first matching result."""
        query = urllib.parse.quote(f'doi:"{doi}"', safe="")
        url = f"{_API_BASE}/search/works?q={query}&limit=1"
        try:
            resp = self.http.get(url, headers=self._headers(), timeout=30)
        except Exception as e:
            logger.debug("core search %s failed: %s", doi, e)
            return None
        if resp.status_code != 200:
            return None
        data = resp.json() or {}
        results = data.get("results") or []
        if not results:
            return None
        hit = results[0]
        # Verify DOI matches to avoid false positives from loose text search.
        raw_doi = (hit.get("doi") or "").strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/"):
            if raw_doi.startswith(prefix):
                raw_doi = raw_doi[len(prefix):]
                break
        if raw_doi and raw_doi != doi.strip().lower():
            return None
        return hit

    def fetch_abstract(self, doi: str, *, title=None, cache_dir=None) -> str | None:
        work = self._search_work(doi)
        if not work:
            return None
        abstract = (work.get("abstract") or "").strip()
        return abstract if len(abstract) > 50 else None

    def fetch_pdf(
        self, doi: str, *, cache_dir, bypass_prefix_filter: bool = False,
    ) -> tuple[Path, str] | None:
        del bypass_prefix_filter
        path = _cache_pdf_path(cache_dir, doi)
        if path.exists():
            return path, f"cache://{path}"

        work = self._search_work(doi)
        if not work:
            return None

        download_url = (work.get("downloadUrl") or "").strip()
        if not download_url:
            return None

        try:
            resp = self.http.get(download_url, timeout=60)
        except Exception as e:
            logger.debug("core PDF download %s failed: %s", download_url, e)
            return None
        if resp.status_code != 200 or resp.content[:4] != b"%PDF":
            return None

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return path, download_url
