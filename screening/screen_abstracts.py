#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic>=0.30", "requests>=2.31"]
# ///
"""Standalone abstract screener — reads search CSVs, writes decisions.

Bypasses Zotero; reads directly from search_results.csv + pubmed_export.nbib
and writes to abstract_screening.csv in the format manuscript_stats.py expects.

Usage (from project root):
    uv run screening/screen_abstracts.py
    uv run screening/screen_abstracts.py --dry-run        # no API calls
    uv run screening/screen_abstracts.py --sample 20      # test on 20 papers
    uv run screening/screen_abstracts.py --workers 4      # parallel workers

Resumable: already-decided item_keys are skipped on re-run.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import importlib.util
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCREENING = _ROOT / "screening"
_OUT_CSV = _SCREENING / "abstract_screening.csv"

OUTPUT_FIELDS = [
    "item_key", "title", "authors", "year", "source", "doi",
    "decision", "reason", "model", "prompt_version", "screened_at",
]


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_screening_config():
    path = _ROOT / "screening_config.py"
    spec = importlib.util.spec_from_file_location("screening_config", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Input parsers
# ---------------------------------------------------------------------------

def _load_search_csv() -> list[dict]:
    path = _SCREENING / "search_results.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _parse_pubmed_nbib(path: Path) -> list[dict]:
    """Parse PubMed .nbib format into list of dicts."""
    records = []
    current: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("PMID- "):
                if current:
                    records.append(current)
                current = {"pmid": line[6:].strip(), "db": "pubmed"}
            elif line.startswith("TI  - "):
                current["title"] = line[6:].strip()
            elif line.startswith("      ") and "title" in current and not current.get("_title_done"):
                current["title"] = current["title"] + " " + line.strip()
            elif line.startswith("AB  - "):
                current["abstract"] = line[6:].strip()
                current["_title_done"] = True
            elif line.startswith("      ") and "abstract" in current:
                current["abstract"] = current["abstract"] + " " + line.strip()
            elif line.startswith("AU  - ") and "authors" not in current:
                current["authors"] = line[6:].strip()
            elif line.startswith("LID - ") and "doi" in line.lower():
                m = re.search(r"(10\.\S+)\s*\[doi\]", line, re.I)
                if m:
                    current["doi"] = m.group(1).lower()
            elif line.startswith("DP  - "):
                m = re.search(r"\d{4}", line)
                if m:
                    current["year"] = m.group()
            elif line.startswith("JT  - ") or line.startswith("TA  - "):
                current.setdefault("source", line[6:].strip())
    if current:
        records.append(current)
    return records


def _parse_ris(path: Path) -> list[dict]:
    """Parse a RIS file (WoS, Embase/Ovid, Scopus exports).

    Handles both standard RIS tags (TI/AB/AU/PY) and Ovid variants
    (T1/N2/A1/Y1) in the same pass.
    """
    records: list[dict] = []
    current: dict = {}
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\n")
            tag = line[:4].rstrip()
            val = line[6:].strip() if len(line) > 6 else ""
            if tag == "TY":
                if current:
                    records.append(current)
                current = {"db": path.stem}
            elif tag in ("TI", "T1"):
                current["title"] = val
            elif tag in ("AB", "N2"):
                current["abstract"] = val
            elif tag in ("AU", "A1") and "authors" not in current:
                current["authors"] = val
            elif tag == "DO":
                doi = re.sub(r"https?://(?:dx\.)?doi\.org/", "", val).lower()
                current.setdefault("doi", doi)
            elif tag in ("PY", "Y1"):
                m = re.search(r"\d{4}", val)
                if m:
                    current.setdefault("year", m.group())
            elif tag in ("T2", "JO", "JA", "JF"):
                current.setdefault("source", val)
            elif tag == "ER":
                if current:
                    records.append(current)
                current = {}
    if current:
        records.append(current)
    return records


def _add_records(rows: list[dict], seen_dois: set[str],
                 new_records: list[dict], fallback_prefix: str) -> None:
    for r in new_records:
        doi = (r.get("doi") or "").strip().lower()
        key = doi or f"{fallback_prefix}_{len(rows)}"
        if doi and doi in seen_dois:
            continue
        if doi:
            seen_dois.add(doi)
        rows.append({
            "item_key": key,
            "title": r.get("title", ""),
            "authors": r.get("authors", ""),
            "year": r.get("year", ""),
            "source": r.get("source", ""),
            "doi": doi,
            "abstract": r.get("abstract", ""),
        })


def _build_combined_records() -> list[dict]:
    """Merge all source files, deduplicate by DOI."""
    rows: list[dict] = []
    seen_dois: set[str] = set()

    _add_records(rows, seen_dois, _load_search_csv(), "oa")

    pubmed_path = _SCREENING / "pubmed_export.nbib"
    if pubmed_path.exists():
        for r in _parse_pubmed_nbib(pubmed_path):
            doi = (r.get("doi") or "").strip().lower()
            pmid = r.get("pmid", "")
            key = doi or f"pmid_{pmid}"
            if doi and doi in seen_dois:
                continue
            if doi:
                seen_dois.add(doi)
            rows.append({
                "item_key": key,
                "title": r.get("title", ""),
                "authors": r.get("authors", ""),
                "year": r.get("year", ""),
                "source": r.get("source", ""),
                "doi": doi,
                "abstract": r.get("abstract", ""),
            })

    for ris_file in sorted(_SCREENING.glob("*.ris")):
        prefix = ris_file.stem
        _add_records(rows, seen_dois, _parse_ris(ris_file), prefix)
        print(f"  Loaded {ris_file.name}")

    return rows


# ---------------------------------------------------------------------------
# Screener
# ---------------------------------------------------------------------------

def _make_client() -> "anthropic.Anthropic":
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        cfg = Path.home() / ".config/academic-research/config.toml"
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                tomllib = None  # type: ignore[assignment]
        if tomllib is None:
            print(f"  Note: tomllib not available; cannot read {cfg}")
        elif not cfg.exists():
            print(f"  Note: config not found at {cfg}")
        else:
            try:
                data = tomllib.loads(cfg.read_text())
                api_key = data.get("anthropic", {}).get("api_key", "")
                if api_key and api_key.startswith("sk-ant-YOURKEY"):
                    api_key = ""
                    print(f"  Note: placeholder key found in {cfg} — replace it with your real key")
            except Exception as exc:
                print(f"  Note: could not parse {cfg}: {exc}")
    if not api_key:
        sys.exit(
            "ERROR: ANTHROPIC_API_KEY not set and not found in config.toml\n"
            "  Fix: ANTHROPIC_API_KEY=sk-ant-... uv run screening/screen_abstracts.py"
        )
    return anthropic.Anthropic(api_key=api_key)


def _screen_one(record: dict, cfg, client, dry_run: bool) -> dict:
    title = record.get("title", "").strip()
    abstract = record.get("abstract", "").strip()
    user_msg = f"Title: {title}\n\nAbstract: {abstract or '[no abstract available]'}"

    if dry_run:
        decision, reason = "borderline", "[dry-run]"
    else:
        import anthropic as _anthropic
        delay = 5
        for attempt in range(6):
            try:
                resp = client.messages.create(
                    model=cfg.ABSTRACT_SCREENING_MODEL,
                    max_tokens=128,
                    temperature=0,
                    system=cfg.ABSTRACT_SCREENING_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                )
                break
            except _anthropic.RateLimitError:
                if attempt == 5:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 120)
        text = resp.content[0].text.strip()
        decision, reason = "borderline", text
        for line in text.splitlines():
            if line.upper().startswith("DECISION:"):
                decision = line.split(":", 1)[1].strip().lower()
            elif line.upper().startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()

    return {
        **{k: record.get(k, "") for k in ("item_key", "title", "authors", "year", "source", "doi")},
        "decision": decision,
        "reason": reason,
        "model": cfg.ABSTRACT_SCREENING_MODEL,
        "prompt_version": cfg.ABSTRACT_SCREENING_PROMPT_VERSION,
        "screened_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    cfg = _load_screening_config()
    records = _build_combined_records()
    print(f"Total records to screen: {len(records)}")

    # Load already-decided keys
    done: set[str] = set()
    if _OUT_CSV.exists():
        with open(_OUT_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                done.add(row["item_key"])
    pending = [r for r in records if r["item_key"] not in done]
    print(f"Already screened: {len(done)}  |  Pending: {len(pending)}")

    if args.sample:
        import random
        pending = random.sample(pending, min(args.sample, len(pending)))
        print(f"Sampling {len(pending)} records")

    if not pending:
        print("Nothing to do.")
        return

    client = None if args.dry_run else _make_client()

    _OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not _OUT_CSV.exists()
    lock = threading.Lock()
    counts = {"include": 0, "borderline": 0, "exclude": 0}

    def process(record: dict) -> None:
        result = _screen_one(record, cfg, client, args.dry_run)
        with lock:
            with open(_OUT_CSV, "a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
                if write_header and f.tell() == 0:
                    w.writeheader()
                w.writerow(result)
            counts[result["decision"]] = counts.get(result["decision"], 0) + 1
            total_done = sum(counts.values())
            if total_done % 50 == 0 or total_done == len(pending):
                print(f"  {total_done}/{len(pending)} — "
                      f"include={counts['include']} "
                      f"borderline={counts['borderline']} "
                      f"exclude={counts['exclude']}")

    # Write header first if needed
    if write_header:
        with open(_OUT_CSV, "w", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=OUTPUT_FIELDS).writeheader()

    workers = 1 if args.dry_run else args.workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(process, pending))

    print(f"\nDone. Results written to {_OUT_CSV}")
    print(f"  Include:    {counts['include']}")
    print(f"  Borderline: {counts['borderline']}")
    print(f"  Exclude:    {counts['exclude']}")


if __name__ == "__main__":
    main()
