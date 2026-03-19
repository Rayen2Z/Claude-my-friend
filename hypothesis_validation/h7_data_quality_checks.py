"""
===============================================================================
  H7 — DATA QUALITY CHECKS (Priority: High)
===============================================================================
  Validates data quality before feeding into the retention model.

  Checks:
  1. Missing values: % missing per feature, flag any > 10%
  2. Duplicates: Any duplicate client_ids per month?
  3. NBI consistency: Does sum of product-level NBI = total NBI per client?
  4. Temporal gaps: Clients with missing months in monthly data
  5. Zero-balance active: All products at zero balance but still flagged active
===============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional


# =============================================================================
# CHECK 1: Missing values
# =============================================================================

def check_missing_values(
    df: pd.DataFrame,
    threshold: float = 0.10,
) -> pd.DataFrame:
    """
    For each feature, compute % missing. Flag features > threshold.
    """
    missing = df.isnull().mean().sort_values(ascending=False)
    missing_df = pd.DataFrame({
        "feature": missing.index,
        "pct_missing": missing.values,
        "n_missing": df.isnull().sum().values,
        "flagged": (missing.values > threshold),
    })

    print("\n=== CHECK 1: Missing Values ===")
    flagged = missing_df[missing_df["flagged"]]
    if len(flagged) > 0:
        print(f"  ⚠ {len(flagged)} features have >{threshold:.0%} missing values:")
        for _, row in flagged.iterrows():
            print(f"    - {row['feature']}: {row['pct_missing']:.1%} missing ({row['n_missing']} rows)")
    else:
        print(f"  ✓ No features exceed {threshold:.0%} missing threshold.")

    # Show top 10 regardless
    print("\n  Top 10 features by missing %:")
    for _, row in missing_df.head(10).iterrows():
        bar = "█" * int(row["pct_missing"] * 50)
        print(f"    {row['feature']:30s} {row['pct_missing']:6.2%} {bar}")

    return missing_df


# =============================================================================
# CHECK 2: Duplicate client-year records
# =============================================================================

def check_duplicates(
    df: pd.DataFrame,
    key_cols: list = None,
) -> pd.DataFrame:
    """Check for duplicate client_id entries per year."""
    if key_cols is None:
        key_cols = ["client_id", "year"]

    available_keys = [c for c in key_cols if c in df.columns]
    if not available_keys:
        print("\n=== CHECK 2: Duplicates ===")
        print("  ⚠ Key columns not found. Skipping.")
        return pd.DataFrame()

    dupes = df[df.duplicated(subset=available_keys, keep=False)]
    n_dupes = len(dupes)
    n_unique_dupes = dupes[available_keys[0]].nunique() if n_dupes > 0 else 0

    print("\n=== CHECK 2: Duplicate Records ===")
    print(f"  Total rows: {len(df)}")
    print(f"  Duplicate rows (same {available_keys}): {n_dupes}")
    print(f"  Unique clients with duplicates: {n_unique_dupes}")

    if n_dupes > 0:
        print(f"\n  ⚠ WARNING: {n_dupes} duplicate records found!")
        print("    Sample duplicates:")
        print(dupes.head(10).to_string(index=False))
    else:
        print("  ✓ No duplicates found.")

    return dupes


# =============================================================================
# CHECK 3: NBI consistency (product-level vs total)
# =============================================================================

def check_nbi_consistency(
    df: pd.DataFrame,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """
    Verify that sum of quarterly NBI ≈ annual NBI.
    Flag discrepancies exceeding tolerance.
    """
    quarterly_cols = [f"nbi_q{q}" for q in range(1, 5)]
    available_q_cols = [c for c in quarterly_cols if c in df.columns]

    if "nbi_annual" not in df.columns or len(available_q_cols) < 4:
        print("\n=== CHECK 3: NBI Consistency ===")
        print("  ⚠ Required NBI columns not found. Skipping.")
        return pd.DataFrame()

    df = df.copy()
    df["nbi_sum_quarters"] = df[available_q_cols].sum(axis=1)
    df["nbi_discrepancy"] = (df["nbi_annual"] - df["nbi_sum_quarters"]).abs()
    df["nbi_discrepancy_pct"] = np.where(
        df["nbi_annual"].abs() > 0,
        df["nbi_discrepancy"] / df["nbi_annual"].abs(),
        0,
    )

    flagged = df[df["nbi_discrepancy_pct"] > tolerance]

    print("\n=== CHECK 3: NBI Consistency (Quarterly Sum vs Annual) ===")
    print(f"  Total records: {len(df)}")
    print(f"  Records with discrepancy > {tolerance:.0%}: {len(flagged)}")
    print(f"  Mean absolute discrepancy: {df['nbi_discrepancy'].mean():.2f} EUR")
    print(f"  Max absolute discrepancy: {df['nbi_discrepancy'].max():.2f} EUR")

    if len(flagged) > 0:
        print(f"\n  ⚠ {len(flagged)} records have NBI inconsistencies:")
        print(flagged[["client_id", "year", "nbi_annual", "nbi_sum_quarters",
                        "nbi_discrepancy"]].head(10).to_string(index=False))
    else:
        print("  ✓ NBI quarterly sums are consistent with annual totals.")

    return flagged


# =============================================================================
# CHECK 4: Temporal gaps in monthly data
# =============================================================================

def check_temporal_gaps(
    transactions_df: pd.DataFrame,
    output_dir: str = "plots",
) -> pd.DataFrame:
    """
    Check for clients with missing months in the monthly transaction data.
    """
    Path(output_dir).mkdir(exist_ok=True)

    df = transactions_df.copy()
    df["month"] = df["transaction_date"].dt.to_period("M")

    # For each client, find expected vs actual months
    gap_records = []
    client_months = df.groupby("client_id")["month"].agg(["min", "max", "nunique"])

    for client_id, row in client_months.iterrows():
        expected = len(pd.period_range(row["min"], row["max"], freq="M"))
        actual = row["nunique"]
        gaps = expected - actual

        if gaps > 0:
            gap_records.append({
                "client_id": client_id,
                "first_month": row["min"],
                "last_month": row["max"],
                "expected_months": expected,
                "actual_months": actual,
                "missing_months": gaps,
                "gap_pct": gaps / expected * 100,
            })

    gap_df = pd.DataFrame(gap_records)

    print("\n=== CHECK 4: Temporal Gaps ===")
    total_clients = client_months.shape[0]
    clients_with_gaps = len(gap_df)
    print(f"  Total clients: {total_clients}")
    print(f"  Clients with temporal gaps: {clients_with_gaps} ({clients_with_gaps/total_clients*100:.1f}%)")

    if not gap_df.empty:
        print(f"  Average missing months: {gap_df['missing_months'].mean():.1f}")
        print(f"  Max missing months: {gap_df['missing_months'].max()}")
        print(f"\n  Distribution of gap sizes:")
        gap_dist = gap_df["missing_months"].describe()
        print(gap_dist.to_string())

        # Plot distribution of gaps
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(gap_df["missing_months"], bins=30, color="orange", alpha=0.7, edgecolor="black")
        ax.set_xlabel("Number of Missing Months")
        ax.set_ylabel("Number of Clients")
        ax.set_title("Distribution of Temporal Gaps per Client")
        plt.tight_layout()
        plt.savefig(f"{output_dir}/h7_temporal_gaps.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Plot saved to {output_dir}/h7_temporal_gaps.png")
    else:
        print("  ✓ No temporal gaps found.")

    return gap_df


# =============================================================================
# CHECK 5: Zero-balance active clients
# =============================================================================

def check_zero_balance_active(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find clients flagged as active (not churned) but with all NBI at zero.
    These may need special handling.
    """
    churn_col = "churned" if "churned" in df.columns else "churned_next_year"
    if churn_col not in df.columns:
        print("\n=== CHECK 5: Zero-Balance Active ===")
        print("  ⚠ No churn column found. Skipping.")
        return pd.DataFrame()
    active = df[df[churn_col] == 0].copy()

    nbi_cols = [c for c in df.columns if c.startswith("nbi_q")]
    if not nbi_cols:
        print("\n=== CHECK 5: Zero-Balance Active ===")
        print("  ⚠ No NBI columns found. Skipping.")
        return pd.DataFrame()

    active["all_nbi_zero"] = (active[nbi_cols].abs() < 0.01).all(axis=1)
    zero_balance = active[active["all_nbi_zero"]]

    print("\n=== CHECK 5: Zero-Balance Active Clients ===")
    print(f"  Active clients: {len(active)}")
    print(f"  With all quarterly NBI ≈ 0: {len(zero_balance)} ({len(zero_balance)/len(active)*100:.1f}%)")

    if len(zero_balance) > 0:
        print("\n  ⚠ These clients are 'active' but generate no revenue.")
        print("    Consider classifying them as 'silent attrition' or excluding")
        print("    them from the retention model training set.")

    return zero_balance


