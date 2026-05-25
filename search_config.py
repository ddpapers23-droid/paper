"""Per-project search configuration for a systematic literature review.

Copy this file to the root of your SLR project and edit every block
below for your specific review. The `search.py` and `search_openalex.py`
pipeline scripts read this module by path (via `--config`).

Keep this file in git alongside your manuscript. It IS the scope of
your review — reviewers will read it to judge whether the search is
appropriate.

Usage:
    uv run ${CLAUDE_PLUGIN_ROOT}/scripts/pipelines/search.py --config ./search_config.py
"""

# ---------------------------------------------------------------------------
# 1. Time window
# ---------------------------------------------------------------------------

FROM_YEAR = 2020
TO_YEAR   = 2026


# ---------------------------------------------------------------------------
# 2. Journal scope
#
# No ISSN filter for this SR — medical/clinical topic spanning neurology,
# psychiatry, rehabilitation medicine, infectious disease, and general
# medicine. Predatory journals excluded via Beall's list at import.
# ---------------------------------------------------------------------------

JOURNALS = {}


# ---------------------------------------------------------------------------
# 3. Scopus / WoS queries — (label, scopus_query, wos_query)
#
# Scopus stems phrase plurals automatically. WoS does NOT — wildcards
# added to phrase tails where plurals matter (dysfunct*, impairment*,
# disabilit*, variabilit*, function*).
#
# Combined logic: Block1 AND (Block2 OR Block3) AND Block4
#   Block1 = Long COVID / PASC identity terms
#   Block2 = Neurocognitive symptom terms
#   Block3 = PEM / fatigue / dysautonomia terms
#   Block4 = Functional impairment / disability outcome terms
# ---------------------------------------------------------------------------

QUERY_DEFS = [
    (
        "Q1_long_covid_cognitive_functional",
        # Scopus
        'TITLE-ABS-KEY("long COVID" OR "long-COVID" OR "post-COVID" OR '
        '"post-acute COVID" OR "post-acute sequelae" OR "PASC" OR '
        '"post-COVID-19 syndrome" OR "chronic COVID" OR "COVID long hauler*") '
        'AND TITLE-ABS-KEY("brain fog" OR "cognitive dysfunction" OR '
        '"cognitive impairment" OR "neurocognitive" OR "memory impairment" OR '
        '"attention deficit" OR "processing speed" OR "executive function" OR '
        '"concentration difficul*" OR "post-exertional malaise" OR "PEM" OR '
        '"fatigue" OR "dysautonomia" OR "postural tachycardia" OR "POTS" OR '
        '"orthostatic intolerance" OR "heart rate variability" OR '
        '"autonomic dysfunction") '
        'AND TITLE-ABS-KEY("functional impairment" OR "functional disability" OR '
        '"disability" OR "activities of daily living" OR "ADL" OR '
        '"work capacity" OR "return to work" OR "quality of life" OR '
        '"patient-reported outcome*" OR "real-world function*")',
        # WoS
        'TS=("long COVID" OR "long-COVID" OR "post-COVID" OR '
        '"post-acute COVID" OR "post-acute sequelae" OR "PASC" OR '
        '"post-COVID-19 syndrome" OR "chronic COVID" OR "COVID long hauler*") '
        'AND TS=("brain fog" OR "cognitive dysfunct*" OR '
        '"cognitive impairment*" OR "neurocognitive" OR "memory impairment*" OR '
        '"attention deficit*" OR "processing speed" OR "executive function*" OR '
        '"concentration difficul*" OR "post-exertional malaise" OR "PEM" OR '
        '"fatigue" OR "dysautonomia" OR "postural tachycardia" OR "POTS" OR '
        '"orthostatic intolerance" OR "heart rate variabilit*" OR '
        '"autonomic dysfunction") '
        'AND TS=("functional impairment*" OR "functional disabilit*" OR '
        '"disabilit*" OR "activities of daily living" OR "ADL" OR '
        '"work capacity" OR "return to work" OR "quality of life" OR '
        '"patient-reported outcome*" OR "real-world function*")',
    ),
]


# ---------------------------------------------------------------------------
# 4. OpenAlex block terms
#
# OpenAlex's search= parameter is relevance-ranked. Two block queries
# (BLOCK_A = Long COVID + symptom identity, BLOCK_B = functional outcomes)
# are run separately then merged and deduped.
# ---------------------------------------------------------------------------

BLOCK_A_TERMS = [
    "long COVID",
    "post-acute sequelae SARS-CoV-2",
    "PASC",
    "post-COVID syndrome",
    "brain fog COVID",
    "post-exertional malaise COVID",
    "dysautonomia COVID",
    "cognitive dysfunction long COVID",
]

BLOCK_B_TERMS = [
    "functional impairment",
    "patient-reported disability",
    "return to work COVID",
    "quality of life long COVID",
    "activities of daily living COVID",
    "neurocognitive assessment long COVID",
]
