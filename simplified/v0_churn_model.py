"""
V0 Churn Model — Baseline retention scorer.

Binary classifier: P(churn) using gradient boosting.
Output: retention_score = 1 - P(churn) per client.

This V0 works with whatever columns are in the dataset:
  - Minimal (client_id only): skips training, reports churn rates only
  - With NBI columns: trains on NBI features
  - With full features: trains on all available numeric columns

Run standalone:
    python v0_churn_model.py --data churn_dataset.csv

Requirements: scikit-learn (pip install scikit-learn)
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path


def _churn_col(df: pd.DataFrame) -> str:
    for c in ("churned", "churned_next_year"):
        if c in df.columns:
            return c
    raise ValueError("No churn column found")


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create derived features from whatever columns are available."""
    df = df.copy()

    # NBI features
    nbi_q = [f"nbi_q{q}" for q in range(1, 5) if f"nbi_q{q}" in df.columns]
    if len(nbi_q) == 4:
        df["nbi_momentum"] = df["nbi_q4"] - df["nbi_q1"]
        df["nbi_volatility"] = df[nbi_q].std(axis=1)

    if "nbi_annual" in df.columns:
        df["log_nbi"] = np.log1p(df["nbi_annual"].clip(lower=0))

    # Transaction features
    txn_q = [f"n_transactions_q{q}" for q in range(1, 5) if f"n_transactions_q{q}" in df.columns]
    if txn_q:
        df["total_txn"] = df[txn_q].sum(axis=1)
        if "quarters_active" in df.columns:
            df["txn_per_quarter"] = np.where(
                df["quarters_active"] > 0,
                df["total_txn"] / df["quarters_active"],
                0,
            )
        if len(txn_q) >= 2:
            df["txn_trend"] = df[txn_q[-1]] - df[txn_q[0]]

    # Product features
    prod_q = [f"n_products_q{q}" for q in range(1, 5) if f"n_products_q{q}" in df.columns]
    if prod_q:
        df["max_products"] = df[prod_q].max(axis=1)

    # Engagement score
    components = []
    if "quarters_active" in df.columns:
        components.append(df["quarters_active"] / 4)
    if "max_products" in df.columns and df["max_products"].max() > 0:
        components.append(df["max_products"] / df["max_products"].max())
    if components:
        df["engagement"] = np.mean(components, axis=0)

    return df


# ---------------------------------------------------------------------------
# Train model
# ---------------------------------------------------------------------------

