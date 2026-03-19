"""
===============================================================================
  H5 — CHURN DEFINITION QUALITY (Priority: High)
===============================================================================
  Validates the derived churn flag to ensure it's meaningful and well-defined.

  Checks:
  1. Pull clients flagged as "churned" in each year
  2. Document the churn flag definition precisely
  3. NBI distribution before churn — is it materially different from zero?
  4. % with NBI > 100 EUR before churning
  5. % with NBI ≈ 0 EUR before churning ("already gone" — churn flag is lagging)
  6. Overall annual churn rate — stable across years?
  7. Silent attrition detection (account open, NBI near-zero)
  8. Churned vs active client feature comparison
  9. Upstream analysis — how many clients upstreamed vs churned?

  Works with both Stock-based data (column: 'churned') and transaction-based
  data (column: 'churned_next_year').
===============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path
from typing import Optional


def _get_churn_col(df: pd.DataFrame) -> str:
    """Detect which churn column is present."""
    if "churned" in df.columns:
        return "churned"
    elif "churned_next_year" in df.columns:
        return "churned_next_year"
    else:
        raise ValueError("No churn column found. Expected 'churned' or 'churned_next_year'.")


def load_retention_data(path: str) -> pd.DataFrame:
    """Load the output from the data pipeline."""
    return pd.read_csv(path)


# =============================================================================
# CHECK 1: Pull churned clients by year
# =============================================================================

def check_churned_clients_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """List clients flagged as churned, grouped by year."""
    churn_col = _get_churn_col(df)

    yearly_stats = []
    for year in sorted(df["year"].unique()):
        year_data = df[df["year"] == year]
        n_total = year_data["client_id"].nunique()
        n_churned = year_data[year_data[churn_col] == 1]["client_id"].nunique()
        n_upstreamed = 0
        if "is_upstreamed" in year_data.columns:
            n_upstreamed = year_data[year_data["is_upstreamed"] == 1]["client_id"].nunique()

        yearly_stats.append({
            "year": year,
            "total_clients": n_total,
            "churned": n_churned,
            "upstreamed": n_upstreamed,
            "retained": n_total - n_churned - n_upstreamed,
            "churn_rate": n_churned / n_total if n_total > 0 else 0,
        })

    summary = pd.DataFrame(yearly_stats)
    print("\n=== CHECK 1: Churned Clients by Year ===")
    print(summary.to_string(index=False))
    print(f"\nChurn definition: Client in Stock Y but NOT in Stock Y+1 and NOT upstreamed")
    print(f"Upstreamed clients are treated as RETAINED (not churned).")

    return summary


# =============================================================================
# CHECK 2: NBI distribution before churn
# =============================================================================

def check_nbi_before_churn(
    df: pd.DataFrame,
    output_dir: str = "plots",
) -> dict:
    """
    For churned clients: what was their NBI in the year BEFORE churn?
    Plot the distribution and compute key statistics.

    Requires NBI columns (nbi_annual or nbi_q1..q4). If not present,
    prints a message and returns empty — you'll need to enrich the data
    with transaction features first.
    """
    Path(output_dir).mkdir(exist_ok=True)
    churn_col = _get_churn_col(df)

    if "nbi_annual" not in df.columns:
        print("\n=== CHECK 2: NBI Before Churn ===")
        print("  ⚠ No 'nbi_annual' column found. This check requires enriching")
        print("    the Stock-based churn data with transaction features (NBI).")
        print("    Add NBI columns to your Stock CSVs or use enrich_churn_with_features().")
        return {}

    churned = df[df[churn_col] == 1].copy()
    active = df[df[churn_col] == 0].copy()

    if churned.empty:
        print("No churned clients found — cannot analyze NBI before churn.")
        return {}

    nbi_churned = churned["nbi_annual"]
    nbi_active = active["nbi_annual"]

    stats = {
        "churned_mean_nbi": nbi_churned.mean(),
        "churned_median_nbi": nbi_churned.median(),
        "churned_std_nbi": nbi_churned.std(),
        "active_mean_nbi": nbi_active.mean(),
        "active_median_nbi": nbi_active.median(),
        "pct_nbi_gt_100": (nbi_churned > 100).mean() * 100,
        "pct_nbi_near_zero": (nbi_churned.abs() < 1.0).mean() * 100,
        "pct_nbi_negative": (nbi_churned < 0).mean() * 100,
    }

    print("\n=== CHECK 2: NBI Before Churn ===")
    print(f"  Churned clients: mean NBI = {stats['churned_mean_nbi']:.2f} EUR")
    print(f"  Churned clients: median NBI = {stats['churned_median_nbi']:.2f} EUR")
    print(f"  Active clients:  mean NBI = {stats['active_mean_nbi']:.2f} EUR")
    print(f"  Active clients:  median NBI = {stats['active_median_nbi']:.2f} EUR")
    print(f"  % with NBI > 100 EUR before churn: {stats['pct_nbi_gt_100']:.1f}%")
    print(f"  % with NBI ≈ 0 EUR before churn:   {stats['pct_nbi_near_zero']:.1f}%")
    print(f"  % with NBI < 0 EUR before churn:    {stats['pct_nbi_negative']:.1f}%")

    if stats["pct_nbi_near_zero"] > 30:
        print("\n  ⚠ WARNING: >30% of churned clients had NBI ≈ 0 before churn.")
        print("    This suggests the churn flag is LAGGING — these clients were")
        print("    'already gone' before the flag triggered. Consider:")
        print("    - Shortening the absence threshold")
        print("    - Adding an NBI-based churn criterion")

    # Plot: NBI distribution for churned vs active
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(nbi_churned.clip(-500, 5000), bins=50, alpha=0.7,
                 label="Churned", color="red", density=True)
    axes[0].hist(nbi_active.clip(-500, 5000), bins=50, alpha=0.5,
                 label="Active", color="blue", density=True)
    axes[0].set_xlabel("Annual NBI (EUR)")
    axes[0].set_ylabel("Density")
    axes[0].set_title("NBI Distribution: Churned vs Active (Year Before)")
    axes[0].legend()
    axes[0].axvline(0, color="black", linestyle="--", alpha=0.5)

    data_to_plot = [
        nbi_churned.clip(-1000, 10000).dropna(),
        nbi_active.clip(-1000, 10000).dropna(),
    ]
    bp = axes[1].boxplot(data_to_plot, labels=["Churned", "Active"], patch_artist=True)
    bp["boxes"][0].set_facecolor("red")
    bp["boxes"][0].set_alpha(0.5)
    bp["boxes"][1].set_facecolor("blue")
    bp["boxes"][1].set_alpha(0.5)
    axes[1].set_ylabel("Annual NBI (EUR)")
    axes[1].set_title("NBI Box Plot: Churned vs Active")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/h5_nbi_before_churn.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot saved to {output_dir}/h5_nbi_before_churn.png")

    return stats


# =============================================================================
# CHECK 3: Annual churn rate stability
# =============================================================================

def check_churn_rate_stability(df: pd.DataFrame, output_dir: str = "plots") -> pd.DataFrame:
    """Is the churn rate stable across years?"""
    Path(output_dir).mkdir(exist_ok=True)
    churn_col = _get_churn_col(df)

    yearly = []
    for year in sorted(df["year"].unique()):
        year_data = df[df["year"] == year]
        total = year_data["client_id"].nunique()
        churned = year_data[year_data[churn_col] == 1]["client_id"].nunique()
        upstreamed = 0
        if "is_upstreamed" in year_data.columns:
            upstreamed = year_data[year_data["is_upstreamed"] == 1]["client_id"].nunique()
        yearly.append({
            "year": year,
            "total_clients": total,
            "churned": churned,
            "upstreamed": upstreamed,
            "churn_rate": churned / total if total > 0 else 0,
            "upstream_rate": upstreamed / total if total > 0 else 0,
        })

    yearly_df = pd.DataFrame(yearly)

    print("\n=== CHECK 3: Churn Rate Stability ===")
    print(yearly_df.to_string(index=False))

    if len(yearly_df) >= 2:
        rates = yearly_df["churn_rate"].values
        max_diff = np.max(np.abs(np.diff(rates)))
        print(f"\n  Max year-over-year churn rate change: {max_diff:.2%}")
        if max_diff > 0.05:
            print("  ⚠ WARNING: Churn rate varies by >5pp between years.")
            print("    Investigate potential structural breaks or data issues.")
        else:
            print("  ✓ Churn rate appears relatively stable.")

    # Plot
    if len(yearly_df) >= 2:
        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(yearly_df))
        width = 0.35
        ax.bar(x - width/2, yearly_df["churn_rate"], width, label="Churn Rate", color="coral")
        if yearly_df["upstream_rate"].sum() > 0:
            ax.bar(x + width/2, yearly_df["upstream_rate"], width, label="Upstream Rate", color="teal")
        ax.set_xticks(x)
        ax.set_xticklabels(yearly_df["year"].astype(str))
        ax.set_ylabel("Rate")
        ax.set_title("Annual Churn & Upstream Rates")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
        ax.legend()
        for i, row in yearly_df.iterrows():
            ax.text(i - width/2, row["churn_rate"] + 0.005, f"{row['churn_rate']:.1%}",
                    ha="center", fontsize=9)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/h5_churn_rate_stability.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Plot saved to {output_dir}/h5_churn_rate_stability.png")

    return yearly_df


# =============================================================================
# CHECK 4: Silent attrition detection
# =============================================================================

def check_silent_attrition(
    df: pd.DataFrame,
    nbi_threshold: float = 10.0,
    output_dir: str = "plots",
) -> pd.DataFrame:
    """
    Find clients who are technically active (not flagged as churned)
    but whose NBI dropped to near-zero. These are "silent attrition" cases.
    """
    Path(output_dir).mkdir(exist_ok=True)
    churn_col = _get_churn_col(df)

    if "nbi_annual" not in df.columns:
        print("\n=== CHECK 4: Silent Attrition ===")
        print("  ⚠ No 'nbi_annual' column. Requires NBI data to detect silent attrition.")
        return pd.DataFrame()

    active = df[df[churn_col] == 0].copy()
    silent = active[active["nbi_annual"].abs() < nbi_threshold].copy()

    total_active = len(active)
    n_silent = len(silent)
    pct_silent = n_silent / total_active * 100 if total_active > 0 else 0

    print("\n=== CHECK 4: Silent Attrition ===")
    print(f"  Total active client-years: {total_active}")
    print(f"  Silent attrition (NBI < {nbi_threshold} EUR): {n_silent} ({pct_silent:.1f}%)")

    if pct_silent > 5:
        print(f"\n  ⚠ WARNING: {pct_silent:.1f}% of 'active' clients have near-zero NBI.")
        print("    These clients are effectively churned but not flagged.")
        print("    Consider adding NBI-based churn criterion or a separate")
        print("    'silent attrition' label for your retention model.")

    silent_by_year = []
    for year in sorted(active["year"].unique()):
        yr_active = active[active["year"] == year]
        yr_silent = yr_active[yr_active["nbi_annual"].abs() < nbi_threshold]
        silent_by_year.append({
            "year": year,
            "active_clients": len(yr_active),
            "silent_attrition": len(yr_silent),
            "pct_silent": len(yr_silent) / len(yr_active) * 100 if len(yr_active) > 0 else 0,
        })

    silent_df = pd.DataFrame(silent_by_year)
    print("\n  Silent attrition by year:")
    print(silent_df.to_string(index=False))

    return silent_df


# =============================================================================
# CHECK 5: Churned vs active feature comparison
# =============================================================================

def check_churned_vs_active_features(
    df: pd.DataFrame,
    output_dir: str = "plots",
) -> pd.DataFrame:
    """Quick comparison of churned vs active clients on key features."""
    Path(output_dir).mkdir(exist_ok=True)
    churn_col = _get_churn_col(df)

    # Dynamically pick available numeric feature columns
    feature_cols = []
    for col in ["nbi_annual", "quarters_active", "age", "tenure_months"]:
        if col in df.columns:
            feature_cols.append(col)
    for q in range(1, 5):
        col = f"n_products_q{q}"
        if col in df.columns:
            feature_cols.append(col)
            break

    if not feature_cols:
        print("\n=== CHECK 5: Churned vs Active — Feature Comparison ===")
        print("  ⚠ No numeric feature columns available for comparison.")
        print("    Enrich your Stock data with NBI/transaction features first.")
        return pd.DataFrame()

    churned = df[df[churn_col] == 1]
    active = df[df[churn_col] == 0]

    comparison = []
    for col in feature_cols:
        if col not in df.columns:
            continue
        comparison.append({
            "feature": col,
            "churned_mean": churned[col].mean(),
            "active_mean": active[col].mean(),
            "churned_median": churned[col].median(),
            "active_median": active[col].median(),
            "diff_pct": (
                (churned[col].mean() - active[col].mean()) / active[col].mean() * 100
                if active[col].mean() != 0 else np.nan
            ),
        })

    comp_df = pd.DataFrame(comparison)
    print("\n=== CHECK 5: Churned vs Active — Feature Comparison ===")
    print(comp_df.to_string(index=False, float_format="%.2f"))

    return comp_df


# =============================================================================
# CHECK 6: Upstream analysis
# =============================================================================

def check_upstream_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze upstreamed clients — are they truly different from churned?"""
    churn_col = _get_churn_col(df)

    if "is_upstreamed" not in df.columns:
        print("\n=== CHECK 6: Upstream Analysis ===")
        print("  ⚠ No 'is_upstreamed' column. Skipping.")
        return pd.DataFrame()

    yearly = []
    for year in sorted(df["year"].unique()):
        yd = df[df["year"] == year]
        total = len(yd)
        n_churned = (yd[churn_col] == 1).sum()
        n_upstream = (yd["is_upstreamed"] == 1).sum()
        n_retained = total - n_churned - n_upstream
        yearly.append({
            "year": year,
            "total": total,
            "retained": n_retained,
            "upstreamed": n_upstream,
            "churned": n_churned,
            "pct_retained": n_retained / total * 100 if total > 0 else 0,
            "pct_upstreamed": n_upstream / total * 100 if total > 0 else 0,
            "pct_churned": n_churned / total * 100 if total > 0 else 0,
        })

    yearly_df = pd.DataFrame(yearly)
    print("\n=== CHECK 6: Upstream Analysis ===")
    print(yearly_df.to_string(index=False, float_format="%.1f"))

    # If NBI available, compare NBI of upstreamed vs retained vs churned
    if "nbi_annual" in df.columns:
        print("\n  NBI comparison:")
        for label, mask in [("Retained", (df[churn_col] == 0) & (df["is_upstreamed"] == 0)),
                             ("Upstreamed", df["is_upstreamed"] == 1),
                             ("Churned", df[churn_col] == 1)]:
            subset = df[mask]
            if not subset.empty:
                print(f"    {label:12s}: mean NBI = {subset['nbi_annual'].mean():>10.2f}, "
                      f"median = {subset['nbi_annual'].median():>10.2f}, n = {len(subset)}")

    return yearly_df


