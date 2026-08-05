#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Cohen's kappa for dual-reviewer Rayyan screening decisions.

Two input modes, since Rayyan doesn't export "one file per reviewer" —
a project export bundles every reviewer's decision into one row's
`notes` field as `RAYYAN-INCLUSION: {"Alice"=>"Included", "Bob"=>"Excluded"}`:

    Mode A (--input, one shared Rayyan export):
        uv run kappa_calculator.py --input rayyan_export.csv \\
            --reviewer1-name "Alice" --reviewer2-name "Bob"
        Parses both reviewers' decisions out of the same `notes` column.

    Mode B (--reviewer1-file / --reviewer2-file, two separate CSVs):
        uv run kappa_calculator.py \\
            --reviewer1-file alice_decisions.csv \\
            --reviewer2-file bob_decisions.csv
        Each file has its own decision column (e.g. you already split
        the export, or exported per-reviewer some other way).

Both modes need a shared key column to match records across reviewers/
files — auto-detected from key/PMID/article_id/id/title (first match
wins), or set explicitly with --key-column.

Decision values are normalized (case-insensitive; included/include/
yes/in -> INCLUDED, excluded/exclude/no/out -> EXCLUDED, maybe/unsure
-> MAYBE) before computing agreement, so "Included" vs "included" isn't
scored as a disagreement.

Output: prints Cohen's kappa, the observed agreement count/rate, and
writes every disagreeing (and any unmatched/undecided) pair to
disagreements.csv for adjudication.

Usage:
    uv run kappa_calculator.py --input rayyan_export.csv --reviewer1-name "Alice" --reviewer2-name "Bob"
    uv run kappa_calculator.py --reviewer1-file r1.csv --reviewer2-file r2.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

KEY_COLUMN_CANDIDATES = ["key", "Key", "PMID", "pmid", "article_id", "id", "ID", "title", "Title"]
DECISION_COLUMN_CANDIDATES = ["decision", "Decision", "screening_decision", "status", "Status", "included", "Included"]

DECISION_ALIASES = {
    "included": "INCLUDED",
    "include": "INCLUDED",
    "yes": "INCLUDED",
    "in": "INCLUDED",
    "excluded": "EXCLUDED",
    "exclude": "EXCLUDED",
    "no": "EXCLUDED",
    "out": "EXCLUDED",
    "maybe": "MAYBE",
    "unsure": "MAYBE",
}

RAYYAN_INCLUSION_RE = re.compile(r'RAYYAN-INCLUSION:\s*\{([^}]*)\}')
RAYYAN_PAIR_RE = re.compile(r'"([^"]+)"\s*=>\s*"([^"]*)"')


