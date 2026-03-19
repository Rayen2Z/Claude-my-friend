"""
===============================================================================
  RETENTION SCORING MODEL
===============================================================================
  Produces a retention probability (0-1) for each client, aligned with the
  CLV model's 3-year prediction horizon.

  Architecture:
  - Binary classification: P(retained | features) using gradient boosting
  - Output: retention_score ∈ [0, 1] = probability of staying next year
  - For 3-year CLV: retention_3yr = retention_score^3 (if constant hazard holds)
    or use year-specific scores if H3 rejects constant hazard

  Integration with CLV:
  - CLV = Σ(t=1 to 3) [ NBI_predicted(t) × retention_score^t × discount_factor^t ]
===============================================================================
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


# =============================================================================
# Feature engineering for retention model
# =============================================================================

def engineer_retention_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create features specifically designed for retention prediction.
    These complement the quarterly features from the data pipeline.
    """
    df = df.copy()

    # NBI momentum (Q4 vs Q1 trend within the year)
    if "nbi_q4" in df.columns and "nbi_q1" in df.columns:
        df["nbi_momentum"] = df["nbi_q4"] - df["nbi_q1"]
        df["nbi_volatility"] = df[[f"nbi_q{q}" for q in range(1, 5)]].std(axis=1)

    # Transaction intensity (total transactions / quarters active)
    txn_cols = [f"n_transactions_q{q}" for q in range(1, 5)]
    available_txn = [c for c in txn_cols if c in df.columns]
    if available_txn:
        df["total_transactions"] = df[available_txn].sum(axis=1)
        df["txn_per_active_quarter"] = np.where(
            df.get("quarters_active", 1) > 0,
            df["total_transactions"] / df.get("quarters_active", 1),
            0,
        )
        # Transaction trend
        if len(available_txn) >= 2:
            df["txn_trend"] = df[available_txn[-1]] - df[available_txn[0]]

    # Product diversification
    prod_cols = [f"n_products_q{q}" for q in range(1, 5)]
    available_prod = [c for c in prod_cols if c in df.columns]
    if available_prod:
        df["max_products"] = df[available_prod].max(axis=1)
        df["product_trend"] = df[available_prod[-1]] - df[available_prod[0]]

    # Recency: was the client active in Q4? (most recent quarter)
    if "active_q4" in df.columns:
        df["recent_activity"] = df["active_q4"]

    # Engagement score (composite)
    score_components = []
    if "quarters_active" in df.columns:
        score_components.append(df["quarters_active"] / 4)
    if "max_products" in df.columns:
        max_prod = df["max_products"].max()
        if max_prod > 0:
            score_components.append(df["max_products"] / max_prod)
    if score_components:
        df["engagement_score"] = np.mean(score_components, axis=0)

    # Log-transform skewed NBI
    if "nbi_annual" in df.columns:
        df["log_nbi_annual"] = np.log1p(df["nbi_annual"].clip(lower=0))

    return df


# =============================================================================
# Model training
# =============================================================================

def train_retention_model(
    df: pd.DataFrame,
    target_col: str = "churned_next_year",
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """
    Train a gradient boosting model to predict retention probability.

    The model predicts P(churn), and retention_score = 1 - P(churn).

    Returns
    -------
    dict with keys: model, feature_names, metrics, predictions
    """
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import (
        roc_auc_score, precision_recall_curve, average_precision_score,
        classification_report, brier_score_loss,
    )
    from sklearn.calibration import calibration_curve

    # Prepare features
    df = engineer_retention_features(df)

    # Select numeric features, exclude target and identifiers
    exclude_cols = {
        target_col, "client_id", "year", "churn_month", "last_active_month",
        "start_date", "end_date", "activity_pattern", "segment", "region",
        "date_of_birth", "account_opening_date",
    }
    feature_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if c not in exclude_cols
    ]

    X = df[feature_cols].fillna(0)
    y = df[target_col]

    # Train/test split (stratified, time-aware if possible)
    if "year" in df.columns:
        # Use most recent year as test set (more realistic)
        max_year = df["year"].max()
        train_mask = df["year"] < max_year
        test_mask = df["year"] == max_year

        if test_mask.sum() > 0 and train_mask.sum() > 0:
            X_train, X_test = X[train_mask], X[test_mask]
            y_train, y_test = y[train_mask], y[test_mask]
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, stratify=y, random_state=random_state
            )
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, stratify=y, random_state=random_state
        )

    print(f"\nTraining retention model...")
    print(f"  Features: {len(feature_cols)}")
    print(f"  Train: {len(X_train)} rows, churn rate = {y_train.mean():.2%}")
    print(f"  Test:  {len(X_test)} rows, churn rate = {y_test.mean():.2%}")

    # Train gradient boosting
    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=random_state,
    )
    model.fit(X_train, y_train)

    # Predictions
    y_prob = model.predict_proba(X_test)[:, 1]  # P(churn)
    retention_scores = 1 - y_prob  # P(retained)

    # Metrics
    auc = roc_auc_score(y_test, y_prob)
    ap = average_precision_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    print(f"\n  Model Performance:")
    print(f"    AUC-ROC:          {auc:.4f}")
    print(f"    Average Precision: {ap:.4f}")
    print(f"    Brier Score:       {brier:.4f}")
    print(f"\n  Classification Report:")
    print(classification_report(y_test, (y_prob > 0.5).astype(int),
                                target_names=["Retained", "Churned"]))

    # Feature importance
    importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    print("\n  Top 10 Features:")
    for _, row in importance.head(10).iterrows():
        bar = "█" * int(row["importance"] * 100)
        print(f"    {row['feature']:30s} {row['importance']:.4f} {bar}")

    return {
        "model": model,
        "feature_names": feature_cols,
        "metrics": {"auc": auc, "average_precision": ap, "brier_score": brier},
        "importance": importance,
        "X_test": X_test,
        "y_test": y_test,
        "retention_scores": retention_scores,
    }


