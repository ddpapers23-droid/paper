"""Search configuration — AI/ML for PROMs following TKA and THA.

Systematic review: Artificial Intelligence and Machine Learning for
Predicting Patient-Reported Outcomes Following Total Knee and Total
Hip Arthroplasty.

PIPELINE USAGE (automated databases — Scopus, WoS, OpenAlex, Semantic Scholar):
    uv run ${CLAUDE_PLUGIN_ROOT}/scripts/pipelines/search.py --config ./search_config.py

MANUAL DATABASES (PubMed, Embase, Cochrane):
    Run the strings in PUBMED_QUERY, EMBASE_OVID_QUERY, and COCHRANE_QUERY
    in their respective platforms. Export results as RIS or CSV and import
    to Zotero, then run import_to_zotero.py to merge into the pipeline.

    uv run ${CLAUDE_PLUGIN_ROOT}/scripts/pipelines/import_to_zotero.py \\
        --ris pubmed_export.ris --collection <collection-key>

Date completed: <INSERT DATE>
PROSPERO registration: <INSERT CRD NUMBER>
"""

# ---------------------------------------------------------------------------
# 1. Time window
# ---------------------------------------------------------------------------

FROM_YEAR = 2010
TO_YEAR   = 2026


# ---------------------------------------------------------------------------
# 2. Journal scope
#
# Medical SLRs are NOT journal-restricted — the search is unrestricted
# by source to avoid missing key clinical informatics or AI-specific
# venues (e.g. npj Digital Medicine, JAMIA, Artificial Intelligence in
# Medicine) that would not appear in a single-discipline list.
#
# Leave empty; search.py will not apply an ISSN filter.
# ---------------------------------------------------------------------------

JOURNALS: dict[str, tuple[str, str]] = {}


# ---------------------------------------------------------------------------
# 3. Scopus / WoS queries (automated pipeline)
#
# Scopus: TITLE-ABS-KEY stems plurals automatically.
# WoS:    TS= (topic = title + abstract + keywords + keywords plus).
#         WoS does NOT auto-stem — wildcard phrase tails where needed
#         (e.g. "functional outcome*" covers "outcomes").
#
# search.py appends the year filter (FROM_YEAR–TO_YEAR) automatically.
# Do NOT embed PUBYEAR or PY= here.
# ---------------------------------------------------------------------------

QUERY_DEFS = [
    (
        "Q1_arthroplasty_x_AI_x_PROM",
        # ---- Scopus ----
        'TITLE-ABS-KEY('
        '  "total knee arthroplasty" OR "total hip arthroplasty"'
        '  OR "TKA" OR "THA"'
        '  OR "knee replacement" OR "hip replacement"'
        ') AND TITLE-ABS-KEY('
        '  "machine learning" OR "artificial intelligence"'
        '  OR "deep learning" OR "random forest"'
        '  OR "neural network" OR "gradient boosting" OR "XGBoost"'
        ') AND TITLE-ABS-KEY('
        '  "patient-reported outcome" OR "PROM"'
        '  OR "KOOS" OR "HOOS" OR "WOMAC"'
        '  OR "functional outcome" OR "MCID"'
        ')',
        # ---- Web of Science ----
        'TS=("total knee arthroplasty" OR "total hip arthroplasty"'
        '    OR "TKA" OR "THA"'
        '    OR "knee replacement" OR "hip replacement")'
        ' AND TS=("machine learning" OR "artificial intelligence"'
        '         OR "deep learning" OR "random forest"'
        '         OR "neural network" OR "gradient boosting" OR "XGBoost")'
        ' AND TS=("patient-reported outcome*" OR "PROM"'
        '         OR "KOOS" OR "HOOS" OR "WOMAC"'
        '         OR "functional outcome*" OR "MCID")',
    ),
]


# ---------------------------------------------------------------------------
# 4. OpenAlex block terms (search_openalex.py)
#
# OpenAlex relevance-ranks on a single search= field; two-block strategy
# returns papers central to AI/ML (Block A) AND arthroplasty PROMs (Block B).
# ---------------------------------------------------------------------------

