"""
===============================================================================
  CHURN / RETENTION DATA PIPELINE
===============================================================================
  Two modes of operation:

  MODE 1 (PRIMARY): From Stock CSVs
    Uses CHURN_YYYY folders with Stock Y, Stock Y+1, Upstreaming.csv files.
    Churn is derived by comparing client lists year-over-year.

  MODE 2 (FALLBACK): From transaction data
    Derives churn from monthly transaction presence (3+ month absence).

  CRITICAL: Clients who "upstream" to the VIP portfolio are NOT churned.
  They are flagged as retained (target=0).

  Output: One row per client per year with churn target + any extra columns
          from the Stock files (expandable for quarterly features later).
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
# MODE 1: Build dataset from Stock CSVs (PRIMARY)
# =============================================================================

def run_pipeline_from_stocks(
    base_path: str,
    years: list = None,
    encoding: str = "utf-8",
    output_path: str = "retention_model_data.csv",
) -> pd.DataFrame:
    """
    Build retention dataset from CHURN_YYYY/Stock CSVs.

    This is the primary pipeline. It loads Stock Y vs Stock Y+1 files,
    derives churn, and merges all years into a single dataset.

    Parameters
    ----------
    base_path : Directory containing CHURN_2023/, CHURN_2024/, CHURN_2025/
    years : Years to process (auto-detected if None)
    encoding : CSV encoding (try 'latin-1' if utf-8 fails)
    output_path : Where to save output

    Returns
    -------
    DataFrame: one row per client per year with columns:
        client_id, year, churned, is_upstreamed, + any extra Stock columns
    """
    from data_pipeline.load_churn_csvs import build_churn_dataset

    df = build_churn_dataset(
        base_path=base_path,
        years=years,
        encoding=encoding,
        output_path=output_path,
    )

    return df


# =============================================================================
# MODE 2: Derive churn from transaction presence (FALLBACK)
# =============================================================================

def derive_monthly_churn(
    df: pd.DataFrame,
    absence_threshold: int = 3,
    upstreamed_clients: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Derive churn by comparing client presence month-over-month.

    A client is flagged as churned if they disappear for `absence_threshold`
    consecutive months. Clients who upstreamed to VIP are EXCLUDED from churn.

    Parameters
    ----------
    df : DataFrame with at least ['client_id', 'transaction_date']
    absence_threshold : Number of consecutive absent months to confirm churn
    upstreamed_clients : DataFrame with 'client_id' column listing clients
        who moved to the VIP portfolio. These are NOT churned.

    Returns
    -------
    DataFrame with columns:
        client_id, churn_month, last_active_month
    """
    # Build set of upstreamed client IDs for fast lookup
    upstream_ids = set()
    if upstreamed_clients is not None and not upstreamed_clients.empty:
        upstream_ids = set(upstreamed_clients["client_id"].unique())

    # Build monthly presence
    df = df.copy()
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
    n_upstream_excluded = 0

    for _, row in monthly_presence.iterrows():
        client_id = row["client_id"]
        active = row["active_months"]

        # Skip upstreamed clients — they are NOT churned
        if client_id in upstream_ids:
            n_upstream_excluded += 1
            continue

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

    if n_upstream_excluded > 0:
        print(f"  Excluded {n_upstream_excluded} upstreamed (VIP) clients from churn")

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
# Feature building (used by both modes when transaction data is available)
# =============================================================================

def build_quarterly_features(
    df: pd.DataFrame,
    nbi_col: str = "nbi_amount",
    product_col: Optional[str] = "product_id",
) -> pd.DataFrame:
    """
    Aggregate transaction data into one-row-per-client-per-year with quarterly
    snapshot columns, matching the CLV model structure.
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


def enrich_churn_with_features(
    churn_df: pd.DataFrame,
    features_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge quarterly features (from transaction data) into the churn dataset
    (from Stock CSVs). This enriches the client-year rows with NBI, transaction
    counts, etc. for model training.

    Parameters
    ----------
    churn_df : Output of build_churn_dataset() — has client_id, year, churned
    features_df : Output of build_quarterly_features() — has quarterly columns

    Returns
    -------
    Enriched DataFrame with churn labels + quarterly features
    """
    # Standardize column types for merge
    churn_df = churn_df.copy()
    features_df = features_df.copy()
    churn_df["client_id"] = churn_df["client_id"].astype(str)
    features_df["client_id"] = features_df["client_id"].astype(str)

    merged = churn_df.merge(
        features_df,
        on=["client_id", "year"],
        how="left",
    )

    n_matched = merged[merged["nbi_annual"].notna()].shape[0] if "nbi_annual" in merged.columns else 0
    n_total = len(merged)

    print(f"\n  Feature enrichment:")
    print(f"    Churn rows: {n_total}")
    print(f"    Matched with features: {n_matched} ({n_matched/n_total*100:.1f}%)")
    print(f"    Unmatched (no transaction data): {n_total - n_matched}")

    return merged


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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build retention model dataset")
    parser.add_argument("--mode", choices=["stocks", "transactions"], default="stocks",
                        help="Data source: 'stocks' (CHURN_YYYY folders) or 'transactions' (raw txn CSV)")
    parser.add_argument("--base-path", default=".",
                        help="[stocks mode] Directory containing CHURN_YYYY folders")
    parser.add_argument("--years", nargs="+", type=int, default=None,
                        help="[stocks mode] Years to process (auto-detect if omitted)")
    parser.add_argument("--transactions", default=None,
                        help="[transactions mode] Path to transactions CSV")
    parser.add_argument("--clients", default=None, help="Path to clients CSV")
    parser.add_argument("--encoding", default="utf-8", help="CSV encoding")
    parser.add_argument("--output", default="retention_model_data.csv")
    args = parser.parse_args()

    if args.mode == "stocks":
        df = run_pipeline_from_stocks(
            base_path=args.base_path,
            years=args.years,
            encoding=args.encoding,
            output_path=args.output,
        )
    else:
        print("Transaction-based mode — use run_validation.py for full pipeline")