# =============================================================================
# Score all clients
# =============================================================================

def score_clients(
    df: pd.DataFrame,
    model,
    feature_names: list,
) -> pd.DataFrame:
    """
    Apply the trained model to score all clients with a retention probability.

    Output includes:
    - retention_score: P(retained next year) ∈ [0, 1]
    - retention_3yr: retention_score^3 (constant hazard assumption)
    """
    df = engineer_retention_features(df)

    X = df[feature_names].fillna(0)
    p_churn = model.predict_proba(X)[:, 1]

    df = df.copy()
    df["retention_score"] = 1 - p_churn
    df["retention_3yr"] = df["retention_score"] ** 3

    print(f"\nRetention Score Distribution:")
    print(f"  Mean:   {df['retention_score'].mean():.4f}")
    print(f"  Median: {df['retention_score'].median():.4f}")
    print(f"  Std:    {df['retention_score'].std():.4f}")
    print(f"  Min:    {df['retention_score'].min():.4f}")
    print(f"  Max:    {df['retention_score'].max():.4f}")

    return df


# =============================================================================
# Plot model diagnostics
# =============================================================================

def plot_model_diagnostics(
    results: dict,
    output_dir: str = "plots",
):
    """Generate diagnostic plots for the retention model."""
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve, precision_recall_curve
    from sklearn.calibration import calibration_curve

    Path(output_dir).mkdir(exist_ok=True)

    y_test = results["y_test"]
    p_churn = 1 - results["retention_scores"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # ROC Curve
    fpr, tpr, _ = roc_curve(y_test, p_churn)
    axes[0, 0].plot(fpr, tpr, color="blue", linewidth=2,
                     label=f"AUC = {results['metrics']['auc']:.3f}")
    axes[0, 0].plot([0, 1], [0, 1], "--", color="gray")
    axes[0, 0].set_xlabel("False Positive Rate")
    axes[0, 0].set_ylabel("True Positive Rate")
    axes[0, 0].set_title("ROC Curve")
    axes[0, 0].legend()

    # Precision-Recall Curve
    prec, rec, _ = precision_recall_curve(y_test, p_churn)
    axes[0, 1].plot(rec, prec, color="green", linewidth=2,
                     label=f"AP = {results['metrics']['average_precision']:.3f}")
    axes[0, 1].set_xlabel("Recall")
    axes[0, 1].set_ylabel("Precision")
    axes[0, 1].set_title("Precision-Recall Curve")
    axes[0, 1].legend()

    # Calibration curve
    prob_true, prob_pred = calibration_curve(y_test, p_churn, n_bins=10)
    axes[1, 0].plot(prob_pred, prob_true, "o-", color="purple", label="Model")
    axes[1, 0].plot([0, 1], [0, 1], "--", color="gray", label="Perfect")
    axes[1, 0].set_xlabel("Predicted Probability")
    axes[1, 0].set_ylabel("Actual Fraction")
    axes[1, 0].set_title("Calibration Curve")
    axes[1, 0].legend()

    # Retention score distribution
    axes[1, 1].hist(results["retention_scores"], bins=50, color="teal",
                     alpha=0.7, edgecolor="black")
    axes[1, 1].set_xlabel("Retention Score")
    axes[1, 1].set_ylabel("Count")
    axes[1, 1].set_title("Retention Score Distribution (Test Set)")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/retention_model_diagnostics.png", dpi=150,
                bbox_inches="tight")
    plt.close()
    print(f"\n  Diagnostics saved to {output_dir}/retention_model_diagnostics.png")

    # Feature importance plot
    importance = results["importance"].head(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(importance["feature"], importance["importance"], color="steelblue")
    ax.set_xlabel("Feature Importance")
    ax.set_title("Top 15 Features — Retention Model")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(f"{output_dir}/retention_feature_importance.png", dpi=150,
                bbox_inches="tight")
    plt.close()
    print(f"  Feature importance saved to {output_dir}/retention_feature_importance.png")


# =============================================================================
# CLV integration helper
# =============================================================================

def compute_clv_with_retention(
    nbi_predictions: pd.DataFrame,
    retention_scores: pd.DataFrame,
    discount_rate: float = 0.05,
    horizon_years: int = 3,
) -> pd.DataFrame:
    """
    Integrate retention scores into CLV calculation.

    CLV = Σ(t=1 to T) [ NBI(t) × S(t) × (1+r)^(-t) ]

    Where:
    - NBI(t) = predicted NBI for year t (from your CLV model)
    - S(t) = retention_score^t (survival probability at year t)
    - r = discount rate

    Parameters
    ----------
    nbi_predictions : DataFrame with columns [client_id, nbi_year1, nbi_year2, nbi_year3]
    retention_scores : DataFrame with columns [client_id, retention_score]
    discount_rate : Annual discount rate
    horizon_years : Number of years to project
    """
    merged = nbi_predictions.merge(
        retention_scores[["client_id", "retention_score"]],
        on="client_id",
        how="left",
    )

    # Fill missing retention scores with portfolio average
    avg_retention = merged["retention_score"].mean()
    merged["retention_score"] = merged["retention_score"].fillna(avg_retention)

    # Compute CLV components
    for t in range(1, horizon_years + 1):
        nbi_col = f"nbi_year{t}"
        if nbi_col not in merged.columns:
            continue

        survival_t = merged["retention_score"] ** t
        discount_t = (1 + discount_rate) ** (-t)

        merged[f"clv_component_year{t}"] = merged[nbi_col] * survival_t * discount_t

    # Total CLV
    clv_cols = [f"clv_component_year{t}" for t in range(1, horizon_years + 1)
                if f"clv_component_year{t}" in merged.columns]
    merged["clv_total"] = merged[clv_cols].sum(axis=1)

    # CLV without retention adjustment (for comparison)
    nbi_cols = [f"nbi_year{t}" for t in range(1, horizon_years + 1)
                if f"nbi_year{t}" in merged.columns]
    for t in range(1, horizon_years + 1):
        if f"nbi_year{t}" in merged.columns:
            merged[f"clv_unadjusted_year{t}"] = (
                merged[f"nbi_year{t}"] * (1 + discount_rate) ** (-t)
            )
    unadj_cols = [c for c in merged.columns if c.startswith("clv_unadjusted_year")]
    merged["clv_unadjusted"] = merged[unadj_cols].sum(axis=1)

    merged["retention_impact_pct"] = np.where(
        merged["clv_unadjusted"] != 0,
        (merged["clv_total"] - merged["clv_unadjusted"]) / merged["clv_unadjusted"].abs() * 100,
        0,
    )

    print(f"\nCLV with Retention Integration:")
    print(f"  Mean CLV (with retention):    {merged['clv_total'].mean():.2f} EUR")
    print(f"  Mean CLV (without retention): {merged['clv_unadjusted'].mean():.2f} EUR")
    print(f"  Mean retention impact:        {merged['retention_impact_pct'].mean():.1f}%")

    return merged


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train and score retention model")
    parser.add_argument("--data", required=True, help="Path to retention model data CSV")
    parser.add_argument("--output-dir", default="plots")
    parser.add_argument("--output-scores", default="client_retention_scores.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.data)

    # Train
    results = train_retention_model(df)
    plot_model_diagnostics(results, args.output_dir)

    # Score all clients
    scored = score_clients(df, results["model"], results["feature_names"])
    scored[["client_id", "year", "retention_score", "retention_3yr"]].to_csv(
        args.output_scores, index=False
    )
    print(f"\nScores saved to {args.output_scores}")
