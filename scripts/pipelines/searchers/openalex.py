"""OpenAlex REST API search.

When both BLOCK_A_TERMS and BLOCK_B_TERMS are present, runs a single
ANDed query: (A1 OR A2 ...) AND (B1 OR B2 ...).  This mirrors the
PubMed/Scopus three-concept AND strategy and avoids the 10k-cap
explosion that occurs when each block is run independently against
broad AI/ML or arthroplasty term sets.  Free tier; no API key required.
"""

from __future__ import annotations

import time

import requests

from .base import SearchContext, SearchSource, empty_row

PER_PAGE = 200           # OpenAlex max
RATE_LIMIT_SLEEP = 0.2   # polite pool delay between requests


class OpenAlexSearch(SearchSource):
    name = "openalex"
    supports_journal_scope = True
    supports_block_queries = True

    def run(self, config, ctx: SearchContext) -> list[dict]:
        filter_str = self._build_filter(ctx.issns, ctx.from_year, ctx.to_year)

        a_terms = getattr(config, "BLOCK_A_TERMS", None) or []
        b_terms = getattr(config, "BLOCK_B_TERMS", None) or []
        c_terms = getattr(config, "BLOCK_C_TERMS", None) or []
        if not a_terms and not b_terms:
            return []

        # Build ANDed query across all blocks: (A) AND (B) AND (C ...)
        parts: list[str] = []
        if a_terms:
            parts.append("(" + " OR ".join(f'"{t}"' for t in a_terms) + ")")
        if b_terms:
            parts.append("(" + " OR ".join(f'"{t}"' for t in b_terms) + ")")
        if c_terms:
            parts.append("(" + " OR ".join(f'"{t}"' for t in c_terms) + ")")
        query = " AND ".join(parts)

        print("  OpenAlex combined: ", end="", flush=True)
        works = self._fetch_all(query, filter_str, ctx.mailto)
        print(f"{len(works)} results", flush=True)
        return [self._work_to_row(w, "combined") for w in works]

    def _build_filter(self, issns: list[str], from_year: int,
                      to_year: int) -> str:
        parts = [f"publication_year:{from_year}-{to_year}", "type:article"]
        if issns:
            parts.insert(0, f"primary_location.source.issn:{'|'.join(issns)}")
        return ",".join(parts)

    def _fetch_all(self, query: str, filter_str: str, mailto: str) -> list[dict]:
        all_works: list[dict] = []
        page = 1
        total: int | None = None
        while True:
            data = self._fetch_page(query, filter_str, page, mailto)
            if total is None:
                total = data["meta"]["count"]
            results = data.get("results", [])
            if not results:
                break
            all_works.extend(results)
            if page * PER_PAGE >= min(total, 10000):
                break
            page += 1
            time.sleep(RATE_LIMIT_SLEEP)
        return all_works

    def _fetch_page(self, query: str, filter_str: str, page: int,
                    mailto: str) -> dict:
        params: dict = {
            "search": query,
            "filter": filter_str,
            "page": page,
            "per_page": PER_PAGE,
            "select": ",".join([
                "id", "doi", "title", "publication_year", "publication_date",
                "cited_by_count", "type", "authorships",
                "primary_location", "open_access", "abstract_inverted_index",
            ]),
        }
        if mailto:
            params["mailto"] = mailto
        resp = requests.get("https://api.openalex.org/works",
                            params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _work_to_row(self, w: dict, label: str) -> dict:
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        primary = w.get("primary_location") or {}
        src = primary.get("source") or {}
        oa = w.get("open_access") or {}
        authorships = w.get("authorships") or []
        authors = "; ".join(
            a.get("author", {}).get("display_name", "")
            for a in authorships
            if a.get("author", {}).get("display_name")
        )
        abstract = self._reconstruct_abstract(w.get("abstract_inverted_index"))
        year_str = str(w.get("publication_year", "") or "")

        row = empty_row()
        row.update({
            "db": self.name,
            "query": label,
            "doi": doi,
            "title": w.get("title", "") or "",
            "authors": authors,
            "year": year_str,
            "source": src.get("display_name", "") or "",
            "issn": src.get("issn_l", "") or "",
            "cited_by": w.get("cited_by_count", 0) or 0,
            "openalex_id": w.get("id", "") or "",
            "abstract": abstract,
            "oa_status": oa.get("oa_status", "") or "",
            "oa_url": oa.get("oa_url", "") or "",
        })
        return row

    def _reconstruct_abstract(self, inverted_index: dict | None) -> str:
        """Rebuild plaintext from OpenAlex inverted index.

        Note: OpenAlex abstracts are often reconstructed from GROBID
        full-text parsing and may contain body-text fragments rather
        than the paper's real abstract. Downstream `fetch_abstracts.py`
        (or its successor) re-fetches proper abstracts from Crossref /
        Semantic Scholar / Scopus; this is a best-effort starting
        point for the search CSV only.
        """
        if not inverted_index:
            return ""
        positions: list[tuple[int, str]] = []
        for word, ps in inverted_index.items():
            for p in ps:
                positions.append((p, word))
        positions.sort()
        return " ".join(w for _, w in positions)
