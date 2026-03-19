"""
===============================================================================
  CHURN / RETENTION DATA PIPELINE
===============================================================================
  Transforms raw client data into the annual+quarterly structure used by the
  CLV model, with churn labels derived from month-over-month presence.

  Input:  Raw client-level monthly data (CSV export from SAP BI or DB connection)
  Output: One row per client per year with quarterly features + churn target
===============================================================================
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


def load_data(
    filepath: str,
    date_col: str = "transaction_date",
    client_col: str = "client_id",
) -> pd.DataFrame:
    """Load raw transaction data from CSV (SAP BI export)."""
    df = pd.read_csv(filepath, parse_dates=[date_col])
    df.rename(columns={date_col: "transaction_date", client_col: "client_id"}, inplace=True)
    return df


# =============================================================================
# STEP 1: Derive churn from monthly presence
# =============================================================================

def derive_monthly_churn(
    df: pd.DataFrame,
    absence_threshold: int = 3,
) -> pd.DataFrame:
    """
    Derive churn by comparing client presence month-over-month.

    A client is flagged as churned if they disappear for `absence_threshold`
    consecutive months. This avoids false positives from temporary inactivity.

    Parameters
    ----------
    df : DataFrame with at least ['client_id', 'transaction_date']
    absence_threshold : Number of consecutive absent months to confirm churn

    Returns
    -------
    DataFrame with columns:
        client_id, churn_month, last_active_month
    """
    # Build monthly presence
    df["active_month"] = df["transaction_date"].dt.to_period("M")
    monthly_presence = df.groupby("client_id")["active_month"].apply(set).reset_index()
    monthly_presence.rename(columns={"active_month": "active_months"}, inplace=True)

    # Full calendar of months
    all_months = pd.period_range(
        df["transaction_date"].min(),
        df["transaction_date"].max(),
        freq="M",
    )

    churn_records = []

    for _, row in monthly_presence.iterrows():
        client_id = row["client_id"]
        active = row["active_months"]

        consecutive_absent = 0
        last_active = None

        for month in all_months:
            if month in active:
                consecutive_absent = 0
                last_active = month
            else:
                if last_active is not None:
                    consecutive_absent += 1
                    if consecutive_absent == absence_threshold:
                        churn_records.append({
                            "client_id": client_id,
                            "last_active_month": last_active,
                            "churn_month": last_active + absence_threshold,
                        })
                        break  # Only record first confirmed churn

    churn_df = pd.DataFrame(churn_records)
    if not churn_df.empty:
        churn_df["churn_month"] = churn_df["churn_month"].apply(
            lambda p: p.to_timestamp()
        )
        churn_df["last_active_month"] = churn_df["last_active_month"].apply(
            lambda p: p.to_timestamp()
        )
    return churn_df


# =============================================================================
# STEP 2: Build quarterly features (aligned with CLV structure)
# =============================================================================

def build_quarterly_features(
    df: pd.DataFrame,
    nbi_col: str = "nbi_amount",
    product_col: Optional[str] = "product_id",
) -> pd.DataFrame:
    """
    Aggregate transaction data into one-row-per-client-per-year with quarterly
    snapshot columns, matching the CLV model structure.

    Parameters
    ----------
    df : Raw transaction DataFrame
    nbi_col : Column name for Net Banking Income
    product_col : Column name for product identifier (optional)

    Returns
    -------
    DataFrame: one row per (client_id, year) with quarterly features
    """
    df = df.copy()
    df["year"] = df["transaction_date"].dt.year
    df["quarter"] = df["transaction_date"].dt.quarter

    # Transaction counts per quarter
    txn_counts = (
        df.groupby(["client_id", "year", "quarter"])
        .size()
        .unstack(fill_value=0)
        .rename(columns={q: f"n_transactions_q{q}" for q in range(1, 5)})
        .reset_index()
    )

    # NBI per quarter
    if nbi_col in df.columns:
        nbi_quarterly = (
            df.groupby(["client_id", "year", "quarter"])[nbi_col]
            .sum()
            .unstack(fill_value=0)
            .rename(columns={q: f"nbi_q{q}" for q in range(1, 5)})
            .reset_index()
        )
    else:
        nbi_quarterly = df[["client_id", "year"]].drop_duplicates()
        for q in range(1, 5):
            nbi_quarterly[f"nbi_q{q}"] = 0.0

    # Product counts per quarter
    if product_col and product_col in df.columns:
        prod_counts = (
            df.groupby(["client_id", "year", "quarter"])[product_col]
            .nunique()
            .unstack(fill_value=0)
            .rename(columns={q: f"n_products_q{q}" for q in range(1, 5)})
            .reset_index()
        )
    else:
        prod_counts = df[["client_id", "year"]].drop_duplicates()
        for q in range(1, 5):
            prod_counts[f"n_products_q{q}"] = 0

    # Merge all quarterly features
    features = txn_counts.merge(nbi_quarterly, on=["client_id", "year"], how="outer")
    if product_col and product_col in df.columns:
        features = features.merge(prod_counts, on=["client_id", "year"], how="outer")

    features = features.fillna(0)

    # Derived features
    for q in range(1, 5):
        col = f"n_transactions_q{q}"
        if col in features.columns:
            features[f"active_q{q}"] = (features[col] > 0).astype(int)

    features["quarters_active"] = sum(
        features[f"active_q{q}"] for q in range(1, 5) if f"active_q{q}" in features.columns
    )

    # NBI trend
    if "nbi_q1" in features.columns and "nbi_q4" in features.columns:
        features["nbi_trend_q4_vs_q1"] = features["nbi_q4"] - features["nbi_q1"]
        features["nbi_growth_rate"] = np.where(
            features["nbi_q1"] > 0,
            (features["nbi_q4"] - features["nbi_q1"]) / features["nbi_q1"],
            np.nan,
        )

    features["nbi_annual"] = sum(
        features[f"nbi_q{q}"] for q in range(1, 5) if f"nbi_q{q}" in features.columns
    )

    # Activity pattern
    def classify_activity(row):
        q1 = row.get("active_q1", 0)
        q4 = row.get("active_q4", 0)
        qa = row.get("quarters_active", 0)
        if qa == 4:
            return "stable"
        if q1 == 1 and q4 == 0:
            return "declining"
        if q1 == 0 and q4 == 1:
            return "increasing"
        return "irregular"

    features["activity_pattern"] = features.apply(classify_activity, axis=1)

    return features


# =============================================================================
# STEP 3: Attach churn target to annual features
# =============================================================================

def attach_churn_target(
    features_df: pd.DataFrame,
    churn_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add 'churned_next_year' target column.

    The target for year Y is: did the client churn at any point in year Y+1?
    This is what the retention model predicts.
    """
    if churn_df.empty:
        features_df["churned_next_year"] = 0
        return features_df

    churn_df = churn_df.copy()
    churn_df["churn_year"] = churn_df["churn_month"].dt.year

    # For each client, get the year they churned
    churn_lookup = churn_df[["client_id", "churn_year"]].drop_duplicates()

    features_df = features_df.merge(churn_lookup, on="client_id", how="left")
    features_df["churned_next_year"] = (
        features_df["churn_year"] == features_df["year"] + 1
    ).astype(int)
    features_df.drop(columns=["churn_year"], inplace=True)

    return features_df


