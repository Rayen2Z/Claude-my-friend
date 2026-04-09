# =============================================================================
# PROPOSITION B — Phase 1: Declarative Model (Day 0)
# =============================================================================
#
# Phase 1 is identical to Proposition A in terms of model architecture.
# The difference is in the output format: it tags predictions as "phase1"
# with a low confidence flag, and provides a clean handoff interface
# to Phase 2 when early behavioral data becomes available.
#
# Prerequisite: run new_acq_data_preparation.py first to build df_training.
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    roc_auc_score, brier_score_loss, average_precision_score,
)
import warnings
warnings.filterwarnings("ignore")


# %% ---- CELL 2: Configuration ----

DISCOUNT_RATE = 0.05
RETENTION_ESTABLISHED = 0.95
GROWTH_FACTOR = 1.10

# Columns to exclude from features (same as Proposition A)
EXCLUDE_COLS = {
    "client_id", "acquisition_year", "acquisition_date",
    "churned_year1", "is_upstreamed", "pnb_annee1",
    "code_postal", "code_commune", "categorie_urbaine",
    "csp_category", "csp", "profession",
    "nationalite", "nationality",
    "situation_familiale", "family_situation",
    "canal", "channel",
    "genre", "gender",
    "tranche_revenu", "income_range",
    "pays_residence", "country_of_residence",
    "date_naissance", "date_of_birth",
}


# %% ---- CELL 3: Prepare features and targets ----

# df_training comes from new_acq_data_preparation.py
feature_cols = [
    col for col in df_training.columns
    if col not in EXCLUDE_COLS
    and df_training[col].dtype in [np.float64, np.int64, np.float32, np.int32]
]

X = df_training[feature_cols].copy().fillna(df_training[feature_cols].median())
y_pnb = df_training["pnb_annee1"].fillna(0)
y_churn = df_training["churned_year1"].fillna(0).astype(int)

# Temporal split
years = sorted(df_training["acquisition_year"].unique())
if len(years) >= 2:
    train_mask = df_training["acquisition_year"].isin(years[:-1])
    test_mask = df_training["acquisition_year"] == years[-1]
else:
    np.random.seed(42)
    train_mask = np.random.rand(len(df_training)) < 0.8
    test_mask = ~train_mask

X_train, X_test = X[train_mask], X[test_mask]
y_pnb_train, y_pnb_test = y_pnb[train_mask], y_pnb[test_mask]
y_churn_train, y_churn_test = y_churn[train_mask], y_churn[test_mask]

print(f"Phase 1 — Train: {len(X_train)} | Test: {len(X_test)}")
print(f"Features: {len(feature_cols)}")


# %% ---- CELL 4: Train Phase 1 models ----

# PNB regression
pnb_model_p1 = GradientBoostingRegressor(
    n_estimators=300, max_depth=4, learning_rate=0.05,
    subsample=0.8, min_samples_leaf=20, loss="huber", random_state=42,
)
pnb_model_p1.fit(X_train, y_pnb_train)

# Retention classification
retention_model_p1 = GradientBoostingClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    subsample=0.8, min_samples_leaf=20, random_state=42,
)
retention_model_p1.fit(X_train, y_churn_train)

print("Phase 1 models trained.")


# %% ---- CELL 5: Evaluate Phase 1 ----

pnb_pred = pnb_model_p1.predict(X_test)
churn_pred = retention_model_p1.predict_proba(X_test)[:, 1]

print("=" * 50)
print("PHASE 1 — EVALUATION (Test set)")
print("=" * 50)
print(f"\nPNB Regression:")
print(f"  MAE:  {mean_absolute_error(y_pnb_test, pnb_pred):,.0f} EUR")
print(f"  RMSE: {np.sqrt(mean_squared_error(y_pnb_test, pnb_pred)):,.0f} EUR")
print(f"  R2:   {r2_score(y_pnb_test, pnb_pred):.4f}")

print(f"\nRetention Classification:")
print(f"  AUC-ROC: {roc_auc_score(y_churn_test, churn_pred):.4f}")
print(f"  AP:      {average_precision_score(y_churn_test, churn_pred):.4f}")
print(f"  Brier:   {brier_score_loss(y_churn_test, churn_pred):.4f}")


# %% ---- CELL 6: Phase 1 scoring function ----

def score_phase1(df_clients, feature_cols_list, pnb_model, retention_model,
                 discount_rate=DISCOUNT_RATE, retention_established=RETENTION_ESTABLISHED,
                 growth_factor=GROWTH_FACTOR):
    """
    Score new clients using Phase 1 (declarative features only).
    Returns a DataFrame with CLV predictions and Phase 1 metadata.
    """
    X_score = df_clients[feature_cols_list].copy().fillna(
        df_clients[feature_cols_list].median()
    )

    pnb_y1 = pnb_model.predict(X_score)
    p_churn = retention_model.predict_proba(X_score)[:, 1]
    retention = 1 - p_churn

    pnb_y2 = pnb_y1 * growth_factor
    pnb_y3 = pnb_y2 * growth_factor

    s1 = retention
    s2 = s1 * retention_established
    s3 = s2 * retention_established

    d1 = 1 / (1 + discount_rate) ** 1
    d2 = 1 / (1 + discount_rate) ** 2
    d3 = 1 / (1 + discount_rate) ** 3

    result = pd.DataFrame({
        "client_id": df_clients["client_id"].values,
        "phase_modele": "phase1",
        "confiance": "faible",
        "pnb_pred_annee1": pnb_y1,
        "pnb_pred_annee2": pnb_y2,
        "pnb_pred_annee3": pnb_y3,
        "retention_score_new": retention,
        "survie_annee1": s1,
        "survie_annee2": s2,
        "survie_annee3": s3,
        "clv_composante_annee1": pnb_y1 * s1 * d1,
        "clv_composante_annee2": pnb_y2 * s2 * d2,
        "clv_composante_annee3": pnb_y3 * s3 * d3,
        "type_modele": "nouvelle_acq_phase1",
    })
    result["clv_total"] = (
        result["clv_composante_annee1"]
        + result["clv_composante_annee2"]
        + result["clv_composante_annee3"]
    )

    return result


# %% ---- CELL 7: Score and display ----

phase1_results = score_phase1(
    df_training, feature_cols, pnb_model_p1, retention_model_p1
)

print(f"\nPhase 1 scored {len(phase1_results)} clients")
print(f"Mean CLV:    {phase1_results['clv_total'].mean():,.0f} EUR")
print(f"Median CLV:  {phase1_results['clv_total'].median():,.0f} EUR")
print(f"Mean retention: {phase1_results['retention_score_new'].mean():.3f}")

print("\nSample output:")
print(phase1_results.head(5).to_string())


# %% ---- CELL 8: Export models and feature list for Phase 2 handoff ----

# These objects are used by Phase 2 and the transition module
phase1_artifacts = {
    "pnb_model": pnb_model_p1,
    "retention_model": retention_model_p1,
    "feature_cols": feature_cols,
    "results": phase1_results,
}

print("\nPhase 1 artifacts ready for handoff to Phase 2.")
print(f"  PNB model:       GBRegressor ({pnb_model_p1.n_estimators} trees)")
print(f"  Retention model: GBClassifier ({retention_model_p1.n_estimators} trees)")
print(f"  Feature count:   {len(feature_cols)}")