def train(
    df: pd.DataFrame,
    test_size: float = 0.2,
    output_dir: str = "plots",
) -> dict:
    """
    Train gradient boosting churn classifier.

    Uses temporal split (most recent year = test) when multiple years exist.
    Falls back to stratified random split otherwise.
    """
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import (
        roc_auc_score, average_precision_score, brier_score_loss,
        classification_report, roc_curve, precision_recall_curve,
    )
    from sklearn.calibration import calibration_curve

    Path(output_dir).mkdir(exist_ok=True)
    cc = _churn_col(df)

    # Exclude upstreamed clients
    if "is_upstreamed" in df.columns:
        n_before = len(df)
        df = df[df["is_upstreamed"] == 0].copy()
        n_excluded = n_before - len(df)
        if n_excluded:
            print(f"  Excluded {n_excluded} upstreamed clients from training")

    df = engineer_features(df)

    # Select features
    exclude = {
        cc, "churned", "churned_next_year", "is_upstreamed",
        "client_id", "year", "activity_pattern", "segment", "region",
        "date_of_birth", "account_opening_date",
    }
    features = [c for c in df.select_dtypes(include="number").columns if c not in exclude]

    if len(features) < 1:
        print("\n  No trainable features. Add columns to your Stock CSVs:")
        print("    nbi_annual, n_transactions_q1..q4, n_products_q1..q4, age, tenure_months")
        return {}

    X = df[features].fillna(0)
    y = df[cc]

    print(f"  Features ({len(features)}): {features}")

    # Temporal split
    if "year" in df.columns and df["year"].nunique() > 1:
        max_year = df["year"].max()
        train_mask = df["year"] < max_year
        test_mask = df["year"] == max_year
        if test_mask.sum() > 10 and train_mask.sum() > 10:
            X_tr, X_te = X[train_mask], X[test_mask]
            y_tr, y_te = y[train_mask], y[test_mask]
            print(f"  Temporal split: train <{max_year}, test ={max_year}")
        else:
            X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=test_size, stratify=y, random_state=42)
            print("  Random stratified split (not enough data for temporal)")
    else:
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=test_size, stratify=y, random_state=42)
        print("  Random stratified split")

    print(f"  Train: {len(X_tr)} (churn={y_tr.mean():.2%}) | Test: {len(X_te)} (churn={y_te.mean():.2%})")

    # Train
    model = GradientBoostingClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, min_samples_leaf=20, random_state=42,
    )
    model.fit(X_tr, y_tr)

    # Evaluate
    p_churn = model.predict_proba(X_te)[:, 1]
    retention = 1 - p_churn

    auc = roc_auc_score(y_te, p_churn)
    ap = average_precision_score(y_te, p_churn)
    brier = brier_score_loss(y_te, p_churn)

    print(f"\n  AUC-ROC          : {auc:.4f}")
    print(f"  Average Precision: {ap:.4f}")
    print(f"  Brier Score      : {brier:.4f}")
    print(f"\n{classification_report(y_te, (p_churn > 0.5).astype(int), target_names=['Retained', 'Churned'])}")

    # Feature importance
    imp = pd.DataFrame({"feature": features, "importance": model.feature_importances_})
    imp = imp.sort_values("importance", ascending=False)
    print("  Top features:")
    for _, r in imp.head(10).iterrows():
        bar = "#" * int(r["importance"] * 80)
        print(f"    {r['feature']:28s} {r['importance']:.4f}  {bar}")

    # --- Plots ---
    fig, axes = plt.subplots(2, 2, figsize=(13, 11))

    # ROC
    fpr, tpr, _ = roc_curve(y_te, p_churn)
    axes[0, 0].plot(fpr, tpr, lw=2, label=f"AUC={auc:.3f}")
    axes[0, 0].plot([0, 1], [0, 1], "--", color="gray")
    axes[0, 0].set(xlabel="FPR", ylabel="TPR", title="ROC Curve")
    axes[0, 0].legend()

    # Precision-Recall
    prec, rec, _ = precision_recall_curve(y_te, p_churn)
    axes[0, 1].plot(rec, prec, lw=2, color="green", label=f"AP={ap:.3f}")
    axes[0, 1].set(xlabel="Recall", ylabel="Precision", title="Precision-Recall")
    axes[0, 1].legend()

    # Calibration
    prob_true, prob_pred = calibration_curve(y_te, p_churn, n_bins=10)
    axes[1, 0].plot(prob_pred, prob_true, "o-", color="purple", label="Model")
    axes[1, 0].plot([0, 1], [0, 1], "--", color="gray", label="Perfect")
    axes[1, 0].set(xlabel="Predicted P(churn)", ylabel="Actual fraction", title="Calibration")
    axes[1, 0].legend()

    # Retention score distribution
    axes[1, 1].hist(retention, bins=50, color="teal", alpha=0.7, edgecolor="black")
    axes[1, 1].set(xlabel="Retention score", ylabel="Count", title="Retention Score Distribution")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/v0_model_diagnostics.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Diagnostics: {output_dir}/v0_model_diagnostics.png")

    # Feature importance plot
    top = imp.head(15)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(top["feature"], top["importance"], color="steelblue")
    ax.set_xlabel("Importance")
    ax.set_title("V0 Churn Model — Feature Importance")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(f"{output_dir}/v0_feature_importance.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Feature importance: {output_dir}/v0_feature_importance.png")

    return {
        "model": model,
        "features": features,
        "metrics": {"auc": auc, "ap": ap, "brier": brier},
        "importance": imp,
        "retention_scores": retention,
        "y_test": y_te,
    }


# ---------------------------------------------------------------------------
# Score all clients
# ---------------------------------------------------------------------------

def score_all(df: pd.DataFrame, model, features: list) -> pd.DataFrame:
    """Apply trained model to all clients."""
    df = engineer_features(df)
    X = df[features].fillna(0)
    p = model.predict_proba(X)[:, 1]

    df = df.copy()
    df["retention_score"] = 1 - p
    df["retention_3yr"] = df["retention_score"] ** 3  # constant hazard assumption

    print(f"\n  Retention scores: mean={df['retention_score'].mean():.3f}, "
          f"median={df['retention_score'].median():.3f}")
    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_v0(data_path: str, output_dir: str = "plots", scores_path: str = "retention_scores.csv"):
    df = pd.read_csv(data_path)

    print("=" * 55)
    print("  V0 CHURN MODEL")
    print("=" * 55)

    results = train(df, output_dir=output_dir)

    if results:
        scored = score_all(df, results["model"], results["features"])
        scored[["client_id", "year", "retention_score", "retention_3yr"]].to_csv(scores_path, index=False)
        print(f"  Scores saved: {scores_path}")

    print("\n" + "=" * 55)
    print("  V0 complete.")
    print("=" * 55)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--output-dir", default="plots")
    p.add_argument("--scores", default="retention_scores.csv")
    args = p.parse_args()
    run_v0(args.data, args.output_dir, args.scores)
