# =============================================================================
# H7 — DATA QUALITY CHECKS
# =============================================================================
#
# Validates data integrity before model training:
#   Check 1: Missing values per column
#   Check 2: Duplicate client-year records
#   Check 3: NBI consistency (quarterly sum vs annual)
#   Check 4: Stock consistency (churned+upstreamed overlap, reappearances)
#   Check 5: Zero-balance active clients
#
# Prerequisite: run data_processing.py first to get `df`.
# Or load from CSV:  df = pd.read_csv("churn_dataset.csv")
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np


# %% ---- CELL 2: Pick the churn column ----

CHURN_COL = None
if "churned" in df.columns:
    CHURN_COL = "churned"
elif "churned_next_year" in df.columns:
    CHURN_COL = "churned_next_year"
print(f"Using churn column: '{CHURN_COL}'")


# %% ---- CELL 3: Check 1 — Missing values ----

threshold = 0.10  # flag columns with >10% missing

pct_missing = df.isnull().mean().sort_values(ascending=False)
missing_df = pd.DataFrame({"feature": pct_missing.index, "pct_missing": pct_missing.values})
missing_df["flagged"] = missing_df["pct_missing"] > threshold

flagged = missing_df[missing_df["flagged"]]
if len(flagged):
    print(f"{len(flagged)} columns exceed {threshold:.0%} missing:")
    for _, r in flagged.iterrows():
        print(f"  {r['feature']:30s}  {r['pct_missing']:.1%}")
else:
    print(f"All columns below {threshold:.0%} missing. OK.")

missing_df.head(10)


# %% ---- CELL 4: Check 2 — Duplicate client-year records ----

keys = [c for c in ["client_id", "year"] if c in df.columns]
n_dupes = df.duplicated(subset=keys).sum()
print(f"Rows: {len(df)} | Duplicates on ({', '.join(keys)}): {n_dupes}")

if n_dupes:
    print("Warning: duplicates found. Inspect and deduplicate before training.")
    df[df.duplicated(subset=keys, keep=False)].head(10)


# %% ---- CELL 5: Check 3 — NBI consistency (quarterly vs annual) ----

q_cols = [f"nbi_q{q}" for q in range(1, 5) if f"nbi_q{q}" in df.columns]

if "nbi_annual" in df.columns and len(q_cols) == 4:
    sum_quarterly = df[q_cols].sum(axis=1)
    discrepancy = (df["nbi_annual"] - sum_quarterly).abs()
    n_bad = (discrepancy > 0.01 * df["nbi_annual"].abs().clip(lower=1)).sum()

    print(f"Records where sum(Q1..Q4) != annual NBI: {n_bad}")
    print(f"Mean absolute discrepancy: {discrepancy.mean():.2f} EUR")
    print(f"Max  absolute discrepancy: {discrepancy.max():.2f} EUR")
else:
    print("Skipped — need nbi_annual + nbi_q1..q4 columns.")


# %% ---- CELL 6: Check 4 — Stock consistency ----

if CHURN_COL:
    # 4a: Clients flagged as BOTH churned AND upstreamed (should be impossible)
    if "is_upstreamed" in df.columns:
        both = ((df[CHURN_COL] == 1) & (df["is_upstreamed"] == 1)).sum()
        if both:
            print(f"Warning: {both} rows flagged as BOTH churned AND upstreamed!")
        else:
            print("OK: no churned+upstreamed overlap.")

    # 4b: Clients who churned in year Y but reappear in year Y+1
    years = sorted(df["year"].unique())
    reappeared = 0
    for i in range(len(years) - 1):
        y1, y2 = years[i], years[i + 1]
        churned_ids = set(df[(df["year"] == y1) & (df[CHURN_COL] == 1)]["client_id"])
        present_ids = set(df[df["year"] == y2]["client_id"])
        overlap = churned_ids & present_ids
        if overlap:
            reappeared += len(overlap)
            print(f"Warning: {len(overlap)} clients churned in {y1} reappear in {y2}")
    if reappeared == 0:
        print("OK: no churned clients reappear in later years.")

    # 4c: Client counts by year
    print("\nClient counts by year:")
    for y in years:
        n = df[df["year"] == y]["client_id"].nunique()
        print(f"  {y}: {n:>8,}")
else:
    print("Skipped — no churn column found.")


# %% ---- CELL 7: Check 5 — Zero-balance active clients ----

nbi_cols = [c for c in df.columns if c.startswith("nbi_q")]

if CHURN_COL and nbi_cols:
    active = df[df[CHURN_COL] == 0]
    zero_balance = (active[nbi_cols].abs() < 0.01).all(axis=1).sum()
    pct = zero_balance / len(active) * 100 if len(active) else 0

    print(f"Active clients: {len(active)}")
    print(f"With all quarterly NBI ~ 0: {zero_balance} ({pct:.1f}%)")

    if pct > 5:
        print("Warning: significant silent attrition.")
        print("Consider adding an NBI-based churn criterion.")
else:
    print("Skipped — need churn column + NBI columns (nbi_q1..q4).")


# %% ---- CELL 8: Summary ----

print("\n=== DATA QUALITY SUMMARY ===")
print(f"  Total rows    : {len(df)}")
print(f"  Columns       : {len(df.columns)}")
print(f"  Flagged missing (>{threshold:.0%}): {len(flagged)}")
print(f"  Duplicates    : {n_dupes}")
print(f"  Columns available: {list(df.columns)}")
