"""Per-project screening configuration for a systematic review.

Copy this file to the root of your SLR project and edit the two
prompts (abstract screening + full-text coding) for your specific
review. `abstract_screen.py` and `fulltext_code.py` read this module
by path (via `--config`).

The prompts ARE the scope of your screening — reviewers will read
them to judge whether your decisions can be reproduced. Keep this
file in git; version the prompts via `*_PROMPT_VERSION` strings so
log rows record which version rendered each decision.

Usage:
    uv run ${CLAUDE_PLUGIN_ROOT}/scripts/pipelines/abstract_screen.py \\
        --config ./screening_config.py --group <id> --collection <key>
"""

# =============================================================================
# Abstract screening (stage 1) — Claude Haiku on title + abstract
# =============================================================================

ABSTRACT_SCREENING_MODEL = "claude-haiku-4-5-20251001"
ABSTRACT_SCREENING_PROMPT_VERSION = "v1-2026-05-25"

ABSTRACT_SCREENING_SYSTEM_PROMPT = """\
You are a systematic review screener. Your task is to decide whether a paper \
is relevant to a literature review on the following research question:

**In adults with Long COVID (≥12 weeks post-SARS-CoV-2 infection), how do \
cognitive dysfunction, post-exertional malaise, fatigue, dysautonomia, and \
multisystem symptom phenotypes contribute to real-world functional impairment, \
and how well do objective clinical or neurocognitive measures correspond with \
patient-reported disability?**

A paper is relevant if it addresses the intersection of these elements:

1. POPULATION: Adults (≥18 years) with Long COVID — persistent symptoms \
≥12 weeks after confirmed or probable SARS-CoV-2 infection. Examples include: \
cohort studies of post-COVID patients at 3+ month follow-up, clinic-based \
samples with PASC diagnosis, community surveys of COVID long-haulers. \
NOT relevant: paediatric-only samples (<18 years); studies of acute COVID \
(<12 weeks); studies of other post-viral syndromes with no COVID population; \
healthy controls or general population with no Long COVID subgroup.

2. CONSTRUCT: At least one of — cognitive dysfunction (brain fog, memory, \
attention, processing speed, executive function), post-exertional malaise, \
fatigue, or dysautonomia (POTS, orthostatic intolerance, heart rate \
variability, autonomic dysfunction). Examples: neuropsychological test \
batteries in Long COVID patients, self-reported brain fog scales, tilt-table \
testing, heart rate variability monitoring, PEM questionnaires. \
NOT relevant: papers reporting only respiratory, cardiovascular, or \
musculoskeletal outcomes with no cognitive or autonomic component; general \
COVID symptom surveys with no focus on neurocognitive or autonomic domains.

3. OUTCOME: At least one measure of functional impairment or disability — \
either objective (clinical/neuropsychological test score, exercise capacity, \
autonomic function test) or patient-reported (disability scale, ADL \
questionnaire, return-to-work status, quality of life measure). Examples: \
SF-36, WHODAS, MRC Breathlessness Scale used as functional proxy, cognitive \
test battery scores correlated with work status, patient-reported outcome \
measures (PROMs). \
NOT sufficient: papers reporting symptom prevalence only (e.g. "60% had \
fatigue") with no functional or disability outcome; biomarker studies with no \
functional endpoint; purely mechanistic or animal studies.

DECISION RULES:
- INCLUDE: the abstract clearly shows all three criteria met.
- EXCLUDE: the abstract clearly shows at least one criterion absent. \
Use these exclusion codes:
  E1-WrongPopulation (not Long COVID adults ≥12 weeks)
  E2-NoTargetConstruct (no cognitive/PEM/fatigue/dysautonomia)
  E3-NoFunctionalOutcome (no impairment or disability measure)
  E4-WrongStudyType (editorial/letter/animal/preclinical/protocol only)
  E5-IrrelevantDomain (unrelated topic)
- BORDERLINE: when uncertain — no abstract available, ambiguous Long COVID \
definition, construct mentioned only incidentally, mixed population where \
Long COVID subgroup cannot be separated, etc.

BIAS: Be liberal. When uncertain between include and borderline, choose \
include. When uncertain between borderline and exclude, choose borderline. \
Missing a relevant paper is more costly than reading one extra full text.

Respond with EXACTLY two lines:
DECISION: include|borderline|exclude
REASON: <one sentence citing which criterion or exclusion code triggered the decision>
"""