# =============================================================================
# RUN ALL H5 CHECKS
# =============================================================================

def run_all_h5_checks(
    data_path: str,
    output_dir: str = "plots",
) -> dict:
    """Run all H5 churn definition quality checks."""
    df = load_retention_data(data_path)

    print("=" * 70)
    print("  H5 — CHURN DEFINITION QUALITY VALIDATION")
    print("=" * 70)

    results = {}
    results["churned_by_year"] = check_churned_clients_by_year(df)
    results["nbi_stats"] = check_nbi_before_churn(df, output_dir)
    results["churn_stability"] = check_churn_rate_stability(df, output_dir)
    results["silent_attrition"] = check_silent_attrition(df, output_dir=output_dir)
    results["feature_comparison"] = check_churned_vs_active_features(df, output_dir)
    results["upstream_analysis"] = check_upstream_analysis(df)

    print("\n" + "=" * 70)
    print("  H5 VALIDATION COMPLETE")
    print("=" * 70)
    print("\nKey questions for your business team:")
    print("  1. Is there a difference between 'account closed' and 'relationship ended'?")
    print("     A client might close one account but keep another.")
    print("  2. Are upstreamed clients truly gone from your portfolio, or do some")
    print("     maintain accounts in both mainstream and VIP?")
    print("  3. Is the upstream threshold (NBI/AUM cutoff) consistent across years?")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H5 Churn Definition Quality Checks")
    parser.add_argument("--data", required=True, help="Path to retention model data CSV")
    parser.add_argument("--output-dir", default="plots")
    args = parser.parse_args()

    run_all_h5_checks(args.data, args.output_dir)
