# CLV Model for New Acquisitions — Two Propositions

## Context

The existing CLV model predicts NBI over 3 years for **established clients** using quarterly behavioral data (NBI, transactions, products, activity). It integrates a retention sub-model: `CLV = Sigma NBI(t) * retention^t * discount^t`.

**Problem**: New clients (just joined the bank) have **zero historical data**. We only have:
- Demographics: age, gender, address/city, family situation
- Declarative: income range, profession/CSP
- Products subscribed at onboarding (no amounts)
- Channel: online (app/web) vs branch
- **Look-alike capability**: we CAN reconstruct existing clients' profiles at their own sign-up date and observe their actual NBI trajectory afterward

**Goal**: Design a model that predicts CLV for new clients from Day 0, then transitions to the established model when enough behavioral data accumulates.

---

## PROPOSITION A: Look-alike Cohort Model (Single-stage)

### Concept
One unified model trained on historical sign-up profiles of existing clients, predicting their 12-month NBI outcome. Simple, fast to deploy, single prediction at onboarding.

### 1. Training Data Construction

**Source**: Take all clients who joined the bank in 2022 and 2023 (from Stock files). For each:
- Reconstruct their **sign-up profile** (demographics, declared income, CSP, products at onboarding, channel)
- Compute their **actual NBI over the 12 months following sign-up** (from 2023 and 2024 Stock data respectively)
- Compute their **churn flag** at 12 months (present in Stock Y+1 or not)

**Train/test split**: Temporal — clients who joined in 2022 = train, clients who joined in 2023 = test. This mirrors real deployment (predict future from past).

**Target variables** (two models):
- **NBI model**: `nbi_year1` (continuous, EUR) — total NBI generated in the first 12 months
- **Retention model**: `churned_year1` (binary) — did the client leave within 12 months?

**Sample size**: Depends on bank's acquisition volume. Typically 10k-50k new clients/year for a mid-size French bank. Sufficient for gradient boosting.

### 2. Feature Engineering

#### Raw features from sign-up data
| Feature | Type | Encoding |
|---------|------|----------|
| `age` | numeric | as-is (years) |
| `gender` | binary | 0/1 (M/F) |
| `family_situation` | categorical | ordinal or one-hot: celibataire, marie, divorce, veuf, pacse |
| `income_range` | ordinal | numeric encoding of bracket midpoint (e.g., 0-15k=7500, 15-25k=20000, 25-40k=32500, 40-60k=50000, 60k+=75000) |
| `csp_category` | categorical | one-hot: cadre, employe, ouvrier, prof_liberale, commercant_artisan, retraite, etudiant, sans_emploi |
| `code_postal` | categorical | not used directly — used to join INSEE data |
| `channel_online` | binary | 1 if digital acquisition, 0 if branch |

#### Product mix at onboarding (binary flags)
| Feature | Description |
|---------|-------------|
| `has_compte_courant` | Current account (nearly always 1) |
| `has_livret_a` | Livret A savings |
| `has_livret_jeune` | Livret Jeune (if age < 25) |
| `has_assurance_vie` | Life insurance |
| `has_credit_immobilier` | Mortgage |
| `has_credit_conso` | Consumer credit |
| `has_carte_bancaire` | Debit/credit card |
| `has_assurance_habitation` | Home insurance |
| `has_assurance_auto` | Car insurance |
| `has_prevoyance` | Income protection |
| `n_products_onboarding` | Total count of products at sign-up |
| `n_product_families` | Number of distinct product families covered (out of 4) |

#### Product family aggregates (4 families)
| Feature | Products included |
|---------|------------------|
| `fam_everyday_banking` | 1 if has compte_courant OR carte_bancaire |
| `fam_savings_investments` | 1 if has livret_a OR livret_jeune OR assurance_vie |
| `fam_lending` | 1 if has credit_immobilier OR credit_conso |
| `fam_insurance_protection` | 1 if has assurance_habitation OR assurance_auto OR prevoyance |

#### Geographic enrichment (INSEE open data)
Join on `code_postal` or `code_commune` from INSEE Filosofi and Base Comparateur de Territoires:

| Feature | Source | Description |
|---------|--------|-------------|
| `median_income_commune` | INSEE Filosofi | Median disposable income in the commune (EUR) |
| `population_density` | INSEE | Inhabitants per km2 |
| `pct_cadres_commune` | INSEE RP | % of cadres in the commune's active population |
| `unemployment_rate_commune` | INSEE | Local unemployment rate |
| `urban_category` | INSEE | urban/periurban/rural (one-hot or ordinal) |

