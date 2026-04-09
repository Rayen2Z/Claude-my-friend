# =============================================================================
# PROPOSITION B — Phase 2: Early Behavioral Model (Month 3-6)
# =============================================================================
#
# Phase 2 adds early behavioral features (first 3-6 months of transactions)
# to the declarative features from Phase 1. The combined feature set
# produces significantly more accurate PNB and retention predictions.
#
# Key signal: salary domiciliation (domiciliation du salaire) — if the
# client routes their salary through the bank in the first 3 months,
# this is the single strongest predictor of long-term value.
#
# Prerequisites:
#   - new_acq_data_preparation.py (df_training)
#   - new_acq_phase1_model.py (phase1_artifacts for comparison)
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    roc_auc_score, brier_score_loss, average_precision_score,
    classification_report, roc_curve,
)
from sklearn.calibration import calibration_curve
import warnings
warnings.filterwarnings("ignore")


# %% ---- CELL 2: Configuration ----

DISCOUNT_RATE = 0.05
RETENTION_ESTABLISHED = 0.95
GROWTH_FACTOR = 1.10

# Phase 1 exclusion columns + behavioral columns that are targets, not features
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
    # Phase 2 targets (not features)
    "pnb_restant",
}


# %% ---- CELL 3: Add early behavioral features ----

def add_behavioral_features(df):
    """
    Add Phase 2 behavioral features from the client's first 3 months.

    Expected columns in the source data (from transactional enrichment):
      - pnb_m1, pnb_m2, pnb_m3 (monthly PNB)
      - n_txn_m1_m3 (transaction count, first 3 months)
      - jours_avant_premiere_txn (days to first transaction)
      - a_domiciliation_salaire (binary: salary routed)
      - montant_salaire_estime (estimated monthly salary)
      - n_paiements_cb (card payment count)
      - carte_activee (binary: card used)
      - epargne_alimentee (binary: savings funded)
      - n_produits_mois3 (product count at month 3)
      - a_prelevement (binary: direct debit set up)
      - connexions_digitales_m1 (app/web logins month 1)
      - pct_usage_digital (% digital interactions)
      - contact_conseiller (binary: met advisor)

    If columns are missing, they are filled with NaN (graceful degradation).
    """
    df = df.copy()

    # --- PNB first quarter ---
    pnb_monthly = ["pnb_m1", "pnb_m2", "pnb_m3"]
    available_months = [c for c in pnb_monthly if c in df.columns]
    if available_months:
        for c in available_months:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        df["pnb_premier_trimestre"] = df[available_months].sum(axis=1)
        df["log_pnb_premier_trimestre"] = np.log1p(df["pnb_premier_trimestre"].clip(lower=0))
        if "pnb_m1" in df.columns and "pnb_m3" in df.columns:
            df["taux_montee_pnb"] = np.where(
                df["pnb_m1"] > 0,
                df["pnb_m3"] / df["pnb_m1"],
                np.where(df["pnb_m3"] > 0, 2.0, 0.0)  # m3 > 0 but m1 = 0 -> strong ramp
            )
    else:
        df["pnb_premier_trimestre"] = np.nan
        df["log_pnb_premier_trimestre"] = np.nan
        df["taux_montee_pnb"] = np.nan

    # --- Transaction signals ---
    if "n_txn_m1_m3" in df.columns:
        df["n_txn_m1_m3"] = pd.to_numeric(df["n_txn_m1_m3"], errors="coerce").fillna(0)
        df["frequence_txn"] = df["n_txn_m1_m3"] / 90  # per day over 3 months
    else:
        df["n_txn_m1_m3"] = np.nan
        df["frequence_txn"] = np.nan

    if "jours_avant_premiere_txn" in df.columns:
        df["jours_avant_premiere_txn"] = pd.to_numeric(
            df["jours_avant_premiere_txn"], errors="coerce"
        )
        df["vitesse_activation"] = 1 / (df["jours_avant_premiere_txn"].clip(lower=0) + 1)
    else:
        df["jours_avant_premiere_txn"] = np.nan
        df["vitesse_activation"] = np.nan

    # --- Salary domiciliation (key signal) ---
    if "a_domiciliation_salaire" in df.columns:
        df["a_domiciliation_salaire"] = df["a_domiciliation_salaire"].fillna(0).astype(int)
    else:
        df["a_domiciliation_salaire"] = np.nan

    if "montant_salaire_estime" in df.columns:
        df["montant_salaire_estime"] = pd.to_numeric(
            df["montant_salaire_estime"], errors="coerce"
        ).fillna(0)
    else:
        df["montant_salaire_estime"] = np.nan

    # --- Card and product activation ---
    for col in ["carte_activee", "epargne_alimentee", "a_prelevement", "contact_conseiller"]:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)
        else:
            df[col] = np.nan

    if "n_produits_mois3" in df.columns:
        df["n_produits_mois3"] = pd.to_numeric(df["n_produits_mois3"], errors="coerce")
        if "n_produits_onboarding" in df.columns:
            df["produits_ajoutes"] = df["n_produits_mois3"] - df["n_produits_onboarding"]
            df["taux_activation_produits"] = np.where(
                df["n_produits_onboarding"] > 0,
                df["n_produits_mois3"] / df["n_produits_onboarding"],
                1.0
            )
    else:
        df["n_produits_mois3"] = np.nan
        df["produits_ajoutes"] = np.nan
        df["taux_activation_produits"] = np.nan

    # --- Digital engagement ---
    if "connexions_digitales_m1" in df.columns:
        df["connexions_digitales_m1"] = pd.to_numeric(
            df["connexions_digitales_m1"], errors="coerce"
        ).fillna(0)
    else:
        df["connexions_digitales_m1"] = np.nan

    if "pct_usage_digital" in df.columns:
        df["pct_usage_digital"] = pd.to_numeric(
            df["pct_usage_digital"], errors="coerce"
        ).fillna(0)
    else:
        df["pct_usage_digital"] = np.nan

    if "n_paiements_cb" in df.columns:
        df["n_paiements_cb"] = pd.to_numeric(df["n_paiements_cb"], errors="coerce").fillna(0)
    else:
        df["n_paiements_cb"] = np.nan

    # --- Phase 2 interaction features ---
    if "a_domiciliation_salaire" in df.columns and "income_midpoint" in df.columns:
        df["salaire_x_revenu_declare"] = np.where(
            df["income_midpoint"] > 0,
            df["montant_salaire_estime"] / df["income_midpoint"],
            0
        )

    if "connexions_digitales_m1" in df.columns and "n_txn_m1_m3" in df.columns:
        df["digital_x_transactions"] = df["connexions_digitales_m1"] * df["n_txn_m1_m3"]

    # --- PNB remaining target (for regression) ---
    if "pnb_annee1" in df.columns and "pnb_premier_trimestre" in df.columns:
        df["pnb_restant"] = df["pnb_annee1"] - df["pnb_premier_trimestre"].fillna(0)

    return df


