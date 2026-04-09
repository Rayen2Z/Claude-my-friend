# CLV Project — Complete Knowledge Base

This file contains all critical information about the CLV (Customer Lifetime Value) project for a retail bank in Luxembourg. Use it as a reference for context, decisions, architecture, and data.

---

## 1. Project Overview

**Goal**: Predict client NBI (Net Banking Income, called PNB in French) over a 3-year horizon for a retail bank in Luxembourg.

**CLV Formula**:
```
CLV = SUM(t=1..3) [ NBI(t) * retention_score^t * (1 + discount_rate)^(-t) ]

Where:
  discount_rate = 0.05 (5% annual)
  retention_score = 1 - P(churn), output of the retention sub-model
```

**Two CLV models**:
1. **Established clients**: Uses quarterly NBI, transaction, product, and activity data (12+ months of history)
2. **New acquisitions**: Cold-start model for clients with no historical data (only sign-up features)

**4 Product Families**:
1. Everyday Banking (compte courant, carte bancaire)
2. Savings & Investments (livret d'epargne, assurance-vie)
3. Lending (credit immobilier, credit consommation)
4. Insurance & Protection (MRH, auto, prevoyance)

---

## 2. Repository Structure

```
Claude-my-friend/
|
|-- CHURN_2023/             # Stock Y (2023), Stock Y+1 (2024), Upstreaming.csv
|-- CHURN_2024/             # Stock Y (2024), Stock Y+1 (2025), Upstreaming.csv
|-- CHURN_2025/             # Stock Y (2025), Stock Y+1 (2026), Upstreaming.csv
|
|-- simplified/             # Notebook-style files (# %% cells) for Jupyter
|   |-- data_processing.py          # Stock CSV loading, churn derivation
|   |-- h3_constant_hazard.py       # Hypothesis H3: constant hazard test
|   |-- h5_churn_definition.py      # Hypothesis H5: churn definition quality
|   |-- h7_data_quality.py          # Hypothesis H7: data quality checks
|   |-- v0_churn_model.py           # V0 churn/retention model (GBClassifier)
|   |-- ROI_simulation.py           # Business case / ROI justification
|
|-- Acquisition_model/      # New acquisitions CLV model
|   |-- propositions_clv_nouvelles_acquisitions.md   # French propositions doc
|   |-- new_acq_data_preparation.py    # Shared data loading & feature engineering
|   |-- new_acq_model_a.py            # Proposition A: look-alike cohort model
|   |-- new_acq_phase1_model.py        # Proposition B Phase 1: declarative
|   |-- new_acq_phase2_model.py        # Proposition B Phase 2: early behavioral
|   |-- new_acq_transition.py          # Transition & blending logic
|   |-- new_acq_scoring.py             # Unified scoring pipeline
|   |-- justification_des_choix.md     # Defense of all technical choices
|   |-- project_knowledge.md           # This file
|
|-- model/
|   |-- retention_model.py     # Production retention model + CLV integration
|
|-- data_pipeline/
|   |-- load_churn_csvs.py     # Production CSV loader
|   |-- churn_data_pipeline.py # Pipeline: Stock mode + transaction fallback
|
|-- sql/
|   |-- 01_derive_churn_monthly.sql    # SAP BI query: monthly churn derivation
|   |-- 02_build_annual_churn_features.sql  # Annual feature structure
|
|-- docs/
|   |-- new_acquisitions_clv_propositions.md  # English propositions doc
|
|-- requirements.txt
|-- run_validation.py
```

---

## 3. Data Architecture

### Stock CSV Files
Each CHURN_YYYY folder contains:
- `Stock YYYY.csv` — All clients at the start of year YYYY
- `Stock YYYY+1.csv` — All clients at the start of the following year
- `Upstreaming.csv` — Clients who migrated to VIP (upstream) during the year

### Churn Derivation Logic
```
Client in Stock Y:
  -> In Stock Y+1          => churned = 0 (retained)
  -> In Upstreaming         => churned = 0, is_upstreamed = 1 (VIP migration, NOT churn)
  -> NOT in Y+1 AND NOT up  => churned = 1 (churned)
```

**Critical**: Upstream clients are treated as RETAINED, not churned. Treating them as churned would contaminate the model (high-NBI clients flagged as leaving = inverted retention scores).

### Client ID Detection
Auto-detects from: `client_id`, `clientid`, `id_client`, `customer_id`, `cust_id`, `id`, `no_client`, `num_client`.

### Column Auto-detection
Churn column: auto-detects `churned` or `churned_next_year` (the `_churn_col()` pattern used across all files).

---

## 4. Established Model (v0_churn_model.py)

### Features
**NBI**: `nbi_q1..q4`, `nbi_annual`, `nbi_momentum` (q4-q1), `nbi_volatility` (std), `log_nbi` (log1p)
**Transactions**: `n_transactions_q1..q4`, `total_txn`, `txn_per_quarter`, `txn_trend` (q4-q1)
**Products**: `n_products_q1..q4`, `max_products`, `product_trend` (q4-q1)
**Activity**: `active_q1..q4`, `quarters_active`, `recent_activity` (active_q4)
**Engagement**: `engagement_score` = mean(quarters_active/4, max_products/max)

### Model
```python
GradientBoostingClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    subsample=0.8, min_samples_leaf=20, random_state=42
)
```

### Output
- `retention_score = 1 - P(churn)` in [0, 1]
- `retention_3yr = retention_score^3` (constant hazard assumption)

### CLV Integration (model/retention_model.py)
```python
compute_clv_with_retention(nbi_predictions, retention_scores, discount_rate=0.05, horizon=3)
# For each year t: clv_component = nbi_year_t * retention^t * (1.05)^(-t)
# clv_total = sum of components
```

---

## 5. Hypothesis Validation Results

### H5 — Churn Definition Quality (VALIDATED)
- Churn rate stable across years: ~1.38% (low, which is good)
- 3.5% of churned clients had near-zero NBI (the churn flag is meaningful)
- NBI distribution differs significantly between churned and retained clients

### H3 — Constant Hazard Assumption (BORDERLINE)
- Kaplan-Meier survival: [0.92, 0.86, 0.82] at years 1, 2, 3
- Hazard ratio P2/P1 = 0.809 (below 0.85 threshold = decelerating hazard)
- **V1 acceptable** with p^t assumption
- **V2 upgrade**: Weibull survival S(t) = exp(-(t/lambda)^k), needed when k < 1
- Weibull formula note: t = time horizon (years), NOT the churn rate. The churn rate is absorbed into lambda during fitting.

### H7 — Data Quality (VALIDATED)
- Missing values acceptable
- No duplicate client IDs within a year
- NBI consistency verified
- Churned + upstreamed overlap checked (none)

---

## 6. ROI Simulation Results

### Key Constants
- Survival rates: [0.92, 0.86, 0.82]
- Discount rate: 5%
- Max retention spend: < 50% of NBI preserved (ROI = 2x)

### Framework
- NBI concentration measured via Pareto/Lorenz
- Churn analyzed by NBI segment (top 1%, 5%, 10%, 20%, bottom 50%)
- Multi-scenario: 0.5pp, 1.0pp, 1.5pp, 2.0pp, 3.0pp churn reduction
- 3-year CLV impact: NBI preserved * survival * discount per saved client

---

## 7. New Acquisitions Model

### The Problem (Cold Start)
New clients have zero transaction history. Available data:
- Demographics: age, gender, commune, family situation
- Declarative: income range, CSP category
- Products at onboarding (no amounts)
- Channel: digital (app/web) vs branch (binary)
- Look-alike: can reconstruct existing clients' sign-up profiles

### Proposition A — Look-alike Cohort (Single-stage)
- Single GBRegressor (PNB) + GBClassifier (retention)
- ~30 features: demographics, income, CSP, products, channel, STATEC geographic, interactions
- Temporal split: oldest cohort = train, newest = test
- Survival: S(1)=retention, S(2)=S(1)*0.95, S(3)=S(2)*0.95
- Hard cutover to established model at month 12

### Proposition B — Two-phase Progressive
- **Phase 1 (Day 0)**: Same as Proposition A
- **Phase 2 (Month 3-6)**: Adds ~15 behavioral features (early PNB, transactions, salary domiciliation, card activation, digital engagement)
- GBRegressor (n=400, depth=5) + GBClassifier (n=300, depth=5) for Phase 2
- Key signal: `a_domiciliation_salaire` (salary routed through bank)
- Blending window months 10-14: linear alpha from 100% new to 100% established
- Graduation: needs 4 quarters of data + minimum activity

### Key Parameters
```python
DISCOUNT_RATE = 0.05
RETENTION_ESTABLISHED = 0.95  # post year-1 annual retention
GROWTH_FACTOR = 1.10          # PNB year-over-year growth for new clients
```

---

## 8. Luxembourg Context

### Key Differences from France
- **Statistics office**: STATEC (not INSEE)
- **Open data portal**: data.public.lu (not data.gouv.fr)
- **Communes**: ~100 communes in Luxembourg (vs 35,000 in France)
- **Cross-border workers (frontaliers)**: ~45% of workforce commutes from France, Belgium, Germany
- **Income levels**: Luxembourg GDP per capita is highest in EU; income brackets are higher
- **Languages**: French, German, Luxembourgish (all used in banking)
- **Regulatory**: CSSF (Commission de Surveillance du Secteur Financier), not AMF/ACPR

### Luxembourg-specific Features
- `est_frontalier` (binary): critical signal for PNB and retention
- `nationalite`: luxembourgeois, francais, belge, allemand, portugais (largest foreign community), autre
- `pays_residence`: Luxembourg, France, Belgique, Allemagne
- `pct_frontaliers_commune`: % of cross-border workers in the commune
- Income brackets adjusted for Luxembourg: 0-30k, 30-50k, 50-80k, 80-120k, 120k+

### Data Sources
- **STATEC**: https://statistiques.public.lu — income, population, employment per commune
- **data.public.lu**: open data portal — commune boundaries, postal codes
- **ADEM** (employment agency): unemployment rates by canton
- **IGSS** (social security): cross-border worker statistics

---

## 9. Code Style Conventions

- **Notebook-friendly**: All files use `# %%` cell markers for Jupyter compatibility
- **No OOP**: Functions + execution calls, no classes
- **Independent cells**: Each cell can be run standalone after running the imports cell
- **Auto-detection**: Column names are auto-detected (flexible naming for client_id, churn column)
- **Encoding fallback**: CSV reading tries utf-8, then latin-1, then cp1252
- **sklearn only**: No XGBoost/LightGBM/TensorFlow dependencies

---

## 10. Key Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Upstream clients | Treated as retained | High-NBI VIP migrations would contaminate churn signal |
| Churn derivation | Stock Y vs Stock Y+1 comparison | No explicit churn column in source data |
| 3-month confirmation | Applied in SQL | Avoid flagging temporary absences as churn |
| Annual model | Quarterly features, annual target | Avoid data leakage from quarterly targets |
| Hazard assumption V1 | Constant (p^t) | Hazard ratio 0.809 is borderline; V2 needs Weibull |
| Hazard assumption V2 | Weibull S(t)=exp(-(t/lambda)^k) | For when k < 1 (decelerating hazard) |
| New client model | GBRegressor + GBClassifier | Consistent with established model, interpretable |
| PNB loss | Huber | Robust to NBI outliers |
| Product sub-models | Unified (not 4 separate) | Sample size too small for new clients |
| Geographic data | STATEC (Luxembourg) | Bank is in Luxembourg, not France |
| Transition | 5-month linear blend | Avoids CLV discontinuity at graduation |
| Salary domiciliation | Key Phase 2 signal | Strongest predictor of long-term value |

---

## 11. Model Hyperparameters Reference

### Established Model (v0)
```python
GradientBoostingClassifier(n_estimators=200, max_depth=4, lr=0.05, subsample=0.8, min_samples_leaf=20)
```

### New Acquisitions — Phase 1 / Proposition A
```python
# PNB
GradientBoostingRegressor(n_estimators=300, max_depth=4, lr=0.05, subsample=0.8, min_samples_leaf=20, loss='huber')
# Retention
GradientBoostingClassifier(n_estimators=200, max_depth=4, lr=0.05, subsample=0.8, min_samples_leaf=20)
```

### New Acquisitions — Phase 2
```python
# PNB
GradientBoostingRegressor(n_estimators=400, max_depth=5, lr=0.05, subsample=0.8, min_samples_leaf=15, loss='huber')
# Retention
GradientBoostingClassifier(n_estimators=300, max_depth=5, lr=0.05, subsample=0.8, min_samples_leaf=15)
```

---

## 12. Evaluation Metrics

### PNB Regression
- MAE (Mean Absolute Error) — primary, in EUR
- RMSE (Root Mean Squared Error)
- R2 (coefficient of determination)
- Predicted vs actual scatter plot

### Retention Classification
- AUC-ROC — primary (> 0.65 acceptable, > 0.70 good)
- Average Precision (AP)
- Brier Score (calibration quality)
- ROC curve, Precision-Recall curve, Calibration curve
- Classification report (precision, recall, F1)

### CLV Validation
- Predicted CLV distribution vs actual observed CLV for test cohort
- Mean predicted CLV within 10% of actual cohort average
- Retention model predicts higher churn for new clients than established model

---

## 13. File Dependencies

```
new_acq_data_preparation.py
    |-> new_acq_model_a.py  (Proposition A)
    |-> new_acq_phase1_model.py  (Proposition B Phase 1)
    |   |-> new_acq_phase2_model.py  (Phase 2, uses Phase 1 artifacts)
    |       |-> new_acq_transition.py  (blending logic)
    |-> new_acq_scoring.py  (unified, uses all models)

simplified/data_processing.py  (Stock loading, reused by data_preparation)
model/retention_model.py       (CLV formula, reused conceptually)
```