#### Interaction features
| Feature | Formula | Rationale |
|---------|---------|-----------|
| `income_x_products` | `income_range * n_products_onboarding` | High income + many products = high NBI potential |
| `age_x_lending` | `age * fam_lending` | Age modulates lending NBI (mortgage age vs. young consumer credit) |
| `digital_x_age` | `channel_online * age` | Young digital client vs. older digital client = different behavior |
| `income_above_commune` | `income_range - median_income_commune` | Client's income relative to local norm |

#### Summary: ~25-30 features total

### 3. Model Architecture

**NBI Prediction (regression)**:
```
Model: GradientBoostingRegressor
Params: n_estimators=300, max_depth=4, learning_rate=0.05, 
        subsample=0.8, min_samples_leaf=20
Target: nbi_year1 (EUR, continuous)
Loss: huber (robust to NBI outliers)
```

Why GBRegressor:
- Handles mixed feature types (numeric + encoded categorical)
- Robust to outliers with Huber loss
- Consistent with existing model's sklearn approach
- Interpretable feature importances

**Alternative considered**: Predict log(NBI+1) with squared loss instead of Huber. Test both, keep better MAE.

**Retention Prediction (classification)**:
```
Model: GradientBoostingClassifier
Params: n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, min_samples_leaf=20
Target: churned_year1 (binary)
```
Same architecture as the established retention model, just different features.

**Product family sub-models**: NOT recommended for Proposition A. With only sign-up features, there isn't enough signal to justify 4 separate NBI sub-models. Use a single unified model. The product family flags serve as input features instead.

### 4. Retention Sub-model for New Clients

**Key insight**: First-year churn for new clients is typically 15-25% (vs. 3-5% for established clients). The survival curve shape is different — high early attrition that stabilizes ("bathtub curve").

**Approach**:
- Train GBClassifier on `churned_year1` (left the bank within 12 months of sign-up)
- Output: `retention_score_new = 1 - P(churn_year1)` in [0, 1]
- For 3-year CLV projection, use a **modified survival curve** specific to new clients:
  - `S(1) = retention_score_new` (model output)
  - `S(2) = S(1) * retention_established` (after year 1, they behave like established clients)
  - `S(3) = S(2) * retention_established`
  - Where `retention_established` comes from the existing model (e.g., ~0.95 annual for surviving clients)

**Formula**:
```
CLV_new = NBI_pred(1) * S(1) / (1.05)^1
        + NBI_pred(2) * S(2) / (1.05)^2
        + NBI_pred(3) * S(3) / (1.05)^3

Where:
  NBI_pred(1) = model prediction from sign-up features
  NBI_pred(2) = NBI_pred(1) * growth_factor  (cohort average NBI growth Y1->Y2)
  NBI_pred(3) = NBI_pred(2) * growth_factor
  S(1) = retention_score_new
  S(2) = S(1) * 0.95  (established retention rate)
  S(3) = S(2) * 0.95
```

The `growth_factor` is estimated from historical cohort data (average NBI evolution from year 1 to year 2 for clients who stayed).

### 5. Output Format

| Column | Type | Description |
|--------|------|-------------|
| `client_id` | str | Client identifier |
| `nbi_pred_year1` | float | Predicted first-year NBI (EUR) |
| `nbi_pred_year2` | float | Projected Year 2 NBI |
| `nbi_pred_year3` | float | Projected Year 3 NBI |
| `retention_score_new` | float | P(retained after year 1) |
| `survival_year1` | float | = retention_score_new |
| `survival_year2` | float | = S(1) * 0.95 |
| `survival_year3` | float | = S(2) * 0.95 |
| `clv_total` | float | 3-year discounted CLV |
| `model_type` | str | "new_acquisition_v1" |

Compatible with existing `compute_clv_with_retention()` in `model/retention_model.py`.

### 6. External Data Enrichment

| Source | Data | Join key |
|--------|------|----------|
| **INSEE Filosofi** | Median income, poverty rate, Gini per commune | code_commune |
| **INSEE Recensement** | CSP distribution, age pyramid, education level per commune | code_commune |
| **Code postal -> commune** | Mapping table (one postal code can map to multiple communes) | code_postal |
| **Base Comparateur** | Population density, urban/rural classification | code_commune |

All open data, free, CSV download. Stable yearly release.

### 7. Transition Strategy

Simple:
- **Month 0-12**: Use Proposition A model (sign-up features only)
- **Month 12+**: Client has 4 quarters of behavioral data -> switch to the established CLV model
- No blending — hard cutover at the 12-month mark
- The `model_type` column tracks which model produced each client's CLV

### 8. Implementation

**Files to create**:
- `simplified/new_acq_data_preparation.py` — Build training set from historical cohorts
- `simplified/new_acq_clv_model.py` — Feature engineering + NBI regression + retention classification + CLV computation

