# Full-Text Review Guide
## Systematic Review: AI/ML for PROMs Following TKA and THA

### Your file
- **Reviewer 1** → use `fulltext_review_R1.csv`
- **Reviewer 2** → use `fulltext_review_R2.csv`

Do not share your decisions with the other reviewer until both are complete.

---

### How to review each paper

1. Open your CSV in Excel or Google Sheets
2. For each row, click the DOI link to retrieve the full text
3. Read the methods section carefully
4. Fill in the `decision` column with one of:
   - **include** — meets all four criteria below
   - **exclude** — fails one or more criteria
   - **uncertain** — cannot determine from full text (rare)
5. If excluding, briefly note which criterion failed in `exclusion_reason`
6. Use `notes` for anything worth flagging (e.g. "only validation study", "abstract only available")

---

### Inclusion criteria (ALL four must be met)

| # | Criterion | Examples of what qualifies |
|---|---|---|
| 1 | **Population**: patients undergoing primary TKA or THA | Primary elective arthroplasty; excludes revision, unicompartmental, shoulder/ankle |
| 2 | **Method**: AI or ML model developed or validated | Random forest, neural network, logistic regression used as ML, gradient boosting, deep learning, NLP, clustering — must be a predictive model, not just descriptive statistics |
| 3 | **Outcome**: a patient-reported outcome measure (PROM) predicted | KOOS, HOOS, WOMAC, OKS, OHS, EQ-5D, SF-36, PROMIS, VAS pain, satisfaction, MCID attainment |
| 4 | **Study type**: original research with results | Full papers and conference abstracts with data; excludes study protocols, editorials, narrative reviews, letters |

---

### Common exclusion reasons (use these exact phrases)

- `Not TKA/THA` — different procedure (revision, UKA, shoulder, ankle)
- `Not ML` — only traditional regression or descriptive statistics
- `Not PROM` — predicts radiological, surgical, or complication outcomes only
- `Protocol only` — describes planned study, no results yet
- `Review article` — systematic review or narrative review, not primary study
- `No full text` — could not access despite attempting via DOI + library

---

### Accessing full texts

1. Click the DOI link in the spreadsheet
2. If paywalled, try your institution's library proxy
3. Try [Unpaywall](https://unpaywall.org) browser extension (free, legal)
4. If still unavailable, mark `No full text` in exclusion_reason

---

### When you are done

Send your completed CSV back to the lead author. Do not look at the other reviewer's sheet first.

The lead author will calculate Cohen's kappa and convene a consensus meeting for any disagreements.

---

### Target timeline

Please complete your review within **[INSERT DATE]**.

Questions? Contact: [INSERT LEAD AUTHOR EMAIL]