BLOCK_A_TERMS = [
    "machine learning",
    "artificial intelligence",
    "deep learning",
    "neural network",
    "random forest",
    "gradient boosting",
    "XGBoost",
]

BLOCK_B_TERMS = [
    "total knee arthroplasty",
    "total hip arthroplasty",
    "patient-reported outcome",
    "KOOS",
    "HOOS",
    "WOMAC",
    "PROM",
]


# ---------------------------------------------------------------------------
# 5. Manual database strings
#
# Run these strings in the listed platforms, apply the date filter
# 2010–2026, export as RIS or PubMed XML, import to Zotero.
# Record hit counts in SEARCH_HITS below.
# ---------------------------------------------------------------------------

# PubMed / MEDLINE — exact string provided by review team.
# Platform: https://pubmed.ncbi.nlm.nih.gov/advanced/
# Date filter: 2010/01/01 – 2026/12/31 (use Publication Date filter)
PUBMED_QUERY = (
    '("total knee arthroplasty"[tiab] OR "total hip arthroplasty"[tiab]'
    ' OR "TKA"[tiab] OR "THA"[tiab]'
    ' OR "knee replacement"[tiab] OR "hip replacement"[tiab])'
    ' AND ("machine learning"[tiab] OR "artificial intelligence"[tiab]'
    '      OR "deep learning"[tiab] OR "random forest"[tiab]'
    '      OR "neural network"[tiab] OR "gradient boosting"[tiab]'
    '      OR "XGBoost"[tiab])'
    ' AND ("patient-reported outcome"[tiab] OR "PROM"[tiab]'
    '      OR "KOOS"[tiab] OR "HOOS"[tiab] OR "WOMAC"[tiab]'
    '      OR "functional outcome"[tiab] OR "MCID"[tiab])'
)

# Embase — Ovid interface syntax.
# Platform: Ovid EMBASE (institutional access required)
# Paste each line in a separate Ovid search row, then combine with AND.
# Apply Limit: Publication Year 2010–2026.
EMBASE_OVID_QUERY = (
    "Line 1: (total knee arthroplasty or total hip arthroplasty"
    " or TKA or THA or knee replacement or hip replacement).ti,ab.\n"
    "Line 2: (machine learning or artificial intelligence or deep learning"
    " or random forest or neural network or gradient boosting or XGBoost).ti,ab.\n"
    "Line 3: (patient-reported outcome or PROM or KOOS or HOOS or WOMAC"
    " or functional outcome or MCID).ti,ab.\n"
    "Combine: 1 AND 2 AND 3\n"
    "Limit: Publication Year 2010–2026; Exclude MEDLINE records (avoid PubMed overlap)"
)

# Cochrane CENTRAL — Cochrane Library interface.
# Platform: https://www.cochranelibrary.com/advanced-search
# Paste the block below into the Search Manager; set Date Range 2010–2026.
COCHRANE_QUERY = (
    '("total knee arthroplasty" OR "total hip arthroplasty"'
    ' OR "TKA" OR "THA"'
    ' OR "knee replacement" OR "hip replacement")'
    ' AND ("machine learning" OR "artificial intelligence"'
    '      OR "deep learning" OR "random forest"'
    '      OR "neural network" OR "gradient boosting" OR "XGBoost")'
    ' AND ("patient-reported outcome" OR "PROM"'
    '      OR "KOOS" OR "HOOS" OR "WOMAC"'
    '      OR "functional outcome" OR "MCID")'
)


# ---------------------------------------------------------------------------
# 6. Hit counts — fill in after running each search
#
# These are imported by manuscript_stats.py to produce the PRISMA numbers.
# ---------------------------------------------------------------------------

SEARCH_HITS: dict[str, int | None] = {
    "scopus":            None,  # fill after running search.py
    "wos":               None,
    "openalex":          None,
    "semantic_scholar":  None,
    "pubmed":            73,    # searched 2026-05-21
    "embase":            None,
    "cochrane":          0,
}