# %% ---- CELL 4: Build Phase 2 training set ----

# Add behavioral features to the training data
# In production, these come from transactional data at the 3-month mark.
# For training, we reconstruct them from historical data.

df_phase2 = add_behavioral_features(df_training.copy())

# Select all numeric features (Phase 1 + Phase 2 behavioral)
feature_cols_p2 = [
    col for col in df_phase2.columns
    if col not in EXCLUDE_COLS
    and df_phase2[col].dtype in [np.float64, np.int64, np.float32, np.int32]
]

print(f"Phase 2 features: {len(feature_cols_p2)} (vs Phase 1: ~{len(feature_cols_p2) - 15})")
print("\nNew behavioral features:")
behavioral_specific = [c for c in feature_cols_p2 if c not in getattr(
    globals().get('phase1_artifacts', {}), 'get', lambda x, y: y)('feature_cols', [])]
for col in sorted(feature_cols_p2):
    if any(kw in col for kw in ["pnb_premier", "txn", "salaire", "carte", "epargne",
                                  "prelevement", "connexion", "digital_x", "produits_ajoutes",
                                  "taux_montee", "taux_activation", "vitesse", "frequence",
                                  "contact", "pct_usage", "paiements_cb", "log_pnb_premier",
                                  "n_produits_mois3", "jours_avant"]):
        print(f"  [NEW] {col}")


# %% ---- CELL 5: Prepare and split ----

X_p2 = df_phase2[feature_cols_p2].copy().fillna(df_phase2[feature_cols_p2].median())

# Target: remaining PNB (after first quarter) if available, else full year PNB
if "pnb_restant" in df_phase2.columns and df_phase2["pnb_restant"].notna().any():
    y_pnb_p2 = df_phase2["pnb_restant"].fillna(0)
    pnb_target_name = "pnb_restant (9 remaining months)"
else:
    y_pnb_p2 = df_phase2["pnb_annee1"].fillna(0)
    pnb_target_name = "pnb_annee1 (full year)"

y_churn_p2 = df_phase2["churned_year1"].fillna(0).astype(int)

