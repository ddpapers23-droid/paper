#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Preliminary title/abstract screening for the AI/ML-PROMs-after-TJA review.

Applies keyword-based inclusion/exclusion logic to each deduplicated
record and writes a PRELIM_DECISION of PRELIM_INCLUDE, PRELIM_EXCLUDE,
or NEEDS_REVIEW. This is a *screening aid*, not a substitute for the
two-reviewer human screen — every record still needs eyes on it in
Rayyan; NEEDS_REVIEW and PRELIM_INCLUDE records are the priority queue.

Decision logic (checked against Title + Abstract, case-insensitive):

    PRELIM_EXCLUDE if ANY exclusion term is present (checked first —
    exclusion terms such as "systematic review" should win even when
    ML/PROM/joint terms also match, e.g. a systematic review *of* ML
    models).

    PRELIM_INCLUDE if none of the exclusion terms are present AND ALL
    THREE of: (ML/AI term) AND (PROM term) AND (joint/procedure term)
    are present.

    NEEDS_REVIEW otherwise.

Also adds a Missing_Performance_Metric heuristic flag (Y/N): for
PRELIM_INCLUDE records, Y means no AUC/sensitivity/specificity/
accuracy/R2/c-statistic keyword was found in the abstract — a signal
that the metric may only appear in the full text, or that the record
should be checked closely at full-text stage. Two blank columns
(Reviewer_1_Decision, Reviewer_2_Decision) and a Conflict column are
included for the two-reviewer human screening workflow downstream.

Usage:
    uv run screening_config.py
    uv run screening_config.py --input ../searches/results_deduped.csv --output prelim_screen.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ML_AI_TERMS = [
    "machine learning",
    "artificial intelligence",
    "deep learning",
    "neural network",
    "random forest",
    "gradient boosting",
    "xgboost",
    "predictive model",
    "prediction model",
    # v2 additions, to match the search_config.py v2 query's ML/AI block
    "logistic regression",
    "classification model",
    "supervised learning",
    "ensemble",
    "natural language processing",
    "nlp",
    "regression model",
    "multivariable model",
    "multivariate model",
]

PROM_TERMS = [
    "koos",
    "hoos",
    "womac",
    "ohs",
    "oks",
    "kss",
    "eq-5d",
    "patient-reported",
    "prom",
    "functional outcome",
    "mcid",
    # v2 additions, to match the search_config.py v2 query's PROM block
    "oxford knee score",
    "oxford hip score",
    "eq5d",
    "sf-36",
    "sf36",
    "visual analogue scale",
    "vas",
    "pain score",
    "patient satisfaction",
    "quality of life",
    "quickdash",
    "forgotten joint score",
    "fjs",
]

JOINT_TERMS = [
    "total knee",
    "total hip",
    "tka",
    "tha",
    "knee replacement",
    "hip replacement",
    "arthroplasty",
    # v2 additions, to match the search_config.py v2 query's joint block
    "knee arthroplasty",
    "hip arthroplasty",
    "joint replacement",
    "joint arthroplasty",
]

EXCLUSION_TERMS = [
    "revision arthroplasty",
    "unicompartmental",
    "uka",
    "pediatric",
    "cadaveric",
    "animal",
    "systematic review",
    "meta-analysis",
    "periprosthetic infection",
    "pji",
    "venous thromboembolism",
    # v2 additions, to hold precision as the include-side terms widen
    "shoulder arthroplasty",
    "shoulder replacement",
    "ankle arthroplasty",
    "elbow arthroplasty",
    "spine",
    "spinal",
    "vertebral",
    "fracture fixation",
    "trauma",
    "animal model",
    "rat model",
    "mouse model",
    "in vitro",
    "biomechanical study",
]

PERFORMANCE_METRIC_TERMS = [
    "auc",
    "area under the curve",
    "area under the receiver",
    "sensitivity",
    "specificity",
    "accuracy",
    "r2",
    "r-squared",
    "r²",
    "c-statistic",
    "concordance index",
]

EXTRA_FIELDNAMES = [
    "PRELIM_DECISION",
    "Missing_Performance_Metric",
    "Reviewer_1_Decision",
    "Reviewer_2_Decision",
    "Conflict",
]


def _contains_any(haystack: str, terms: list[str]) -> bool:
    return any(term in haystack for term in terms)


def classify(title: str, abstract: str) -> str:
    combined = f"{title} {abstract}".lower()

    if _contains_any(combined, EXCLUSION_TERMS):
        return "PRELIM_EXCLUDE"

    has_ml = _contains_any(combined, ML_AI_TERMS)
    has_prom = _contains_any(combined, PROM_TERMS)
    has_joint = _contains_any(combined, JOINT_TERMS)

    if has_ml and has_prom and has_joint:
        return "PRELIM_INCLUDE"

    return "NEEDS_REVIEW"


def missing_performance_metric(abstract: str) -> str:
    return "N" if _contains_any(abstract.lower(), PERFORMANCE_METRIC_TERMS) else "Y"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="../searches/results_deduped.csv")
    parser.add_argument("--output", default="prelim_screen.csv")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    input_path = (base_dir / args.input).resolve()
    output_path = base_dir / args.output

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        records = list(reader)

    counts = {"PRELIM_INCLUDE": 0, "PRELIM_EXCLUDE": 0, "NEEDS_REVIEW": 0}
    missing_metric_count = 0

    for row in records:
        title = row.get("Title", "")
        abstract = row.get("Abstract", "")
        decision = classify(title, abstract)
        row["PRELIM_DECISION"] = decision
        counts[decision] += 1

        flag = missing_performance_metric(abstract) if decision == "PRELIM_INCLUDE" else ""
        row["Missing_Performance_Metric"] = flag
        if flag == "Y":
            missing_metric_count += 1

        row["Reviewer_1_Decision"] = ""
        row["Reviewer_2_Decision"] = ""
        row["Conflict"] = ""

    out_fieldnames = fieldnames + [name for name in EXTRA_FIELDNAMES if name not in fieldnames]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Total records screened: {len(records)}")
    print(f"PRELIM_INCLUDE: {counts['PRELIM_INCLUDE']}")
    print(f"PRELIM_EXCLUDE: {counts['PRELIM_EXCLUDE']}")
    print(f"NEEDS_REVIEW: {counts['NEEDS_REVIEW']}")
    print(f"PRELIM_INCLUDE records missing an obvious performance metric: {missing_metric_count}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
