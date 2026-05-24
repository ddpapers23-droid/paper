#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic>=0.30", "requests>=2.31"]
# ///
"""AI-assisted data extraction from full-text PDFs.

Reads PDFs from screening/pdfs/, matches each to an included paper by
filename or DOI slug, sends the full text to Claude, and writes all 53
extraction fields to screening/data_extraction.csv.

Resumable: already-extracted paper_ids are skipped on re-run.

Usage:
    uv run screening/extract_data.py
    uv run screening/extract_data.py --dry-run     # no API calls
    uv run screening/extract_data.py --model claude-sonnet-4-6
    uv run screening/extract_data.py --pdf path/to/paper.pdf  # single paper
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCREENING = _ROOT / "screening"
_PDF_DIR = _SCREENING / "pdfs"
_INCLUDE_CSV = _SCREENING / "fulltext_review.csv"
_OUT_CSV = _SCREENING / "data_extraction.csv"

DEFAULT_MODEL = "claude-sonnet-4-6"

OUTPUT_FIELDS = [
    "paper_id", "first_author", "year", "title", "journal", "doi", "country",
    "study_design", "setting", "data_source",
    "joint", "n_total", "n_tka", "n_tha", "mean_age", "pct_female", "mean_bmi", "indication",
    "ml_algorithms", "n_algorithms_compared", "best_algorithm",
    "feature_types", "n_features_input", "feature_selection", "interpretability_reported",
    "prom_instruments", "prom_endpoint", "prom_timepoint_months", "outcome_type",
    "auc", "accuracy", "sensitivity", "specificity", "r2", "rmse",
    "other_metric", "other_metric_value", "calibration_reported",
    "validation_type", "n_train", "n_test", "external_validation",
    "probast_d1_participants", "probast_d2_predictors",
    "probast_d3_outcome", "probast_d4_analysis", "probast_overall",
    "tripod_adherence", "code_available", "data_available",
    "extractor_initials", "extraction_date", "notes",
]

EXTRACTION_PROMPT = """You are extracting structured data from a systematic review paper about AI/ML for predicting patient-reported outcomes (PROMs) following total knee arthroplasty (TKA) or total hip arthroplasty (THA).

Read the full text below and extract every field. Return ONLY a valid JSON object with these exact keys. Use empty string "" for any field you cannot determine.

Required fields and allowed values:

{
  "first_author": "surname of first author",
  "year": "publication year as 4-digit string",
  "title": "full paper title",
  "journal": "journal name",
  "doi": "DOI without https://doi.org/ prefix",
  "country": "country of study population (not author affiliation)",

  "study_design": "retrospective|prospective|RCT|registry|other",
  "setting": "single-center|multi-center|national-registry|international-registry",
  "data_source": "institutional-registry|national-registry|EHR|prospective-cohort|RCT|other",

  "joint": "TKA|THA|both",
  "n_total": "integer — total patients in study",
  "n_tka": "integer or empty",
  "n_tha": "integer or empty",
  "mean_age": "number in years",
  "pct_female": "percentage 0-100",
  "mean_bmi": "number",
  "indication": "OA|RA|mixed|not-reported",

  "ml_algorithms": "comma-separated list of all ML algorithms tested",
  "n_algorithms_compared": "integer",
  "best_algorithm": "algorithm with best reported performance",
  "feature_types": "clinical|imaging|clinical+imaging|wearable|NLP|other",
  "n_features_input": "integer",
  "feature_selection": "yes|no|not-reported",
  "interpretability_reported": "yes|no",

  "prom_instruments": "comma-separated list e.g. KOOS, WOMAC, OKS",
  "prom_endpoint": "absolute-score|change-score|MCID-binary|satisfaction|other",
  "prom_timepoint_months": "integer — postop follow-up months when PROM measured",
  "outcome_type": "classification|regression|clustering",

  "auc": "best AUC/AUROC reported (0-1), empty if regression",
  "accuracy": "proportion or percentage correctly classified",
  "sensitivity": "sensitivity/recall for best model",
  "specificity": "specificity for best model",
  "r2": "R-squared for regression models, empty if classification",
  "rmse": "RMSE for regression models",
  "other_metric": "name of any other performance metric",
  "other_metric_value": "value of that metric",
  "calibration_reported": "yes|no",

  "validation_type": "none|train-test-split|cross-validation|bootstrap|external",
  "n_train": "integer",
  "n_test": "integer",
  "external_validation": "yes|no",

  "probast_d1_participants": "low|high|unclear — was participant selection unbiased?",
  "probast_d2_predictors": "low|high|unclear — were predictors pre-specified and blind to outcome?",
  "probast_d3_outcome": "low|high|unclear — was the PROM outcome measured appropriately?",
  "probast_d4_analysis": "low|high|unclear — was analysis appropriate (sample size, missing data, overfitting handled)?",
  "probast_overall": "low|high|unclear — high if any domain is high",

  "tripod_adherence": "full|partial|not-reported",
  "code_available": "yes|no|not-reported",
  "data_available": "yes|no|not-reported",

  "notes": "any important caveats, limitations, or flags for human review"
}

PROBAST guidance:
- D1 high risk: convenience sample, exclusions not described, retrospective with unclear eligibility
- D2 high risk: predictors defined post-hoc, data leakage possible, predictors measured after outcome
- D3 high risk: PROM not validated, outcome assessor not blinded, short or inconsistent follow-up
- D4 high risk: sample too small for number of predictors, no missing data handling, no internal validation, optimism not corrected

