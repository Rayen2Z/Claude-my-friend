# =============================================================================
# PROPOSITION A — Look-alike Cohort Model (Single-stage)
# =============================================================================
#
# Trains two sub-models on historical new-client cohorts:
#   1. GBRegressor  -> predict PNB (year 1)
#   2. GBClassifier -> predict retention (churn within year 1)
# Then computes 3-year CLV using new-client-specific survival curve.
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
    classification_report, roc_curve, precision_recall_curve,
)
from sklearn.calibration import calibration_curve
import warnings
warnings.filterwarnings("ignore")


# %% ---- CELL 2: Load training set ----

# df_training comes from new_acq_data_preparation.py
# If running standalone, uncomment:
# from new_acq_data_preparation import build_new_client_training_set
# df_training = build_new_client_training_set()

print(f"Training set: {len(df_training)} rows")
print(f"Cohorts: {sorted(df_training['acquisition_year'].unique())}")
print(f"Columns: {len(df_training.columns)}")


# %% ---- CELL 3: Select features and handle NaN ----

# Columns to exclude from features
EXCLUDE_COLS = {
    "client_id", "acquisition_year", "acquisition_date",
    "churned_year1", "is_upstreamed", "pnb_annee1",
    "code_postal", "code_commune", "categorie_urbaine",
    # Original categorical columns (already one-hot encoded)
    "csp_category", "csp", "profession",
    "nationalite", "nationality",
    "situation_familiale", "family_situation",
    "canal", "channel",
    "genre", "gender",
    "tranche_revenu", "income_range",
    "pays_residence", "country_of_residence",
    "date_naissance", "date_of_birth",
}

# Select numeric features only
feature_cols = [
    col for col in df_training.columns
    if col not in EXCLUDE_COLS
    and df_training[col].dtype in [np.float64, np.int64, np.float32, np.int32, "float64", "int64"]
]

print(f"\nSelected {len(feature_cols)} features:")
for col in sorted(feature_cols):
    print(f"  {col}")

# Prepare feature matrix
X = df_training[feature_cols].copy()
X = X.fillna(X.median())  # fill missing with median (robust to outliers)

# Targets
y_pnb = df_training["pnb_annee1"].fillna(0)
y_churn = df_training["churned_year1"].fillna(0).astype(int)

print(f"\nFeature matrix: {X.shape}")
print(f"PNB target: mean={y_pnb.mean():,.0f}, median={y_pnb.median():,.0f}")
print(f"Churn target: rate={y_churn.mean():.2%}")


# %% ---- CELL 4: Temporal train/test split ----

years = sorted(df_training["acquisition_year"].unique())

if len(years) >= 2:
    train_years = years[:-1]
    test_year = years[-1]
    print(f"Train cohorts: {train_years}")
    print(f"Test cohort:   {test_year}")

    train_mask = df_training["acquisition_year"].isin(train_years)
    test_mask = df_training["acquisition_year"] == test_year
else:
    # Fallback: random 80/20 split
    print("Only one cohort available. Using random 80/20 split.")
    np.random.seed(42)
    train_mask = np.random.rand(len(df_training)) < 0.8
    test_mask = ~train_mask

X_train, X_test = X[train_mask], X[test_mask]
y_pnb_train, y_pnb_test = y_pnb[train_mask], y_pnb[test_mask]
y_churn_train, y_churn_test = y_churn[train_mask], y_churn[test_mask]

print(f"\nTrain: {len(X_train)} | Test: {len(X_test)}")
print(f"Train churn rate: {y_churn_train.mean():.2%} | Test: {y_churn_test.mean():.2%}")
print(f"Train PNB mean: {y_pnb_train.mean():,.0f} | Test: {y_pnb_test.mean():,.0f}")


# %% ---- CELL 5: Train PNB regression model ----

pnb_model = GradientBoostingRegressor(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    min_samples_leaf=20,
    loss="huber",
    random_state=42,
)

print("Training PNB regression model...")
pnb_model.fit(X_train, y_pnb_train)
print("Done.")

pnb_pred_train = pnb_model.predict(X_train)
pnb_pred_test = pnb_model.predict(X_test)


# %% ---- CELL 6: Evaluate PNB model ----

print("=" * 50)
print("PNB REGRESSION — EVALUATION")
print("=" * 50)

for label, y_true, y_pred in [("Train", y_pnb_train, pnb_pred_train),
                               ("Test", y_pnb_test, pnb_pred_test)]:
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    print(f"\n{label}:")
    print(f"  MAE:  {mae:,.0f} EUR")
    print(f"  RMSE: {rmse:,.0f} EUR")
    print(f"  R2:   {r2:.4f}")
    print(f"  Mean actual: {y_true.mean():,.0f} | Mean predicted: {y_pred.mean():,.0f}")

