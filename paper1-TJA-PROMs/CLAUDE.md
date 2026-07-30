# CLAUDE.md — paper1-TJA-PROMs

## Project

**AI/ML prediction of patient-reported outcome measures (PROMs) after total
knee and total hip arthroplasty (TKA/THA): a systematic review.**

This is a systematic review of studies applying machine learning / AI models
to predict patient-reported outcomes (KOOS, HOOS, WOMAC, OHS, OKS, KSS,
EQ-5D, MCID attainment, etc.) after total knee arthroplasty (TKA) and total
hip arthroplasty (THA).

- **Target journal:** Journal of Arthroplasty
- **Search date range:** 2010-01-01 to 2026-05-20
- **PROSPERO ID:** [PENDING - add when received]

## Folder structure

```
paper1-TJA-PROMs/
  searches/       PubMed search + deduplication scripts and their CSV outputs
  screening/      Preliminary screening + Rayyan-format conversion, and their outputs
  extraction/     Data-extraction Excel workbook (built, not auto-populated)
  manuscript/     Manuscript drafting — do not touch except by explicit instruction
  figures/        PRISMA diagram, forest plots, and other manuscript figures
  CLAUDE.md       This file
```

## Scripts

Run in this order:

1. **`searches/search_config.py`** — Queries PubMed via NCBI E-utilities
   (esearch + efetch) with the project's Boolean search string, filtered to
   the 2010–2026 date window. Writes `searches/results_pubmed.csv`
   (PMID, Title, Authors, Year, Journal, Abstract). Max 500 results. No API
   key required at this volume; set `NCBI_API_KEY` to raise the rate limit.

2. **`searches/dedup.py`** — Deduplicates `results_pubmed.csv`: exact PMID
   match first, then fuzzy title match (90% similarity threshold via
   rapidfuzz/difflib). Writes `searches/results_deduped.csv`.

3. **`screening/screening_config.py`** — Applies keyword-based
   inclusion/exclusion logic to `results_deduped.csv` and tags each record
   `PRELIM_INCLUDE` / `PRELIM_EXCLUDE` / `NEEDS_REVIEW`. Also flags
   PRELIM_INCLUDE records that don't mention an obvious performance metric
   (AUC/sensitivity/specificity/accuracy/R²/c-statistic) in the abstract, and
   adds blank `Reviewer_1_Decision` / `Reviewer_2_Decision` / `Conflict`
   columns for the two-reviewer human screen. Writes
   `screening/prelim_screen.csv`. This is a triage aid, not a replacement for
   dual human screening.

4. **`screening/rayyan_formatter.py`** — Converts `prelim_screen.csv` into
   Rayyan's bulk-import CSV format (key, title, authors, journal, year,
   volume, pages, abstract, url). Writes `screening/rayyan_import.csv`.
   `volume`/`pages` are blank — PubMed esearch/efetch output doesn't collect
   them.

5. **`extraction/extraction_template.py`** — Generates
   `extraction/data_extraction.xlsx`: a "Data Extraction" sheet (27 columns
   including AUC/Sensitivity/Specificity/Accuracy/R², PROBAST Domains 1–4,
   Overall PROBAST Risk, with dropdown validation on Joint/External
   Validation/PROBAST columns) and a "PROBAST Guide" reference sheet with the
   four domains' signaling questions. **Built but not auto-run** — only
   generate/regenerate this workbook when explicitly asked, since running it
   again overwrites in-progress extraction data.

## Rules

- **Never modify anything under `manuscript/` without explicit instruction.**
  Manuscript drafting is a distinct, deliberate step — not a side effect of
  pipeline maintenance.
- **All search exports get a date in the filename** when re-run for a new
  search snapshot (e.g. `results_pubmed_2026-07-30.csv`), so successive
  search runs don't silently clobber the prior snapshot. The scripts'
  default output names (`results_pubmed.csv`, etc.) are for the working
  copy; archive dated snapshots alongside them before re-running.
- **Flag any study missing AUC or another performance metric.** This is
  checked heuristically at the screening stage (`Missing_Performance_Metric`
  column) and must be checked again by hand during full-text extraction —
  a study with no discrimination/performance metric reported at all is a
  candidate for exclusion or a PROBAST Domain 4 "High" rating, not silent
  omission.