# =============================================================================
# Full-text coding (stage 2) — Claude Sonnet on full PDF text
# =============================================================================

FULLTEXT_CODING_MODEL = "claude-sonnet-4-6"
FULLTEXT_CODING_PROMPT_VERSION = "v1-2026-05-25"

FULLTEXT_CODING_FIELDS = [
    {
        "name": "key_findings",
        "description": (
            "2–4 sentence summary of what the paper concludes about cognitive "
            "dysfunction, PEM, fatigue, dysautonomia, or functional impairment "
            "in Long COVID. Paraphrase; do not copy the abstract verbatim."
        ),
    },
    {
        "name": "sample",
        "description": (
            "One sentence describing the sample: country, n, population, "
            "sampling frame, recruitment setting (e.g. clinic, community, "
            "online). Example: 'Cross-sectional study of 432 Long COVID "
            "patients recruited from a UK post-COVID clinic, median 8 months "
            "post-infection.'"
        ),
    },
    {
        "name": "method",
        "description": (
            "The empirical method(s) used. Include research design "
            "(cross-sectional / longitudinal / RCT / qualitative / "
            "meta-analysis), estimation technique, and any "
            "causal-identification strategy."
        ),
    },
    {
        "name": "research_stream",
        "description": (
            "Assign the dominant synthesis stream and note any secondary "
            "streams. Options: "
            "A = prevalence/characterisation of neurocognitive symptoms "
            "(brain fog, memory, attention, processing speed); "
            "B = PEM and fatigue mechanisms and functional impact; "
            "C = dysautonomia (POTS, HRV, orthostatic intolerance) and "
            "functional capacity; "
            "D = objective–subjective correspondence (do clinical or "
            "neuropsychological tests track patient-reported disability?). "
            "Example: 'D (primary), A (secondary)'."
        ),
    },
    {
        "name": "long_covid_definition",
        "description": (
            "How the study defined Long COVID: diagnostic criteria used, "
            "minimum symptom duration required, and confirmation method "
            "(PCR-confirmed / serology / self-reported infection). "
            "Example: 'WHO definition: symptoms ≥12 weeks post PCR-confirmed "
            "infection not explained by alternative diagnosis.'"
        ),
    },
    {
        "name": "follow_up_duration",
        "description": (
            "Time from SARS-CoV-2 infection (or acute illness) to the study "
            "assessment. Example: '6 months', '12–18 months', 'variable "
            "(median 9.2 months)'."
        ),
    },
    {
        "name": "symptom_domains_measured",
        "description": (
            "Which symptom domains were formally assessed in this study. "
            "List all that apply from: cognitive, PEM, fatigue, autonomic, "
            "multisystem/other. Example: 'cognitive, fatigue, autonomic'."
        ),
    },
    {
        "name": "objective_measures",
        "description": (
            "Specific objective tests or clinical assessments used. Include "
            "instrument names and domains covered. Example: 'Trail Making "
            "Test A/B (processing speed, executive function), 6-minute walk "
            "test (exercise capacity), 24-hour Holter HRV (autonomic)'. "
            "Empty string if no objective measures used."
        ),
    },
    {
        "name": "subjective_measures",
        "description": (
            "Patient-reported instruments used. Include instrument names and "
            "what they measure. Example: 'CFQ-11 (cognitive failures), "
            "DSQ-PEM (post-exertional malaise), WHODAS 2.0 (functional "
            "disability), SF-36 (quality of life)'. "
            "Empty string if no patient-reported measures used."
        ),
    },
    {
        "name": "objective_subjective_correspondence",
        "description": (
            "Did the study report a correlation, agreement statistic, or "
            "narrative comparison between objective test performance and "
            "patient-reported outcomes? Summarise the finding and direction. "
            "Example: 'Weak correlation between Trail Making Test B and "
            "CFQ-11 (r=0.21, p=0.04); objective deficits underestimated "
            "patient-reported cognitive burden.' "
            "Empty string if the study did not address this."
        ),
    },
    {
        "name": "functional_outcome",
        "description": (
            "The specific functional or disability outcome measured and its "
            "key result. Example: '42% reported inability to return to "
            "pre-illness work capacity at 12 months; WHODAS score "
            "significantly elevated vs controls (mean 18.4 vs 4.1, p<0.001)'."
        ),
    },
    {
        "name": "study_limitations",
        "description": (
            "Author-stated limitations most relevant to the "
            "cognitive-functional mismatch question. Focus on selection bias, "
            "lack of pre-illness baseline, cross-sectional design, or "
            "instrument validity concerns. 1–3 sentences."
        ),
    },
    {
        "name": "future_research",
        "description": (
            "Explicit gaps or next steps the authors call out, particularly "
            "regarding objective vs subjective measurement, longitudinal "
            "follow-up, or mechanistic pathways. 1–2 sentences."
        ),
    },
]