# Predicted vs actual scatter
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

for ax, label, y_true, y_pred in [(axes[0], "Train", y_pnb_train, pnb_pred_train),
                                    (axes[1], "Test", y_pnb_test, pnb_pred_test)]:
    ax.scatter(y_true, y_pred, alpha=0.3, s=10)
    lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    ax.plot(lims, lims, "--", color="red", alpha=0.7)
    ax.set_xlabel("PNB reel (EUR)")
    ax.set_ylabel("PNB predit (EUR)")
    ax.set_title(f"PNB: Predit vs Reel ({label})")
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.show()


# %% ---- CELL 7: Train retention model ----

retention_model = GradientBoostingClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    min_samples_leaf=20,
    random_state=42,
)

print("Training retention (churn) classification model...")
retention_model.fit(X_train, y_churn_train)
print("Done.")

churn_prob_train = retention_model.predict_proba(X_train)[:, 1]
churn_prob_test = retention_model.predict_proba(X_test)[:, 1]

retention_train = 1 - churn_prob_train
retention_test = 1 - churn_prob_test


# %% ---- CELL 8: Evaluate retention model ----

print("=" * 50)
print("RETENTION MODEL — EVALUATION")
print("=" * 50)

for label, y_true, p_churn in [("Train", y_churn_train, churn_prob_train),
                                 ("Test", y_churn_test, churn_prob_test)]:
    auc = roc_auc_score(y_true, p_churn)
    ap = average_precision_score(y_true, p_churn)
    brier = brier_score_loss(y_true, p_churn)
    print(f"\n{label}:")
    print(f"  AUC-ROC:          {auc:.4f}")
    print(f"  Average Precision: {ap:.4f}")
    print(f"  Brier Score:      {brier:.4f}")

# ROC + PR + Calibration curves
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# ROC
fpr, tpr, _ = roc_curve(y_churn_test, churn_prob_test)
axes[0].plot(fpr, tpr, lw=2, label=f"AUC = {roc_auc_score(y_churn_test, churn_prob_test):.3f}")
axes[0].plot([0, 1], [0, 1], "--", color="gray")
axes[0].set_xlabel("Taux de faux positifs")
axes[0].set_ylabel("Taux de vrais positifs")
axes[0].set_title("Courbe ROC (Test)")
axes[0].legend()
axes[0].grid(alpha=0.3)

# Precision-Recall
prec, rec, _ = precision_recall_curve(y_churn_test, churn_prob_test)
axes[1].plot(rec, prec, lw=2, label=f"AP = {average_precision_score(y_churn_test, churn_prob_test):.3f}")
axes[1].set_xlabel("Rappel")
axes[1].set_ylabel("Precision")
axes[1].set_title("Courbe Precision-Rappel (Test)")
axes[1].legend()
axes[1].grid(alpha=0.3)

# Calibration
fraction_pos, mean_predicted = calibration_curve(y_churn_test, churn_prob_test, n_bins=10)
axes[2].plot(mean_predicted, fraction_pos, "o-", lw=2)
axes[2].plot([0, 1], [0, 1], "--", color="gray")
axes[2].set_xlabel("Probabilite predite")
axes[2].set_ylabel("Frequence observee")
axes[2].set_title("Courbe de Calibration (Test)")
axes[2].grid(alpha=0.3)

plt.tight_layout()
plt.show()

print(f"\nClassification Report (Test, seuil=0.5):")
print(classification_report(y_churn_test, (churn_prob_test >= 0.5).astype(int),
                            target_names=["Reste", "Depart"]))


# %% ---- CELL 9: Feature importance ----

fig, axes = plt.subplots(1, 2, figsize=(16, 8))

for ax, model, title in [(axes[0], pnb_model, "PNB (Regression)"),
                           (axes[1], retention_model, "Retention (Classification)")]:
    importance = pd.Series(model.feature_importances_, index=feature_cols)
    top_15 = importance.nlargest(15)
    top_15.sort_values().plot(kind="barh", ax=ax)
    ax.set_title(f"Top 15 Features — {title}")
    ax.set_xlabel("Importance")
    ax.grid(axis="x", alpha=0.3)

plt.tight_layout()
plt.show()


# %% ---- CELL 10: Compute CLV with new-client survival curve ----

DISCOUNT_RATE = 0.05
RETENTION_ESTABLISHED = 0.95  # annual retention for established clients (post year 1)

# Growth factor: how new client PNB evolves from year 1 to year 2+
# Estimated from cohort data. Default = 1.1 (10% growth as relationship deepens)
GROWTH_FACTOR = 1.10


