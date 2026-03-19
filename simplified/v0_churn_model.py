# =============================================================================
# V0 CHURN MODEL — Baseline retention scorer
# =============================================================================
#
# Binary classifier: P(churn) using gradient boosting.
# Output: retention_score = 1 - P(churn) per client.
#
# Works with whatever columns are in the dataset:
#   - client_id only  → tells you what columns to add
#   - With NBI        → trains on NBI features
#   - With full data  → trains on all available numeric columns
#
# Prerequisite: run data_processing.py first to get `df`.
# Or load from CSV:  df = pd.read_csv("churn_dataset.csv")
#
# Requires: pip install scikit-learn
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
    classification_report, roc_curve, precision_recall_curve,
)
from sklearn.calibration import calibration_curve


# %% ---- CELL 2: Setup — detect columns, exclude upstreamed ----

CHURN_COL = "churned" if "churned" in df.columns else "churned_next_year"
print(f"Target column: '{CHURN_COL}'")

work = df.copy()

# Exclude upstreamed clients from training
if "is_upstreamed" in work.columns:
    n_up = (work["is_upstreamed"] == 1).sum()
    work = work[work["is_upstreamed"] == 0].copy()
    print(f"Excluded {n_up} upstreamed clients")

print(f"Training data: {len(work)} rows, churn rate = {work[CHURN_COL].mean():.2%}")


# %% ---- CELL 3: Feature engineering ----
# Creates derived features from whatever columns are available.
# Each block is independent — it checks if the source columns exist first.

work = work.copy()

# NBI features
nbi_q = [f"nbi_q{q}" for q in range(1, 5) if f"nbi_q{q}" in work.columns]
if len(nbi_q) == 4:
    work["nbi_momentum"]   = work["nbi_q4"] - work["nbi_q1"]
    work["nbi_volatility"] = work[nbi_q].std(axis=1)
    print(f"  Added: nbi_momentum, nbi_volatility")

if "nbi_annual" in work.columns:
    work["log_nbi"] = np.log1p(work["nbi_annual"].clip(lower=0))
    print(f"  Added: log_nbi")

# Transaction features
txn_q = [f"n_transactions_q{q}" for q in range(1, 5) if f"n_transactions_q{q}" in work.columns]
if txn_q:
    work["total_txn"] = work[txn_q].sum(axis=1)
    if "quarters_active" in work.columns:
        work["txn_per_quarter"] = np.where(
            work["quarters_active"] > 0,
            work["total_txn"] / work["quarters_active"],
            0,
        )
    if len(txn_q) >= 2:
        work["txn_trend"] = work[txn_q[-1]] - work[txn_q[0]]
    print(f"  Added: total_txn, txn_trend")

# Product features
prod_q = [f"n_products_q{q}" for q in range(1, 5) if f"n_products_q{q}" in work.columns]
if prod_q:
    work["max_products"] = work[prod_q].max(axis=1)
    print(f"  Added: max_products")

# Engagement score
components = []
if "quarters_active" in work.columns:
    components.append(work["quarters_active"] / 4)
if "max_products" in work.columns and work["max_products"].max() > 0:
    components.append(work["max_products"] / work["max_products"].max())
if components:
    work["engagement"] = np.mean(components, axis=0)
    print(f"  Added: engagement")


# %% ---- CELL 4: Select features ----

exclude = {
    CHURN_COL, "churned", "churned_next_year", "is_upstreamed",
    "client_id", "year", "activity_pattern", "segment", "region",
    "date_of_birth", "account_opening_date",
}
features = [c for c in work.select_dtypes(include="number").columns if c not in exclude]

print(f"\nFeatures ({len(features)}): {features}")

if len(features) < 1:
    print("\nNo trainable features! Add columns to your Stock CSVs:")
    print("  nbi_annual, nbi_q1..q4, n_transactions_q1..q4,")
    print("  n_products_q1..q4, age, tenure_months")
    raise SystemExit("Cannot train without features.")


# %% ---- CELL 5: Train/test split ----

X = work[features].fillna(0)
y = work[CHURN_COL]

# Temporal split: most recent year = test, older years = train
if "year" in work.columns and work["year"].nunique() > 1:
    max_year = work["year"].max()
    train_mask = work["year"] < max_year
    test_mask  = work["year"] == max_year

    if test_mask.sum() > 10 and train_mask.sum() > 10:
        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]
        print(f"Temporal split: train < {max_year}, test = {max_year}")
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=42
        )
        print("Stratified random split (not enough data for temporal)")
else:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print("Stratified random split")

print(f"Train: {len(X_train)} (churn = {y_train.mean():.2%})")
print(f"Test : {len(X_test)} (churn = {y_test.mean():.2%})")


# %% ---- CELL 6: Train the model ----

model = GradientBoostingClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    min_samples_leaf=20,
    random_state=42,
)
model.fit(X_train, y_train)
print("Model trained.")


# %% ---- CELL 7: Evaluate ----

p_churn = model.predict_proba(X_test)[:, 1]
retention_scores = 1 - p_churn

