"""Screening configuration — AI/ML for PROMs following TKA and THA.

Systematic review: Artificial Intelligence and Machine Learning for
Predicting Patient-Reported Outcomes Following Total Knee and Total
Hip Arthroplasty.

TWO-REVIEWER MODEL:
    Stage 1 (abstract) and Stage 2 (full text) each use independent
    human screening *in addition* to Claude-assisted pre-screening.
    Workflow:
      1. Claude pre-screens all titles/abstracts → outputs include /
         borderline / exclude with reason.
      2. Reviewer 1 (R1) and Reviewer 2 (R2) independently screen
         each abstract using the same PICOS criteria encoded below.
      3. Compute inter-rater agreement: Cohen's kappa target ≥ 0.80
         before proceeding. Use the kappa worksheet in screening/kappa.xlsx.
      4. Disagreements resolved by consensus meeting; arbitration by
         senior author if unresolved.
      5. Full-text stage repeats the same dual-review process.
    Track kappa by stage in manuscript_stats.py → s['kappa.abstract']
    and s['kappa.fulltext'].

PIPELINE USAGE:
    uv run ${CLAUDE_PLUGIN_ROOT}/scripts/pipelines/abstract_screen.py \\
        --config ./screening_config.py --group <id> --collection <key>

    uv run ${CLAUDE_PLUGIN_ROOT}/scripts/pipelines/fulltext_code.py \\
        --config ./screening_config.py --group <id> --collection <key>
"""

# =============================================================================
# Abstract screening (Stage 1)
# Claude Haiku pre-screens; human reviewers apply the same criteria.
# =============================================================================

ABSTRACT_SCREENING_MODEL = "claude-haiku-4-5-20251001"
ABSTRACT_SCREENING_PROMPT_VERSION = "v1-2026-05-20"

ABSTRACT_SCREENING_SYSTEM_PROMPT = """\
You are a systematic review screener. Your task is to decide whether a \
paper is relevant to the following review:

**Research question:** Do artificial intelligence or machine learning \
models accurately predict patient-reported outcomes (PROMs) following \
total knee arthroplasty (TKA) or total hip arthroplasty (THA)?

A paper is relevant only if ALL THREE criteria are met:

1. PROCEDURE: The study population underwent TKA and/or THA (primary or \
revision). NOT relevant: shoulder, spine, ankle, upper-limb arthroplasty, \
unicompartmental knee arthroplasty (UKA) as the sole procedure, or \
osteotomy only.

2. METHOD: The study develops, validates, or benchmarks at least one AI \
or ML model (e.g. random forest, neural network, gradient boosting, \
XGBoost, support vector machine, logistic regression as ML baseline, \
deep learning). NOT relevant: purely statistical models with no ML \
component (e.g. linear regression, Cox regression alone), clinical \
prediction rules without ML, biomechanical simulations.

3. OUTCOME: The primary or a key secondary outcome is a patient-reported \
outcome measure (PROM) — e.g. KOOS, KOOS-PS, HOOS, HOOS-PS, OKS \
(Oxford Knee Score), OHS (Oxford Hip Score), WOMAC, SF-36, SF-12, \
EQ-5D, VR-12, PROMIS, or similar validated patient-reported instrument. \
NOT sufficient: purely clinical outcomes (range of motion, implant \
survival, complications, length of stay, readmission) with no PROM.

DECISION RULES:
- INCLUDE: all three criteria clearly met in the abstract.
- EXCLUDE: at least one criterion clearly absent. Use the code:
  E1 — wrong procedure (not TKA or THA)
  E2 — no AI/ML method (statistical model only, simulation, imaging AI
       with no PROM prediction)
  E3 — no PROM outcome (clinical outcomes only)
  E4 — wrong study type (review, editorial, letter, protocol, commentary,
       conference abstract without data)
  E5 — duplicate or retracted
  E6 — non-English, no translation available
- BORDERLINE: abstract is insufficient to decide (no abstract, mixed \
population, outcome ambiguous, AI used but unclear if PROM predicted).

BIAS: Be liberal. Prefer include or borderline over exclude when in \
doubt — a missed relevant paper is more costly than reading one extra \
full text.

Respond with EXACTLY two lines:
DECISION: include|borderline|exclude
REASON: <one sentence citing which criterion or exclusion code applies>
"""


# =============================================================================
# Full-text coding (Stage 2)
# Claude Sonnet extracts structured data; human reviewers verify.
# =============================================================================