**Dependencies**: `simplified/data_processing.py` (for Stock loading), `model/retention_model.py` (for CLV formula)

---

## PROPOSITION B: Two-phase Progressive Model

### Concept
Two distinct model phases that activate as data accumulates, with a smooth transition:
- **Phase 1 (Day 0)**: Pure declarative prediction — identical to Proposition A
- **Phase 2 (Month 3-6)**: Early behavioral signals from the client's first transactions enrich the prediction
- **Graduation (Month 12)**: Client transitions to the established CLV model

The key advantage: Phase 2 captures **early engagement signals** that are strongly predictive of long-term value (a client who starts transacting heavily in month 2 is very different from one who never activates their card).

### 1. Training Data Construction

**Phase 1 training set**: Same as Proposition A (sign-up features -> 12-month NBI outcome).

**Phase 2 training set**: For clients who joined in 2022-2023, reconstruct:
- Their **sign-up profile** (same features as Phase 1)
- Their **first 3-6 months of behavioral data**: transactions, NBI, product activations, channel usage
- Their **12-month NBI outcome** (target)
- Their **12-month churn flag** (target)

This means Phase 2 uses a **richer feature set** = sign-up features + early behavioral features.

**Train/test split**: Same temporal approach (2022 = train, 2023 = test).

### 2. Feature Engineering

#### Phase 1 features: Same as Proposition A (~25-30 features)

#### Phase 2 additional features (first 3-6 months of behavior)

**Early NBI signals** (first 90 or 180 days):
| Feature | Description |
|---------|-------------|
| `nbi_first_quarter` | Total NBI in first 3 months (EUR) |
| `nbi_month1` | NBI in month 1 only |
| `nbi_ramp_rate` | nbi_month3 / nbi_month1 (how fast NBI grows, >1 = ramping up) |
| `log_nbi_first_quarter` | log1p(nbi_first_quarter) |

**Early transaction signals**:
| Feature | Description |
|---------|-------------|
| `n_txn_first_quarter` | Transaction count in first 3 months |
| `days_to_first_txn` | Days between account opening and first transaction |
| `txn_frequency` | n_txn_first_quarter / days_active |
| `has_recurring_txn` | 1 if at least one recurring payment set up (salary, bills) |
| `has_salary_domiciliation` | 1 if salary detected (largest monthly incoming transfer) |

**Product activation signals**:
| Feature | Description |
|---------|-------------|
| `n_products_month3` | Number of products active at month 3 |
| `products_added` | n_products_month3 - n_products_onboarding (cross-sell early) |
| `card_activated` | 1 if debit card used at least once |
| `savings_funded` | 1 if any savings product has a balance > 0 |
| `has_direct_debit` | 1 if at least one direct debit set up |

**Engagement signals**:
| Feature | Description |
|---------|-------------|
| `digital_logins_month1` | Number of app/web logins in first month |
| `channel_usage_digital_pct` | % of interactions that are digital |
| `contacted_advisor` | 1 if had a meeting/call with advisor |

**Key signal: salary domiciliation** — If the client routes their salary through the bank within the first 3 months, this is the single strongest predictor of long-term value and retention. It indicates the bank is their primary bank, not a secondary account.

#### Phase 2 total: ~25 sign-up features + ~15 early behavioral features = ~40 features

### 3. Model Architecture

**Phase 1**: Same as Proposition A (GBRegressor for NBI, GBClassifier for retention).

**Phase 2**:
```
NBI Model: GradientBoostingRegressor
Params: n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, min_samples_leaf=15
Target: nbi_year1 (remaining 9 months extrapolated to full year)
        OR nbi_remaining = nbi_year1 - nbi_first_quarter
Loss: huber
```

Using `nbi_remaining` as target (predicting only the remaining NBI to add to already-observed NBI) avoids information leakage and produces a more precise prediction.

**Phase 2 Retention**:
```
Model: GradientBoostingClassifier
Params: n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.8, min_samples_leaf=15
Target: churned_year1 (binary)
```

Phase 2 model is deeper (max_depth=5) and has more estimators because it has more features and should be more accurate.

**Product family sub-models**: In Phase 2, with early behavioral data, it becomes viable to predict NBI **per product family** (4 sub-models). This is optional — test whether it improves accuracy vs. the unified model.

### 4. Retention Sub-model for New Clients

Same approach as Proposition A but with **two-tiered precision**:

**Phase 1 (Day 0)**:
- `retention_score_new_p1 = 1 - P(churn | sign-up features)`
- Broad estimate based on demographics and products

**Phase 2 (Month 3-6)**:
- `retention_score_new_p2 = 1 - P(churn | sign-up + early behavioral)`
- Much more precise — clients who haven't activated their card or routed salary by month 3 are at very high churn risk
- **Early warning**: flag clients with `retention_score_new_p2 < 0.5` for proactive outreach

