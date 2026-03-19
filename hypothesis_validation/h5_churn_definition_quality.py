"""
===============================================================================
  H5 — CHURN DEFINITION QUALITY (Priority: High)
===============================================================================
  Validates the derived churn flag to ensure it's meaningful and well-defined.

  Checks:
  1. Pull clients flagged as "churned" in 2024 and 2025
  2. Document the churn flag definition precisely
  3. NBI distribution before churn — is it materially different from zero?
  4. % with NBI > 100 EUR before churning
  5. % with NBI ≈ 0 EUR before churning ("already gone" — churn flag is lagging)
  6. Overall annual churn rate — stable between 2024 and 2025?
  7. Silent attrition detection (account open, NBI near-zero)
  8. Churned vs active client feature comparison
===============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path
from typing import Optional


def load_retention_data(path: str) -> pd.DataFrame:
    """Load the output from the data pipeline."""
    return pd.read_csv(path)


# =============================================================================
# CHECK 1: Pull churned clients by year
# =============================================================================

def check_churned_clients_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """List clients flagged as churned, grouped by year."""
    churned = df[df["churned_next_year"] == 1].copy()

    summary = churned.groupby("year").agg(
        n_churned=("client_id", "nunique"),
        total_clients=("client_id", lambda x: df[df["year"] == x.name]["client_id"].nunique()),
    )

    # Simpler approach: compute per year
    yearly_stats = []
    for year in sorted(df["year"].unique()):
        year_data = df[df["year"] == year]
        n_total = year_data["client_id"].nunique()
        n_churned = year_data[year_data["churned_next_year"] == 1]["client_id"].nunique()
        yearly_stats.append({
            "year": year,
            "total_clients": n_total,
            "churned_clients": n_churned,
            "churn_rate": n_churned / n_total if n_total > 0 else 0,
        })

    summary = pd.DataFrame(yearly_stats)
    print("\n=== CHECK 1: Churned Clients by Year ===")
    print(summary.to_string(index=False))
    print(f"\nChurn definition: Client absent for 3+ consecutive months")
    print(f"Target: 'churned_next_year' = 1 if client churns in year Y+1")

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
    """
    Path(output_dir).mkdir(exist_ok=True)

    churned = df[df["churned_next_year"] == 1].copy()
    active = df[df["churned_next_year"] == 0].copy()

    if churned.empty:
        print("No churned clients found — cannot analyze NBI before churn.")
        return {}

    nbi_churned = churned["nbi_annual"]
    nbi_active = active["nbi_annual"]

    # Key statistics
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

    # Histogram
    axes[0].hist(nbi_churned.clip(-500, 5000), bins=50, alpha=0.7,
                 label="Churned", color="red", density=True)
    axes[0].hist(nbi_active.clip(-500, 5000), bins=50, alpha=0.5,
                 label="Active", color="blue", density=True)
    axes[0].set_xlabel("Annual NBI (EUR)")
    axes[0].set_ylabel("Density")
    axes[0].set_title("NBI Distribution: Churned vs Active (Year Before)")
    axes[0].legend()
    axes[0].axvline(0, color="black", linestyle="--", alpha=0.5)

    # Box plot
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
    """Is the churn rate stable between 2024 and 2025?"""
    Path(output_dir).mkdir(exist_ok=True)

    yearly = []
    for year in sorted(df["year"].unique()):
        year_data = df[df["year"] == year]
        total = year_data["client_id"].nunique()
        churned = year_data[year_data["churned_next_year"] == 1]["client_id"].nunique()
        yearly.append({
            "year": year,
            "total_clients": total,
            "churned": churned,
            "churn_rate": churned / total if total > 0 else 0,
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
        ax.bar(yearly_df["year"].astype(str), yearly_df["churn_rate"], color="coral")
        ax.set_ylabel("Churn Rate")
        ax.set_title("Annual Churn Rate Over Time")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
        for i, row in yearly_df.iterrows():
            ax.text(i, row["churn_rate"] + 0.005, f"{row['churn_rate']:.1%}",
                    ha="center", fontsize=10)
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
    Find clients who are technically active (account open, not flagged as churned)
    but whose NBI dropped to near-zero. These are "silent attrition" cases.
    """
    Path(output_dir).mkdir(exist_ok=True)

    # Active clients (not churned) with very low NBI
    active = df[df["churned_next_year"] == 0].copy()
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

    # Year-by-year breakdown
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

    feature_cols = [
        "nbi_annual", "quarters_active",
    ]
    # Add any available demographic columns
    for col in ["age", "tenure_months"]:
        if col in df.columns:
            feature_cols.append(col)
    # Add product columns if available
    for q in range(1, 5):
        col = f"n_products_q{q}"
        if col in df.columns:
            feature_cols.append(col)
            break  # Just include one for summary

    churned = df[df["churned_next_year"] == 1]
    active = df[df["churned_next_year"] == 0]

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

    print("\n" + "=" * 70)
    print("  H5 VALIDATION COMPLETE")
    print("=" * 70)
    print("\nKey questions for your business team:")
    print("  1. Is there a difference between 'account closed' and 'relationship ended'?")
    print("     A client might close one account but keep another.")
    print("  2. What exactly is the churn flag definition? Account closure only,")
    print("     or does it include dormancy (no transactions for X months)?")
    print("  3. Is there a minimum inactivity period before considering churn?")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H5 Churn Definition Quality Checks")
    parser.add_argument("--data", required=True, help="Path to retention model data CSV")
    parser.add_argument("--output-dir", default="plots")
    args = parser.parse_args()

    run_all_h5_checks(args.data, args.output_dir)