# =============================================================================
# CHECK 6: Stock file consistency (for Stock-based data)
# =============================================================================

def check_stock_consistency(df: pd.DataFrame) -> dict:
    """
    Validate consistency of Stock-based churn data:
    - Clients flagged as both churned AND upstreamed (should be impossible)
    - Clients appearing in multiple years with conflicting churn flags
    - Year-over-year client count trends
    """
    churn_col = "churned" if "churned" in df.columns else "churned_next_year"
    if churn_col not in df.columns:
        print("\n=== CHECK 6: Stock Consistency ===")
        print("  ⚠ No churn column found. Skipping.")
        return {}

    print("\n=== CHECK 6: Stock File Consistency ===")
    issues = {}

    # Check 1: churned AND upstreamed at the same time
    if "is_upstreamed" in df.columns:
        both = df[(df[churn_col] == 1) & (df["is_upstreamed"] == 1)]
        issues["churned_and_upstreamed"] = len(both)
        if len(both) > 0:
            print(f"  ⚠ {len(both)} rows are flagged as BOTH churned AND upstreamed!")
            print("    These should be mutually exclusive. Review your data.")
        else:
            print("  ✓ No clients flagged as both churned and upstreamed.")

    # Check 2: Clients who churned in year Y but reappear in year Y+1
    years = sorted(df["year"].unique())
    reappeared = 0
    for i in range(len(years) - 1):
        y1, y2 = years[i], years[i + 1]
        churned_y1 = set(df[(df["year"] == y1) & (df[churn_col] == 1)]["client_id"])
        present_y2 = set(df[df["year"] == y2]["client_id"])
        overlap = churned_y1 & present_y2
        if overlap:
            reappeared += len(overlap)
            print(f"  ⚠ {len(overlap)} clients churned in {y1} but reappear in {y2}")

    if reappeared == 0:
        print("  ✓ No churned clients reappear in later years.")
    issues["reappeared_after_churn"] = reappeared

    # Check 3: Year-over-year client count changes
    print("\n  Client counts by year:")
    for year in years:
        n = df[df["year"] == year]["client_id"].nunique()
        print(f"    {year}: {n:>8,} clients")
    issues["years"] = years

    return issues