# Same temporal split
years = sorted(df_phase2["acquisition_year"].unique())
if len(years) >= 2:
    train_mask = df_phase2["acquisition_year"].isin(years[:-1])
    test_mask = df_phase2["acquisition_year"] == years[-1]
else:
    np.random.seed(42)
    train_mask = np.random.rand(len(df_phase2)) < 0.8
    test_mask = ~train_mask

X_train_p2, X_test_p2 = X_p2[train_mask], X_p2[test_mask]
y_pnb_train_p2, y_pnb_test_p2 = y_pnb_p2[train_mask], y_pnb_p2[test_mask]
y_churn_train_p2, y_churn_test_p2 = y_churn_p2[train_mask], y_churn_p2[test_mask]

print(f"Phase 2 — Train: {len(X_train_p2)} | Test: {len(X_test_p2)}")
print(f"PNB target: {pnb_target_name}")


# %% ---- CELL 6: Train Phase 2 PNB model ----

pnb_model_p2 = GradientBoostingRegressor(
    n_estimators=400,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    min_samples_leaf=15,
    loss="huber",
    random_state=42,
)

print("Training Phase 2 PNB model (deeper, more trees)...")
pnb_model_p2.fit(X_train_p2, y_pnb_train_p2)
print("Done.")


# %% ---- CELL 7: Train Phase 2 retention model ----

retention_model_p2 = GradientBoostingClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    min_samples_leaf=15,
    random_state=42,
)

print("Training Phase 2 retention model...")
retention_model_p2.fit(X_train_p2, y_churn_train_p2)
print("Done.")


# %% ---- CELL 8: Evaluate Phase 2 and compare with Phase 1 ----

pnb_pred_p2 = pnb_model_p2.predict(X_test_p2)
churn_pred_p2 = retention_model_p2.predict_proba(X_test_p2)[:, 1]

print("=" * 60)
print("PHASE 2 vs PHASE 1 — COMPARISON")
print("=" * 60)

# Phase 2 metrics
mae_p2 = mean_absolute_error(y_pnb_test_p2, pnb_pred_p2)
rmse_p2 = np.sqrt(mean_squared_error(y_pnb_test_p2, pnb_pred_p2))
r2_p2 = r2_score(y_pnb_test_p2, pnb_pred_p2)
auc_p2 = roc_auc_score(y_churn_test_p2, churn_pred_p2)
brier_p2 = brier_score_loss(y_churn_test_p2, churn_pred_p2)

print(f"\nPhase 2 PNB Regression:")
print(f"  MAE:  {mae_p2:,.0f} EUR")
print(f"  RMSE: {rmse_p2:,.0f} EUR")
print(f"  R2:   {r2_p2:.4f}")

print(f"\nPhase 2 Retention:")
print(f"  AUC-ROC: {auc_p2:.4f}")
print(f"  Brier:   {brier_p2:.4f}")

# Compare with Phase 1 if available
try:
    phase1_pnb_pred = phase1_artifacts["pnb_model"].predict(X_test_p2[phase1_artifacts["feature_cols"]])
    phase1_churn_pred = phase1_artifacts["retention_model"].predict_proba(X_test_p2[phase1_artifacts["feature_cols"]])[:, 1]

    mae_p1 = mean_absolute_error(y_pnb_test_p2, phase1_pnb_pred)
    auc_p1 = roc_auc_score(y_churn_test_p2, phase1_churn_pred)

    print(f"\n--- Improvement Phase 2 vs Phase 1 ---")
    print(f"  PNB MAE:  {mae_p1:,.0f} -> {mae_p2:,.0f} ({(mae_p2-mae_p1)/mae_p1*100:+.1f}%)")
    print(f"  AUC-ROC:  {auc_p1:.4f} -> {auc_p2:.4f} ({(auc_p2-auc_p1)/auc_p1*100:+.1f}%)")
except Exception:
    print("\n  (Phase 1 artifacts not available for comparison)")


# %% ---- CELL 9: Feature importance (highlight behavioral) ----

fig, axes = plt.subplots(1, 2, figsize=(18, 10))

for ax, model, title in [(axes[0], pnb_model_p2, "PNB Phase 2"),
                           (axes[1], retention_model_p2, "Retention Phase 2")]:
    importance = pd.Series(model.feature_importances_, index=feature_cols_p2)
    top_20 = importance.nlargest(20)

    # Color behavioral features differently
    behavioral_keywords = ["pnb_premier", "txn", "salaire", "carte", "epargne",
                           "prelevement", "connexion", "digital_x", "produits_ajoutes",
                           "taux_montee", "taux_activation", "vitesse", "frequence",
                           "contact", "pct_usage", "paiements_cb", "jours_avant"]
    colors = ["#e74c3c" if any(kw in feat for kw in behavioral_keywords) else "#3498db"
              for feat in top_20.index]

    top_20.sort_values().plot(kind="barh", ax=ax, color=colors[::-1])
    ax.set_title(f"Top 20 Features — {title}")
    ax.set_xlabel("Importance")
    ax.grid(axis="x", alpha=0.3)

# Legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor="#e74c3c", label="Behavioral (Phase 2)"),
    Patch(facecolor="#3498db", label="Declarative (Phase 1)"),
]
axes[0].legend(handles=legend_elements, loc="lower right")
axes[1].legend(handles=legend_elements, loc="lower right")

plt.tight_layout()
plt.show()


# %% ---- CELL 10: Early churn risk flagging ----

retention_score_p2 = 1 - churn_pred_p2

# Flag high-risk clients (retention < 0.5)
high_risk_mask = retention_score_p2 < 0.5
n_high_risk = high_risk_mask.sum()
pct_high_risk = high_risk_mask.mean() * 100

print("=" * 50)
print("EARLY CHURN RISK — PHASE 2 ALERTS")
print("=" * 50)
print(f"\nClients at high churn risk (retention < 0.5): {n_high_risk} ({pct_high_risk:.1f}%)")

if n_high_risk > 0:
    # Analyze what makes them high risk
    test_df = X_test_p2.copy()
    test_df["retention_score_p2"] = retention_score_p2
    test_df["high_risk"] = high_risk_mask

    print("\n--- High-risk vs Low-risk profile ---")
    for col in ["a_domiciliation_salaire", "carte_activee", "n_txn_m1_m3",
                "pnb_premier_trimestre", "connexions_digitales_m1"]:
        if col in test_df.columns and test_df[col].notna().any():
            hr = test_df[test_df["high_risk"]][col].mean()
            lr = test_df[~test_df["high_risk"]][col].mean()
            print(f"  {col}: high_risk={hr:.2f} | low_risk={lr:.2f}")


# %% ---- CELL 11: Phase 2 scoring function ----

def score_phase2(df_clients, feature_cols_list, pnb_model, retention_model,
                 discount_rate=DISCOUNT_RATE, retention_established=RETENTION_ESTABLISHED,
                 growth_factor=GROWTH_FACTOR):
    """
    Score clients at Month 3 using Phase 2 (declarative + behavioral).
    Returns DataFrame with CLV predictions and Phase 2 metadata.
    """
    df_enriched = add_behavioral_features(df_clients.copy())

    available_features = [c for c in feature_cols_list if c in df_enriched.columns]
    X_score = df_enriched[available_features].copy().fillna(
        df_enriched[available_features].median()
    )

    pnb_remaining = pnb_model.predict(X_score)
    p_churn = retention_model.predict_proba(X_score)[:, 1]
    retention = 1 - p_churn

    # If we predicted remaining PNB, add back the observed first quarter
    if "pnb_premier_trimestre" in df_enriched.columns:
        pnb_y1 = df_enriched["pnb_premier_trimestre"].fillna(0).values + pnb_remaining
    else:
        pnb_y1 = pnb_remaining

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
        "phase_modele": "phase2",
        "confiance": "moyenne",
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
        "a_domiciliation_salaire": df_enriched.get("a_domiciliation_salaire", np.nan).values
            if "a_domiciliation_salaire" in df_enriched.columns else np.nan,
        "risque_depart_precoce": (retention < 0.5),
        "type_modele": "nouvelle_acq_phase2",
    })
    result["clv_total"] = (
        result["clv_composante_annee1"]
        + result["clv_composante_annee2"]
        + result["clv_composante_annee3"]
    )

    return result


# %% ---- CELL 12: Score and display Phase 2 results ----

phase2_results = score_phase2(
    df_phase2, feature_cols_p2, pnb_model_p2, retention_model_p2
)

print(f"\nPhase 2 scored {len(phase2_results)} clients")
print(f"Mean CLV:       {phase2_results['clv_total'].mean():,.0f} EUR")
print(f"Median CLV:     {phase2_results['clv_total'].median():,.0f} EUR")
print(f"Mean retention: {phase2_results['retention_score_new'].mean():.3f}")
print(f"High risk:      {phase2_results['risque_depart_precoce'].sum()} clients")

# Export artifacts for transition module
phase2_artifacts = {
    "pnb_model": pnb_model_p2,
    "retention_model": retention_model_p2,
    "feature_cols": feature_cols_p2,
    "results": phase2_results,
}