# =============================================================================
# STEP 4: Attach client demographics
# =============================================================================

def attach_demographics(
    features_df: pd.DataFrame,
    clients_df: pd.DataFrame,
    dob_col: str = "date_of_birth",
    opening_col: str = "account_opening_date",
) -> pd.DataFrame:
    """Add age and tenure to the feature set."""
    clients_df = clients_df.copy()

    if dob_col in clients_df.columns:
        clients_df[dob_col] = pd.to_datetime(clients_df[dob_col])
    if opening_col in clients_df.columns:
        clients_df[opening_col] = pd.to_datetime(clients_df[opening_col])

    features_df = features_df.merge(clients_df, on="client_id", how="left")

    if dob_col in features_df.columns:
        features_df["age"] = features_df["year"] - features_df[dob_col].dt.year

    if opening_col in features_df.columns:
        features_df["tenure_months"] = (
            (pd.to_datetime(features_df["year"].astype(str) + "-12-31")
             - features_df[opening_col]).dt.days / 30.44
        ).round(0).astype("Int64")

    return features_df


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline(
    transactions_path: str,
    clients_path: Optional[str] = None,
    output_path: str = "retention_model_data.csv",
    absence_threshold: int = 3,
    nbi_col: str = "nbi_amount",
    product_col: str = "product_id",
) -> pd.DataFrame:
    """
    Full pipeline: raw data -> CLV-aligned retention dataset.

    Parameters
    ----------
    transactions_path : Path to transaction CSV
    clients_path : Path to client demographics CSV (optional)
    output_path : Where to save the final dataset
    absence_threshold : Months absent to confirm churn
    nbi_col : Column name for NBI amounts
    product_col : Column name for product IDs

    Returns
    -------
    DataFrame ready for retention model training
    """
    print("Loading transaction data...")
    df = load_data(transactions_path)

    print("Deriving monthly churn labels...")
    churn_df = derive_monthly_churn(df, absence_threshold=absence_threshold)
    print(f"  Found {len(churn_df)} confirmed churn events")

    print("Building quarterly features (CLV-aligned)...")
    features = build_quarterly_features(df, nbi_col=nbi_col, product_col=product_col)
    print(f"  Built {len(features)} client-year records")

    print("Attaching churn target...")
    features = attach_churn_target(features, churn_df)
    churn_rate = features["churned_next_year"].mean()
    print(f"  Overall churn rate: {churn_rate:.2%}")

    if clients_path:
        print("Attaching client demographics...")
        clients = pd.read_csv(clients_path)
        features = attach_demographics(features, clients)

    features.to_csv(output_path, index=False)
    print(f"Saved to {output_path}: {features.shape}")

    return features


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build retention model dataset")
    parser.add_argument("--transactions", required=True, help="Path to transactions CSV")
    parser.add_argument("--clients", default=None, help="Path to clients CSV")
    parser.add_argument("--output", default="retention_model_data.csv")
    parser.add_argument("--absence-threshold", type=int, default=3)
    parser.add_argument("--nbi-col", default="nbi_amount")
    parser.add_argument("--product-col", default="product_id")
    args = parser.parse_args()

    run_pipeline(
        transactions_path=args.transactions,
        clients_path=args.clients,
        output_path=args.output,
        absence_threshold=args.absence_threshold,
        nbi_col=args.nbi_col,
        product_col=args.product_col,
    )