**3-year survival projection (Phase 2)**:
```
S(1) = retention_score_new_p2
S(2) = S(1) * retention_established
S(3) = S(2) * retention_established
```

**Actionable insight**: The gap between Phase 1 and Phase 2 retention scores reveals the impact of early engagement. Clients whose score drops from P1 to P2 = poor onboarding experience -> intervention opportunity.

### 5. Output Format

| Column | Type | Description |
|--------|------|-------------|
| `client_id` | str | Client identifier |
| `model_phase` | str | "phase1" or "phase2" |
| `nbi_pred_year1` | float | Predicted first-year NBI |
| `nbi_pred_year2` | float | Projected Year 2 NBI |
| `nbi_pred_year3` | float | Projected Year 3 NBI |
| `retention_score_new` | float | P(retained after year 1) — from whichever phase is active |
| `survival_year1` | float | = retention_score_new |
| `survival_year2` | float | = S(1) * retention_established |
| `survival_year3` | float | = S(2) * retention_established |
| `clv_total` | float | 3-year discounted CLV |
| `confidence` | str | "low" (phase1) / "medium" (phase2) / "high" (established) |
| `salary_domiciliation` | bool | Key flag for commercial teams |
| `early_churn_risk` | bool | retention_score < 0.5 at Phase 2 |
| `model_type` | str | "new_acquisition_phase1" or "new_acquisition_phase2" |

### 6. External Data Enrichment

Same as Proposition A (INSEE Filosofi, Recensement, urbanization), plus:

| Source | Data | Use in Phase 2 |
|--------|------|-----------------|
| **Banque de France** | Average household debt by departement | Benchmark client's lending behavior vs. local average |
| **Open banking benchmarks** | Average # of bank products per age group (industry stats) | Feature: client's product count vs. expected for their age/CSP |

### 7. Transition Strategy

**Timeline**:
```
Day 0          -> Phase 1 prediction (sign-up features only)
Month 3        -> Phase 2 kicks in (re-score with early behavioral data)
Month 6        -> Phase 2 refresh (re-score with 6 months of data)
Month 12       -> Graduate to established CLV model
```

**Blending during transition** (Month 12):
```
CLV_transition = alpha * CLV_new_model + (1 - alpha) * CLV_established_model

Where alpha decreases over months 10-14:
  Month 10: alpha = 1.0 (100% new model)
  Month 11: alpha = 0.75
  Month 12: alpha = 0.50
  Month 13: alpha = 0.25
  Month 14: alpha = 0.0 (100% established model)
```

This 5-month blending window avoids a jarring CLV jump when switching models.

**Trigger for graduation**: Client has at least 4 quarters of NBI data AND at least 10 transactions in the last quarter (minimum behavioral data for the established model to be meaningful).

### 8. Implementation

**Files to create**:
- `simplified/new_acq_data_preparation.py` — Build training sets for Phase 1 and Phase 2 from historical cohorts
- `simplified/new_acq_phase1_model.py` — Phase 1: sign-up features -> NBI + retention
- `simplified/new_acq_phase2_model.py` — Phase 2: sign-up + early behavioral features -> NBI + retention
- `simplified/new_acq_transition.py` — Blending logic and graduation to established model
- `simplified/new_acq_scoring.py` — Score new clients, select correct phase, output unified format

**Dependencies**: `simplified/data_processing.py`, `model/retention_model.py`

---

## Recommendation

**Start with Proposition A** — it's simpler, faster to deploy, and validates the core look-alike hypothesis. If Proposition A shows good accuracy (MAE within 20% of actual NBI, AUC > 0.70 for retention), then build Proposition B as a V2 upgrade.

Proposition B's Phase 2 is where the real value lies (early behavioral signals, especially salary domiciliation, are extremely predictive), but it requires more data engineering and operational complexity (re-scoring clients at month 3 and 6).

**Recommended sequence**: Proposition A -> validate -> Proposition B Phase 2.

---

## Verification Plan

1. **Data preparation**: Load historical cohorts, verify feature coverage (% non-null per feature), verify NBI distribution of new vs. established clients
2. **Model training**: Train on 2022 cohort, test on 2023 cohort, report MAE/RMSE for NBI, AUC/Brier for retention
3. **Sanity checks**: Average predicted NBI should be within 10% of actual cohort average; retention model should show higher churn for new clients than the established model
4. **Integration test**: Feed predictions into `compute_clv_with_retention()` and verify output format matches existing pipeline
5. **Business validation**: Compare predicted CLV distribution against actual observed CLV for the 2023 test cohort