auc   = roc_auc_score(y_test, p_churn)
ap    = average_precision_score(y_test, p_churn)
brier = brier_score_loss(y_test, p_churn)

print(f"AUC-ROC          : {auc:.4f}")
print(f"Average Precision: {ap:.4f}")
print(f"Brier Score      : {brier:.4f}")
print()
print(classification_report(y_test, (p_churn > 0.5).astype(int),
                            target_names=["Retained", "Churned"]))


# %% ---- CELL 8: Feature importance ----

importance = pd.DataFrame({
    "feature": features,
    "importance": model.feature_importances_,
}).sort_values("importance", ascending=False)

print("Top features:")
for _, r in importance.head(10).iterrows():
    bar = "#" * int(r["importance"] * 80)
    print(f"  {r['feature']:28s} {r['importance']:.4f}  {bar}")

importance


# %% ---- CELL 9: Plot — ROC, PR, Calibration, Retention distribution ----

fig, axes = plt.subplots(2, 2, figsize=(13, 11))

# ROC curve
fpr, tpr, _ = roc_curve(y_test, p_churn)
axes[0, 0].plot(fpr, tpr, lw=2, label=f"AUC = {auc:.3f}")
axes[0, 0].plot([0, 1], [0, 1], "--", color="gray")
axes[0, 0].set(xlabel="FPR", ylabel="TPR", title="ROC Curve")
axes[0, 0].legend()

# Precision-Recall
prec, rec, _ = precision_recall_curve(y_test, p_churn)
axes[0, 1].plot(rec, prec, lw=2, color="green", label=f"AP = {ap:.3f}")
axes[0, 1].set(xlabel="Recall", ylabel="Precision", title="Precision-Recall")
axes[0, 1].legend()

# Calibration
prob_true, prob_pred = calibration_curve(y_test, p_churn, n_bins=10)
axes[1, 0].plot(prob_pred, prob_true, "o-", color="purple", label="Model")
axes[1, 0].plot([0, 1], [0, 1], "--", color="gray", label="Perfect")
axes[1, 0].set(xlabel="Predicted P(churn)", ylabel="Actual fraction", title="Calibration")
axes[1, 0].legend()

# Retention score distribution
axes[1, 1].hist(retention_scores, bins=50, color="teal", alpha=0.7, edgecolor="black")
axes[1, 1].set(xlabel="Retention score", ylabel="Count", title="Retention Score Distribution")

plt.tight_layout()
plt.show()


# %% ---- CELL 10: Feature importance plot ----

top = importance.head(15)
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh(top["feature"], top["importance"], color="steelblue")
ax.set_xlabel("Importance")
ax.set_title("V0 Churn Model — Top Features")
ax.invert_yaxis()
plt.tight_layout()
plt.show()


# %% ---- CELL 11: Score all clients ----

# Re-engineer features on the full dataset (including upstreamed)
score_df = df.copy()

# Apply same feature engineering
for col_name, src_cols, func in [
    ("nbi_momentum",   ["nbi_q4", "nbi_q1"],  lambda d: d["nbi_q4"] - d["nbi_q1"]),
    ("nbi_volatility", nbi_q,                  lambda d: d[nbi_q].std(axis=1)),
    ("log_nbi",        ["nbi_annual"],         lambda d: np.log1p(d["nbi_annual"].clip(lower=0))),
    ("total_txn",      txn_q,                  lambda d: d[txn_q].sum(axis=1)),
    ("max_products",   prod_q,                 lambda d: d[prod_q].max(axis=1)),
]:
    if all(c in score_df.columns for c in src_cols) and src_cols:
        score_df[col_name] = func(score_df)

if txn_q and len(txn_q) >= 2:
    score_df["txn_trend"] = score_df[txn_q[-1]] - score_df[txn_q[0]]
if "quarters_active" in score_df.columns and "total_txn" in score_df.columns:
    score_df["txn_per_quarter"] = np.where(
        score_df["quarters_active"] > 0,
        score_df["total_txn"] / score_df["quarters_active"], 0,
    )

components = []
if "quarters_active" in score_df.columns:
    components.append(score_df["quarters_active"] / 4)
if "max_products" in score_df.columns and score_df["max_products"].max() > 0:
    components.append(score_df["max_products"] / score_df["max_products"].max())
if components:
    score_df["engagement"] = np.mean(components, axis=0)

# Score
X_all = score_df[features].fillna(0)
score_df["retention_score"] = 1 - model.predict_proba(X_all)[:, 1]
score_df["retention_3yr"]   = score_df["retention_score"] ** 3  # constant hazard assumption

print(f"Retention scores: mean = {score_df['retention_score'].mean():.3f}, "
      f"median = {score_df['retention_score'].median():.3f}")

score_df[["client_id", "year", "retention_score", "retention_3yr"]].head(10)


# %% ---- CELL 12: Save scores (optional) ----

# score_df[["client_id", "year", "retention_score", "retention_3yr"]].to_csv(
#     "retention_scores.csv", index=False
# )
# print("Saved to retention_scores.csv")
