"""
H7 — Data Quality Checks

Validates data integrity before model training:
  1. Missing values per column (flag >10%)
  2. Duplicate client-year records
  3. NBI consistency: quarterly sum vs annual total (if NBI columns present)
  4. Stock consistency: churned+upstreamed overlap, churned-then-reappeared
  5. Zero-balance active clients (if NBI present)

Run standalone:
    python h7_data_quality.py --data churn_dataset.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path


def _churn_col(df: pd.DataFrame) -> str | None:
    for c in ("churned", "churned_next_year"):
        if c in df.columns:
            return c
    return None


# ---------------------------------------------------------------------------
# Check 1 — Missing values
# ---------------------------------------------------------------------------

def check_missing(df: pd.DataFrame, threshold: float = 0.10) -> pd.DataFrame:
    pct = df.isnull().mean().sort_values(ascending=False)
    missing = pd.DataFrame({"feature": pct.index, "pct_missing": pct.values})
    missing["flagged"] = missing["pct_missing"] > threshold

    flagged = missing[missing["flagged"]]

    print("\n--- Check 1: Missing Values ---")
    if len(flagged):
        print(f"  {len(flagged)} columns exceed {threshold:.0%} missing:")
        for _, r in flagged.iterrows():
            print(f"    {r['feature']:30s}  {r['pct_missing']:.1%}")
    else:
        print(f"  All columns below {threshold:.0%} missing threshold.")

    return missing


# ---------------------------------------------------------------------------
# Check 2 — Duplicates
# ---------------------------------------------------------------------------

def check_duplicates(df: pd.DataFrame) -> int:
    keys = [c for c in ["client_id", "year"] if c in df.columns]
    if not keys:
        print("\n--- Check 2: Duplicates ---")
        print("  Skipped (no client_id/year columns).")
        return 0

    n_dupes = df.duplicated(subset=keys).sum()
    print("\n--- Check 2: Duplicates ---")
    print(f"  Rows: {len(df)} | Duplicate ({', '.join(keys)}): {n_dupes}")
    if n_dupes:
        print("  Warning: duplicates found. Deduplicate before training.")
    return n_dupes


# ---------------------------------------------------------------------------
# Check 3 — NBI consistency
# ---------------------------------------------------------------------------

def check_nbi_consistency(df: pd.DataFrame) -> int:
    q_cols = [f"nbi_q{q}" for q in range(1, 5) if f"nbi_q{q}" in df.columns]
    if "nbi_annual" not in df.columns or len(q_cols) < 4:
        print("\n--- Check 3: NBI Consistency ---")
        print("  Skipped (need nbi_annual + nbi_q1..q4 columns).")
        return 0

    sumq = df[q_cols].sum(axis=1)
    disc = (df["nbi_annual"] - sumq).abs()
    n_bad = (disc > 0.01 * df["nbi_annual"].abs().clip(lower=1)).sum()

    print("\n--- Check 3: NBI Consistency ---")
    print(f"  Records with sum(quarterly) != annual: {n_bad}")
    print(f"  Mean absolute discrepancy: {disc.mean():.2f} EUR")
    return int(n_bad)


# ---------------------------------------------------------------------------
# Check 4 — Stock consistency
# ---------------------------------------------------------------------------

def check_stock_consistency(df: pd.DataFrame) -> dict:
    cc = _churn_col(df)
    if cc is None:
        print("\n--- Check 4: Stock Consistency ---")
        print("  Skipped (no churn column).")
        return {}

    issues = {}

    print("\n--- Check 4: Stock Consistency ---")

    # Churned AND upstreamed at the same time
    if "is_upstreamed" in df.columns:
        both = ((df[cc] == 1) & (df["is_upstreamed"] == 1)).sum()
        issues["churned_and_upstreamed"] = both
        if both:
            print(f"  Warning: {both} rows flagged as BOTH churned AND upstreamed.")
        else:
            print("  OK: no churned+upstreamed overlap.")

    # Churned in year Y then reappears in Y+1
    years = sorted(df["year"].unique())
    reappeared = 0
    for i in range(len(years) - 1):
        y1, y2 = years[i], years[i + 1]
        churned_ids = set(df[(df["year"] == y1) & (df[cc] == 1)]["client_id"])
        present_ids = set(df[df["year"] == y2]["client_id"])
        overlap = churned_ids & present_ids
        if overlap:
            reappeared += len(overlap)
            print(f"  Warning: {len(overlap)} clients churned in {y1} reappear in {y2}.")
    if not reappeared:
        print("  OK: no churned clients reappear in later years.")
    issues["reappeared"] = reappeared

    # Year-over-year counts
    print("\n  Client counts by year:")
    for y in years:
        n = df[df["year"] == y]["client_id"].nunique()
        print(f"    {y}: {n:>8,}")

    return issues


# ---------------------------------------------------------------------------
# Check 5 — Zero-balance active
# ---------------------------------------------------------------------------

def check_zero_balance(df: pd.DataFrame) -> int:
    cc = _churn_col(df)
    nbi_cols = [c for c in df.columns if c.startswith("nbi_q")]
    if cc is None or not nbi_cols:
        print("\n--- Check 5: Zero-Balance Active ---")
        print("  Skipped (need churn column + NBI columns).")
        return 0

    active = df[df[cc] == 0]
    zero = (active[nbi_cols].abs() < 0.01).all(axis=1).sum()
    pct = zero / len(active) * 100 if len(active) else 0

    print("\n--- Check 5: Zero-Balance Active ---")
    print(f"  Active clients: {len(active)} | NBI all ~0: {zero} ({pct:.1f}%)")
    if pct > 5:
        print("  Warning: significant silent attrition. Consider extra churn criterion.")
    return zero


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def run_h7(data_path: str):
    df = pd.read_csv(data_path)

    print("=" * 55)
    print("  H7 — DATA QUALITY CHECKS")
    print("=" * 55)

    check_missing(df)
    check_duplicates(df)
    check_nbi_consistency(df)
    check_stock_consistency(df)
    check_zero_balance(df)

    print("\n" + "=" * 55)
    print("  H7 complete.")
    print("=" * 55)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    args = p.parse_args()
    run_h7(args.data)