FULLTEXT_CODING_MODEL = "claude-sonnet-4-6"
FULLTEXT_CODING_PROMPT_VERSION = "v1-2026-05-20"

# FLAG: studies that report no quantitative model performance metric
# (AUC, C-statistic, RMSE, R², accuracy, F1, sensitivity/specificity,
# calibration) are flagged in the 'performance_metric_flag' field.
# These studies may still be included but are noted in the risk-of-bias
# narrative as lacking reportable performance.
FLAG_MISSING_PERFORMANCE_METRIC = True

FULLTEXT_CODING_FIELDS = [
    # ---- Study design ----
    {
        "name": "joint_type",
        "description": (
            "Procedure studied. One of: 'TKA', 'THA', 'TKA and THA', "
            "'TKA (revision)', 'THA (revision)', 'mixed (specify)'. "
            "If both primary and revision are included together, note that."
        ),
    },
    {
        "name": "country",
        "description": (
            "Country or countries where data were collected. "
            "Example: 'USA', 'UK', 'multicenter — USA, Canada, UK'."
        ),
    },
    {
        "name": "study_design",
        "description": (
            "Overall design. Examples: 'retrospective cohort', "
            "'prospective cohort', 'registry-based retrospective', "
            "'RCT secondary analysis', 'cross-sectional'."
        ),
    },
    {
        "name": "sample_size",
        "description": (
            "Total number of patients (or procedures if reported per limb). "
            "Provide the training + test set total if split is reported, "
            "e.g. '1,840 (1,380 train / 460 test)'."
        ),
    },
    # ---- AI/ML model ----
    {
        "name": "ai_method",
        "description": (
            "The AI/ML algorithm(s) used. Be specific: "
            "'random forest', 'gradient boosting (XGBoost)', "
            "'feedforward neural network (3 hidden layers)', "
            "'logistic regression (ML baseline)', 'ensemble (RF + XGBoost)'."
        ),
    },
    {
        "name": "input_features",
        "description": (
            "Key preoperative predictor variables fed into the model. "
            "Summarise in one to two sentences: demographics, comorbidities, "
            "baseline PROM scores, surgical variables, imaging findings, etc."
        ),
    },
    {
        "name": "validation_method",
        "description": (
            "How model performance was assessed. One of: "
            "'internal (random split)', 'internal (k-fold CV)', "
            "'internal (temporal split)', 'external (separate cohort)', "
            "'external (separate institution)', 'none reported'."
        ),
    },
    # ---- Outcome ----
    {
        "name": "outcome_measure",
        "description": (
            "The specific PROM(s) predicted. Include instrument name, "
            "subscale if applicable, and follow-up time point. "
            "Example: 'KOOS-PS at 12 months', 'OKS at 6 months', "
            "'HOOS-PS at 1 year and 2 years'."
        ),
    },
    {
        "name": "prediction_target",
        "description": (
            "What the model predicts. One of: "
            "'continuous score (regression)', "
            "'binary outcome (MCID achieved yes/no)', "
            "'class (good / fair / poor)', "
            "'change score from baseline', 'other (specify)'."
        ),
    },
    {
        "name": "follow_up_months",
        "description": (
            "Primary follow-up duration in months. "
            "Example: '12', '24', '6 and 12', 'unclear'."
        ),
    },
    # ---- Performance ----
    {
        "name": "performance_metric",
        "description": (
            "All quantitative performance metrics reported. "
            "List metric name and value: "
            "'AUC 0.78 (95% CI 0.73–0.83)', 'RMSE 8.4', 'R² 0.41', "
            "'accuracy 74%', 'C-statistic 0.80'. "
            "If NO performance metric is reported, write exactly: "
            "'NONE REPORTED' — this triggers the risk-of-bias flag."
        ),
    },
    {
        "name": "performance_metric_flag",
        "description": (
            "Set to 'FLAGGED' if performance_metric is 'NONE REPORTED'. "
            "Otherwise 'OK'. This flag feeds the risk-of-bias audit."
        ),
    },
    {
        "name": "best_performing_model",
        "description": (
            "Name and key metric of the best-performing model reported, "
            "if the study compares multiple algorithms. "
            "Example: 'XGBoost, AUC 0.82'. Write 'N/A' if only one model."
        ),
    },
    # ---- Risk of bias (PROBAST) ----
    {
        "name": "probast_participants",
        "description": (
            "PROBAST Domain 1 — Participants. "
            "Rate 'Low', 'High', or 'Unclear' risk of bias. "
            "Consider: consecutive or random sampling? Exclusions appropriate? "
            "Case-control design avoided? Appropriate case definition?"
        ),
    },
    {
        "name": "probast_predictors",
        "description": (
            "PROBAST Domain 2 — Predictors. "
            "Rate 'Low', 'High', or 'Unclear'. "
            "Consider: predictor definitions pre-specified? Blinded to outcome "
            "at time of measurement? No predictors selected post hoc?"
        ),
    },
    {
        "name": "probast_outcome",
        "description": (
            "PROBAST Domain 3 — Outcome. "
            "Rate 'Low', 'High', or 'Unclear'. "
            "Consider: validated PROM used? Outcome defined before model "
            "development? Adequate follow-up duration and completeness (>80%)?"
        ),
    },
    {
        "name": "probast_analysis",
        "description": (
            "PROBAST Domain 4 — Analysis. "
            "Rate 'Low', 'High', or 'Unclear'. "
            "Consider: sample size adequate for number of predictors? "
            "Missing data handled appropriately? No overfitting (internal "
            "validation performed)? Performance measures appropriate?"
        ),
    },
    {
        "name": "probast_overall",
        "description": (
            "Overall PROBAST risk of bias. 'Low' only if all 4 domains are "
            "Low. 'High' if any domain is High. 'Unclear' otherwise."
        ),
    },
    # ---- Synthesis ----
    {
        "name": "key_findings",
        "description": (
            "Two to four sentences summarising the study's main findings: "
            "what model performed best, what predictors mattered most, "
            "whether MCID achievement was predicted accurately, "
            "any subgroup differences (e.g. TKA vs THA, age, BMI). "
            "Paraphrase from the Results and Discussion sections."
        ),
    },
    {
        "name": "limitations",
        "description": (
            "Author-stated limitations most relevant to generalisability: "
            "retrospective design, single-centre data, short follow-up, "
            "lack of external validation, missing preoperative PROM data, etc. "
            "One to three sentences."
        ),
    },
]

