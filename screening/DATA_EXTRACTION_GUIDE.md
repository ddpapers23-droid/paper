# Data Extraction Guide
## Systematic Review: AI/ML for PROMs Following TKA and THA

Use `data_extraction_template.csv` — one row per included paper.

---

### Field codebook

#### Study identification
| Field | Instructions |
|---|---|
| `paper_id` | Use the # from fulltext_review.csv (e.g. 1, 2, 48) |
| `first_author` | Surname only |
| `country` | Country of the study population (not corresponding author's country) |

#### Study design
| Field | Allowed values |
|---|---|
| `study_design` | `retrospective` `prospective` `RCT` `registry` `other` |
| `setting` | `single-center` `multi-center` `national-registry` `international-registry` |
| `data_source` | `institutional-registry` `national-registry` `EHR` `prospective-cohort` `RCT` `other` |

#### Population
| Field | Instructions |
|---|---|
| `joint` | `TKA` `THA` `both` |
| `n_total` | Total patients in the study (not just training set) |
| `n_tka` / `n_tha` | Fill both if joint = both; leave blank if joint = single |
| `indication` | `OA` `RA` `mixed` `not-reported` |

#### ML method
| Field | Instructions |
|---|---|
| `ml_algorithms` | List all tested algorithms separated by commas |
| `best_algorithm` | The algorithm with the highest reported AUC/performance |
| `feature_types` | `clinical` `imaging` `clinical+imaging` `wearable` `NLP` `other` |
| `n_features_input` | Number of input variables fed to the model |
| `feature_selection` | `yes` `no` `not-reported` |
| `interpretability_reported` | Was SHAP, LIME, feature importance, or similar reported? `yes` `no` |

#### PROM
| Field | Instructions |
|---|---|
| `prom_instruments` | E.g. `KOOS` `HOOS` `WOMAC` `OKS` `OHS` `EQ-5D` `SF-36` `PROMIS` `VAS` `KSS` `HHS` |
| `prom_endpoint` | `absolute-score` (predicted raw score) `change-score` (Δ pre→post) `MCID-binary` (achieved/not) `satisfaction` `other` |
| `prom_timepoint_months` | Postoperative follow-up at which PROM was measured; use 0 for preoperative |
| `outcome_type` | `classification` (binary/categorical outcome) `regression` (continuous score) `clustering` |

#### Model performance
| Field | Instructions |
|---|---|
| `auc` | AUROC for best model (classification only); leave blank for regression |
| `accuracy` | Proportion correctly classified (0–1 or %) |
| `sensitivity` | True positive rate for best model |
| `specificity` | True negative rate for best model |
| `r2` | R² for regression models |
| `rmse` | Root mean squared error for regression models |
| `other_metric` | Name of any other metric reported (e.g. F1, Brier score, C-statistic) |
| `other_metric_value` | Corresponding value |
| `calibration_reported` | Was calibration assessed (e.g. Hosmer-Lemeshow, calibration plot)? `yes` `no` |

#### Validation
| Field | Allowed values |
|---|---|
| `validation_type` | `none` `train-test-split` `cross-validation` `bootstrap` `external` |
| `n_train` / `n_test` | Sizes of training and test sets |
| `external_validation` | `yes` `no` |

#### Risk of bias — PROBAST
Rate each domain as `low` `high` or `unclear`.

| Domain | What to assess |
|---|---|
| `probast_d1_participants` | Were eligible participants included without selection bias? |
| `probast_d2_predictors` | Were predictors defined and measured without knowledge of outcome? |
| `probast_d3_outcome` | Was the PROM outcome measured and defined appropriately? |
| `probast_d4_analysis` | Was the analysis appropriate (sample size, missing data, overfitting)? |
| `probast_overall` | If any domain is `high` → overall is `high`; all `low` → overall `low` |

Full PROBAST checklist: https://www.probast.org

#### Reporting
| Field | Instructions |
|---|---|
| `tripod_adherence` | Was TRIPOD reporting guideline followed? `full` `partial` `not-reported` |
| `code_available` | Was model code shared (GitHub etc.)? `yes` `no` `not-reported` |
| `data_available` | Was the dataset shared? `yes` `no` `not-reported` |

---

### Tips
- Extract data directly from the **Methods** and **Results** sections — not the abstract
- If multiple ML models are reported, record metrics for the **best-performing** model
- If a paper reports both TKA and THA results separately, create **two rows** (one per joint)
- For missing values, leave the cell blank — do not write "NR" or "N/A"
- Record your initials in `extractor_initials` and today's date in `extraction_date`