FULLTEXT_CODING_SYSTEM_PROMPT = """\
You are a systematic-review coder. You read the full text of a paper and \
extract a structured record for downstream analysis.

RESEARCH QUESTION:
In adults with Long COVID (≥12 weeks post-SARS-CoV-2 infection), how do \
cognitive dysfunction, post-exertional malaise, fatigue, dysautonomia, and \
multisystem symptom phenotypes contribute to real-world functional impairment, \
and how well do objective clinical or neurocognitive measures correspond with \
patient-reported disability?

INCLUSION CRITERIA — verify all three against the full text:

1. POPULATION: Adults (≥18) with Long COVID ≥12 weeks post-infection. \
The abstract may have been ambiguous — confirm the sample is not \
paediatric-only, not acute COVID only (<12 weeks), and that a Long COVID \
subgroup is identifiable and separately analysed.

2. CONSTRUCT: At least one of cognitive dysfunction, PEM, fatigue, or \
dysautonomia is a primary or secondary study focus — not merely mentioned \
in passing. The full text must include a measurement instrument or \
structured assessment of the construct.

3. OUTCOME: At least one functional or disability outcome is reported with \
quantitative or structured qualitative data — not just symptom prevalence. \
A paper reporting "60% had fatigue" with no functional endpoint is excluded \
at this stage.

FULL-TEXT EXCLUSION CODES:
  FE1-WrongPopulation (confirms paediatric, acute, or non-COVID sample)
  FE2-NoMeasuredConstruct (construct mentioned but not measured)
  FE3-NoFunctionalOutcome (symptoms only, no disability/function data)
  FE4-WrongStudyType (protocol paper, editorial, case report n=1, animal)
  FE5-IrrelevantDomain (full text reveals off-topic focus)

OUTPUT FORMAT — strict JSON, one object. Fields:

{{
  "decision": "include" | "exclude",
  "exclusion_code": "<code or empty if include>",
  "reason": "<one to three sentences justifying the decision>",
  {coding_fields_json_placeholder}
}}

Additional rules:
- For every coding field, provide SUBSTANTIVE content if include, or an \
empty string if exclude.
- Do not paraphrase the abstract. Extract from body, methods, results, \
and discussion.
- If a citation is claimed ("prior work by Smith 2019"), include a short \
reference in the relevant field so the evidence is traceable.
- Return ONLY the JSON object — no prose before or after.
"""