Return ONLY the JSON object. No markdown, no explanation.

---
FULL TEXT:
"""


def _pdf_to_text(pdf_path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=60,
        )
        return result.stdout[:80000]  # cap at ~80k chars to stay within context
    except Exception as e:
        return f"[PDF extraction failed: {e}]"


def _make_client(model: str):
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            import tomllib
            cfg = Path.home() / ".config/academic-research/config.toml"
            if cfg.exists():
                data = tomllib.loads(cfg.read_text())
                api_key = data.get("anthropic", {}).get("api_key", "")
        except Exception:
            pass
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set\n"
                 "  Fix: ANTHROPIC_API_KEY=sk-ant-... uv run screening/extract_data.py")
    return anthropic.Anthropic(api_key=api_key)


def _extract_one(pdf_path: Path, paper_meta: dict, client, model: str, dry_run: bool) -> dict:
    text = _pdf_to_text(pdf_path)

    if dry_run:
        result = {k: "[dry-run]" for k in OUTPUT_FIELDS}
        result.update({
            "paper_id": paper_meta.get("num", ""),
            "title": paper_meta.get("title", ""),
            "doi": paper_meta.get("doi", ""),
            "year": paper_meta.get("year", ""),
            "extractor_initials": "AI",
            "extraction_date": datetime.now(timezone.utc).date().isoformat(),
        })
        return result

    delay = 5
    for attempt in range(5):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=2048,
                temperature=0,
                messages=[{"role": "user", "content": EXTRACTION_PROMPT + text}],
            )
            break
        except Exception as e:
            if "rate" in str(e).lower() and attempt < 4:
                time.sleep(delay)
                delay = min(delay * 2, 60)
            else:
                raise

    raw = resp.content[0].text.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        extracted = json.loads(raw)
    except json.JSONDecodeError:
        extracted = {"notes": f"JSON parse error: {raw[:200]}"}

    result = {k: "" for k in OUTPUT_FIELDS}
    result.update({k: str(v) for k, v in extracted.items() if k in OUTPUT_FIELDS})
    result["paper_id"] = paper_meta.get("num", result.get("paper_id", ""))
    result["extractor_initials"] = "AI"
    result["extraction_date"] = datetime.now(timezone.utc).date().isoformat()
    return result


def _load_includes() -> dict[str, dict]:
    """Load included papers keyed by DOI slug."""
    papers = {}
    if not _INCLUDE_CSV.exists():
        return papers
    with open(_INCLUDE_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doi = (row.get("doi") or "").strip().lower()
            doi = re.sub(r"https?://(?:dx\.)?doi\.org/", "", doi)
            slug = re.sub(r"[^\w.-]", "_", doi)[:120] if doi else ""
            papers[slug] = {
                "num": row["#"],
                "title": row["title"],
                "doi": doi,
                "year": row.get("year", ""),
            }
    return papers


def _load_done() -> set[str]:
    done = set()
    if _OUT_CSV.exists():
        with open(_OUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("paper_id"):
                    done.add(row["paper_id"])
    return done


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--pdf", help="Extract a single PDF file")
    args = parser.parse_args()

    includes = _load_includes()
    done = _load_done()
    client = None if args.dry_run else _make_client(args.model)

    if args.pdf:
        pdfs = [Path(args.pdf)]
    else:
        _PDF_DIR.mkdir(parents=True, exist_ok=True)
        pdfs = sorted(_PDF_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {_PDF_DIR}")
        print("Run: uv run screening/fetch_pdfs.py   to download open-access PDFs")
        print("Then add remaining PDFs manually to screening/pdfs/")
        return

    print(f"PDFs found: {len(pdfs)}  |  Already extracted: {len(done)}")

    write_header = not _OUT_CSV.exists()
    _OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    for pdf_path in pdfs:
        # Match PDF to include list by slug
        slug = pdf_path.stem
        meta = includes.get(slug, {"num": slug, "title": pdf_path.name, "doi": "", "year": ""})

        if meta["num"] in done:
            continue

        print(f"  Extracting: {pdf_path.name[:60]}", flush=True)
        try:
            result = _extract_one(pdf_path, meta, client, args.model, args.dry_run)
        except Exception as e:
            print(f"    ERROR: {e}")
            result = {k: "" for k in OUTPUT_FIELDS}
            result.update({
                "paper_id": meta["num"],
                "title": meta["title"],
                "doi": meta["doi"],
                "notes": f"Extraction error: {e}",
                "extractor_initials": "AI",
                "extraction_date": datetime.now(timezone.utc).date().isoformat(),
            })

        with open(_OUT_CSV, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
            if write_header and f.tell() == 0:
                w.writeheader()
                write_header = False
            w.writerow(result)

        print(f"    ✓ {result.get('first_author','?')} {result.get('year','?')} | "
              f"joint={result.get('joint','?')} | "
              f"AUC={result.get('auc','?')} | "
              f"PROBAST={result.get('probast_overall','?')}")
        processed += 1
        time.sleep(0.5)

    if write_header and not _OUT_CSV.exists():
        with open(_OUT_CSV, "w", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=OUTPUT_FIELDS).writeheader()

    print(f"\nDone. {processed} papers extracted.")
    print(f"Results: {_OUT_CSV}")


if __name__ == "__main__":
    main()