def compute_new_client_clv(pnb_year1, retention_score_new, discount_rate=DISCOUNT_RATE,
                            retention_established=RETENTION_ESTABLISHED,
                            growth_factor=GROWTH_FACTOR):
    """
    Compute 3-year CLV for new clients.

    Survival curve:
      S(1) = retention_score_new (predicted by model)
      S(2) = S(1) * retention_established
      S(3) = S(2) * retention_established

    PNB projection:
      PNB(1) = pnb_year1 (predicted)
      PNB(2) = PNB(1) * growth_factor
      PNB(3) = PNB(2) * growth_factor
    """
    pnb_y1 = pnb_year1
    pnb_y2 = pnb_y1 * growth_factor
    pnb_y3 = pnb_y2 * growth_factor

    s1 = retention_score_new
    s2 = s1 * retention_established
    s3 = s2 * retention_established

    d1 = 1 / (1 + discount_rate) ** 1
    d2 = 1 / (1 + discount_rate) ** 2
    d3 = 1 / (1 + discount_rate) ** 3

    clv_y1 = pnb_y1 * s1 * d1
    clv_y2 = pnb_y2 * s2 * d2
    clv_y3 = pnb_y3 * s3 * d3

    clv_total = clv_y1 + clv_y2 + clv_y3

    return {
        "pnb_pred_annee1": pnb_y1,
        "pnb_pred_annee2": pnb_y2,
        "pnb_pred_annee3": pnb_y3,
        "retention_score_new": retention_score_new,
        "survie_annee1": s1,
        "survie_annee2": s2,
        "survie_annee3": s3,
        "clv_composante_annee1": clv_y1,
        "clv_composante_annee2": clv_y2,
        "clv_composante_annee3": clv_y3,
        "clv_total": clv_total,
    }


# %% ---- CELL 11: Score all new clients ----

print("Scoring all new clients...")

pnb_all = pnb_model.predict(X)
churn_all = retention_model.predict_proba(X)[:, 1]
retention_all = 1 - churn_all

# Compute CLV for each client
clv_results = []
for i in range(len(X)):
    result = compute_new_client_clv(pnb_all[i], retention_all[i])
    clv_results.append(result)

clv_df = pd.DataFrame(clv_results)
clv_df["client_id"] = df_training["client_id"].values
clv_df["acquisition_year"] = df_training["acquisition_year"].values
clv_df["type_modele"] = "nouvelle_acquisition_v1"

# Reorder columns
col_order = [
    "client_id", "acquisition_year", "type_modele",
    "pnb_pred_annee1", "pnb_pred_annee2", "pnb_pred_annee3",
    "retention_score_new", "survie_annee1", "survie_annee2", "survie_annee3",
    "clv_composante_annee1", "clv_composante_annee2", "clv_composante_annee3",
    "clv_total",
]
clv_df = clv_df[col_order]

print(f"\nScored {len(clv_df)} clients")
print(clv_df.head(10).to_string())


# %% ---- CELL 12: Summary statistics and distribution ----

print("=" * 50)
print("CLV SUMMARY — PROPOSITION A")
print("=" * 50)

for year in sorted(clv_df["acquisition_year"].unique()):
    yr = clv_df[clv_df["acquisition_year"] == year]
    print(f"\n--- Cohort {year} ({len(yr)} clients) ---")
    print(f"  PNB Year 1:    mean={yr['pnb_pred_annee1'].mean():>10,.0f} EUR  |  median={yr['pnb_pred_annee1'].median():>10,.0f} EUR")
    print(f"  Retention:     mean={yr['retention_score_new'].mean():>10.3f}     |  median={yr['retention_score_new'].median():>10.3f}")
    print(f"  CLV 3yr:       mean={yr['clv_total'].mean():>10,.0f} EUR  |  median={yr['clv_total'].median():>10,.0f} EUR")
    print(f"  CLV total:     {yr['clv_total'].sum():>15,.0f} EUR")

# Distribution plots
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

axes[0].hist(clv_df["pnb_pred_annee1"], bins=50, edgecolor="white", alpha=0.8)
axes[0].set_xlabel("PNB predit annee 1 (EUR)")
axes[0].set_ylabel("Nombre de clients")
axes[0].set_title("Distribution du PNB predit")
axes[0].grid(alpha=0.3)

axes[1].hist(clv_df["retention_score_new"], bins=50, edgecolor="white", alpha=0.8, color="green")
axes[1].set_xlabel("Score de retention")
axes[1].set_ylabel("Nombre de clients")
axes[1].set_title("Distribution du score de retention")
axes[1].grid(alpha=0.3)

axes[2].hist(clv_df["clv_total"], bins=50, edgecolor="white", alpha=0.8, color="orange")
axes[2].set_xlabel("CLV 3 ans (EUR)")
axes[2].set_ylabel("Nombre de clients")
axes[2].set_title("Distribution de la CLV")
axes[2].grid(alpha=0.3)

plt.tight_layout()
plt.show()