# =============================================================================
# COMPREHENSIVE DATA QUALITY REPORT
# =============================================================================

def run_all_h7_checks(
    retention_data_path: str,
    transactions_path: Optional[str] = None,
    output_dir: str = "plots",
) -> dict:
    """Run all H7 data quality checks."""
    df = pd.read_csv(retention_data_path)

    print("=" * 70)
    print("  H7 — DATA QUALITY CHECKS")
    print("=" * 70)

    results = {}
    results["missing_values"] = check_missing_values(df)
    results["duplicates"] = check_duplicates(df)
    results["nbi_consistency"] = check_nbi_consistency(df)
    results["zero_balance"] = check_zero_balance_active(df)
    results["stock_consistency"] = check_stock_consistency(df)

    if transactions_path:
        from data_pipeline.churn_data_pipeline import load_data
        txn_df = load_data(transactions_path)
        results["temporal_gaps"] = check_temporal_gaps(txn_df, output_dir)

    # Summary
    print("\n" + "=" * 70)
    print("  H7 DATA QUALITY SUMMARY")
    print("=" * 70)

    issues = []
    mv = results["missing_values"]
    if mv is not None and len(mv[mv["flagged"]]) > 0:
        issues.append(f"- {len(mv[mv['flagged']])} features with >10% missing values")

    dupes = results["duplicates"]
    if dupes is not None and len(dupes) > 0:
        issues.append(f"- {len(dupes)} duplicate records found")

    nbi = results["nbi_consistency"]
    if nbi is not None and len(nbi) > 0:
        issues.append(f"- {len(nbi)} NBI inconsistencies")

    zb = results["zero_balance"]
    if zb is not None and len(zb) > 0:
        issues.append(f"- {len(zb)} zero-balance 'active' clients")

    if issues:
        print("\n  Issues found:")
        for issue in issues:
            print(f"    {issue}")
    else:
        print("\n  ✓ No major data quality issues detected.")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H7 Data Quality Checks")
    parser.add_argument("--data", required=True, help="Path to retention model data CSV")
    parser.add_argument("--transactions", default=None, help="Path to raw transactions CSV")
    parser.add_argument("--output-dir", default="plots")
    args = parser.parse_args()

    run_all_h7_checks(args.data, args.transactions, args.output_dir)