def _normalize_decision(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    return DECISION_ALIASES.get(raw.lower(), raw.upper())


def _detect_column(fieldnames: list[str], candidates: list[str], role: str, explicit: str | None) -> str:
    if explicit:
        if explicit not in fieldnames:
            raise SystemExit(f"--{role}-column '{explicit}' not found in columns: {fieldnames}")
        return explicit
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    raise SystemExit(
        f"Could not auto-detect a {role} column among {fieldnames}. "
        f"Pass --{role}-column explicitly."
    )


def _parse_rayyan_notes(notes: str, reviewer_name: str) -> str | None:
    match = RAYYAN_INCLUSION_RE.search(notes or "")
    if not match:
        return None
    for name, decision in RAYYAN_PAIR_RE.findall(match.group(1)):
        if name.strip() == reviewer_name:
            return _normalize_decision(decision)
    return None


def load_mode_a(input_path: Path, key_column: str | None, reviewer1_name: str, reviewer2_name: str) -> dict[str, tuple[str | None, str | None]]:
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        key_col = _detect_column(fieldnames, KEY_COLUMN_CANDIDATES, "key", key_column)
        if "notes" not in fieldnames:
            raise SystemExit(f"Expected a 'notes' column with RAYYAN-INCLUSION data; found: {fieldnames}")

        results: dict[str, tuple[str | None, str | None]] = {}
        for row in reader:
            key = row.get(key_col, "").strip()
            if not key:
                continue
            notes = row.get("notes", "")
            d1 = _parse_rayyan_notes(notes, reviewer1_name)
            d2 = _parse_rayyan_notes(notes, reviewer2_name)
            results[key] = (d1, d2)
    return results


def _load_single_file(path: Path, key_column: str | None, decision_column: str | None) -> dict[str, str | None]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        key_col = _detect_column(fieldnames, KEY_COLUMN_CANDIDATES, "key", key_column)
        decision_col = _detect_column(fieldnames, DECISION_COLUMN_CANDIDATES, "decision", decision_column)

        decisions: dict[str, str | None] = {}
        for row in reader:
            key = row.get(key_col, "").strip()
            if not key:
                continue
            decisions[key] = _normalize_decision(row.get(decision_col, ""))
    return decisions


def load_mode_b(
    reviewer1_path: Path, reviewer2_path: Path, key_column: str | None, decision_column: str | None
) -> dict[str, tuple[str | None, str | None]]:
    d1_map = _load_single_file(reviewer1_path, key_column, decision_column)
    d2_map = _load_single_file(reviewer2_path, key_column, decision_column)
    all_keys = set(d1_map) | set(d2_map)
    return {key: (d1_map.get(key), d2_map.get(key)) for key in all_keys}


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    if n == 0:
        return None

    agree = sum(1 for d1, d2 in pairs if d1 == d2)
    po = agree / n

    categories = {d for pair in pairs for d in pair}
    p1 = {c: sum(1 for d1, _ in pairs if d1 == c) / n for c in categories}
    p2 = {c: sum(1 for _, d2 in pairs if d2 == c) / n for c in categories}
    pe = sum(p1[c] * p2[c] for c in categories)

    if pe == 1.0:
        return None  # undefined: no variance to correct for chance agreement
    return (po - pe) / (1 - pe)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", help="Single shared Rayyan export CSV (Mode A)")
    parser.add_argument("--reviewer1-name", help="Reviewer 1's name as it appears in the notes column (Mode A)")
    parser.add_argument("--reviewer2-name", help="Reviewer 2's name as it appears in the notes column (Mode A)")
    parser.add_argument("--reviewer1-file", help="Reviewer 1's own decisions CSV (Mode B)")
    parser.add_argument("--reviewer2-file", help="Reviewer 2's own decisions CSV (Mode B)")
    parser.add_argument("--key-column", default=None)
    parser.add_argument("--decision-column", default=None, help="Mode B only")
    parser.add_argument("--output", default="disagreements.csv")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    output_path = base_dir / args.output

    if args.input:
        if not args.reviewer1_name or not args.reviewer2_name:
            raise SystemExit("Mode A requires --reviewer1-name and --reviewer2-name")
        combined = load_mode_a(base_dir / args.input, args.key_column, args.reviewer1_name, args.reviewer2_name)
    elif args.reviewer1_file and args.reviewer2_file:
        combined = load_mode_b(
            base_dir / args.reviewer1_file, base_dir / args.reviewer2_file, args.key_column, args.decision_column
        )
    else:
        raise SystemExit("Provide either --input with both --reviewer1-name/--reviewer2-name (Mode A), or --reviewer1-file and --reviewer2-file (Mode B)")

    matched_pairs: list[tuple[str, str, str]] = []  # key, d1, d2
    unresolved: list[tuple[str, str | None, str | None]] = []

    for key, (d1, d2) in combined.items():
        if d1 is None or d2 is None:
            unresolved.append((key, d1, d2))
        else:
            matched_pairs.append((key, d1, d2))

    kappa = cohens_kappa([(d1, d2) for _, d1, d2 in matched_pairs])
    agree_count = sum(1 for _, d1, d2 in matched_pairs if d1 == d2)
    disagreements = [(key, d1, d2) for key, d1, d2 in matched_pairs if d1 != d2]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "Reviewer_1_Decision", "Reviewer_2_Decision", "Status"])
        for key, d1, d2 in disagreements:
            writer.writerow([key, d1, d2, "DISAGREEMENT"])
        for key, d1, d2 in unresolved:
            writer.writerow([key, d1 or "", d2 or "", "MISSING_DECISION"])

    print(f"Matched records (both reviewers decided): {len(matched_pairs)}")
    print(f"Unresolved (missing a decision from one/both reviewers): {len(unresolved)}")
    if kappa is None:
        print("Cohen's kappa: undefined (no variance in matched decisions to correct for chance agreement)")
    else:
        print(f"Cohen's kappa: {kappa:.3f}")
    print(f"Agreement: {agree_count}/{len(matched_pairs)}" + (f" ({agree_count / len(matched_pairs):.1%})" if matched_pairs else ""))
    print(f"Disagreements: {len(disagreements)}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