FULLTEXT_CODING_SYSTEM_PROMPT = """\
You are a systematic-review coder. You read the full text of a paper and \
extract a structured record for downstream analysis and narrative synthesis.

RESEARCH QUESTION:
Do artificial intelligence or machine learning models accurately predict \
patient-reported outcomes (PROMs) following total knee arthroplasty (TKA) \
or total hip arthroplasty (THA)?

FULL-TEXT INCLUSION CRITERIA (re-verify against complete paper):
  FT-1. Population: adults (≥18 years) undergoing primary or revision TKA \
and/or THA. Studies mixing arthroplasty with other procedures are included \
only if TKA/THA data are reported separately.
  FT-2. Method: at least one AI or ML model developed, validated, or \
benchmarked to predict a PROM (not just describe PROM distributions).
  FT-3. Outcome: at least one validated PROM (KOOS, KOOS-PS, HOOS, \
HOOS-PS, OKS, OHS, WOMAC, SF-36/12, EQ-5D, PROMIS, VR-12, or equivalent) \
is a primary or key secondary outcome of the ML model.
  FT-4. Quantitative study (not review, editorial, letter, protocol only).

FULL-TEXT EXCLUSION CODES:
  FE1 — population does not meet FT-1 on full text (e.g., only UKA, \
spine, or shoulder; paediatric only)
  FE2 — no ML model applied to PROM prediction; ML used only for imaging \
segmentation or implant classification with no PROM
  FE3 — no validated PROM outcome on full text (only complications, \
readmission, implant survival, range of motion)
  FE4 — not a quantitative study (protocol, review, commentary, editorial)
  FE5 — duplicate of an already-included study (note which)

IMPORTANT — PERFORMANCE METRIC FLAG:
If the paper reports NO quantitative model performance metric (no AUC, \
C-statistic, RMSE, R², accuracy, sensitivity/specificity, F1, or \
calibration statistic), set performance_metric to 'NONE REPORTED' and \
performance_metric_flag to 'FLAGGED'. Do not exclude the paper solely \
for this — flag it so reviewers can assess risk of bias in Domain 4.

OUTPUT FORMAT — strict JSON, one object:
{{
  "decision": "include" | "exclude",
  "exclusion_code": "<FE-code or empty string>",
  "reason": "<one to three sentences justifying the decision>",
  {coding_fields_json_placeholder}
}}

Rules:
- Provide substantive content for all coding fields if decision = include.
- For excluded papers, set all coding fields to empty strings.
- Do not paraphrase the abstract — extract from Methods, Results, Discussion.
- Return ONLY the JSON object, no prose before or after.
"""
