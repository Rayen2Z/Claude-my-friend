"""
H5 — Churn Definition Quality

Validates that the derived churn flag is meaningful:
  1. Churn rate per year (stable? reasonable?)
  2. Upstream breakdown (churned vs upstreamed vs retained)
  3. NBI before churn (if NBI columns present)
  4. Churned vs active feature comparison (if numeric features present)

Run standalone:
    python h5_churn_definition.py --data churn_dataset.csv
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path


def _churn_col(df: pd.DataFrame) -> str:
    for c in ("churned", "churned_next_year"):
        if c in df.columns:
            return c
    raise ValueError("No churn column found ('churned' or 'churned_next_year')")


# ---------------------------------------------------------------------------
# Check 1 — Churn rate per year
# ---------------------------------------------------------------------------

def check_churn_rate(df: pd.DataFrame) -> pd.DataFrame:
    cc = _churn_col(df)
    rows = []
    for year in sorted(df["year"].unique()):
        yd = df[df["year"] == year]
        n = len(yd)
        n_churned = (yd[cc] == 1).sum()
        n_up = (yd["is_upstreamed"] == 1).sum() if "is_upstreamed" in yd.columns else 0
        rows.append({
            "year": year,
            "total": n,
            "churned": n_churned,
            "upstreamed": n_up,
            "retained": n - n_churned - n_up,
            "churn_rate": n_churned / n if n else 0,
        })

    summary = pd.DataFrame(rows)

    print("\n--- Check 1: Churn Rate per Year ---")
    print(summary.to_string(index=False))

    if len(summary) >= 2:
        rates = summary["churn_rate"].values
        max_diff = np.max(np.abs(np.diff(rates)))
        if max_diff > 0.05:
            print(f"\n  Warning: churn rate swings by {max_diff:.2%} between years (>5pp).")
        else:
            print(f"\n  Churn rate is stable (max year-over-year delta = {max_diff:.2%}).")

    return summary


# ---------------------------------------------------------------------------
# Check 2 — NBI before churn (only if nbi_annual exists)
# ---------------------------------------------------------------------------

def check_nbi_before_churn(df: pd.DataFrame, output_dir: str = "plots") -> dict:
    cc = _churn_col(df)
    if "nbi_annual" not in df.columns:
        print("\n--- Check 2: NBI Before Churn ---")
        print("  Skipped (no 'nbi_annual' column). Add NBI to your Stock CSVs to enable.")
        return {}

    Path(output_dir).mkdir(exist_ok=True)

    churned = df[df[cc] == 1]["nbi_annual"]
    active = df[df[cc] == 0]["nbi_annual"]

    stats = {
        "churned_mean": churned.mean(),
        "churned_median": churned.median(),
        "active_mean": active.mean(),
        "active_median": active.median(),
        "pct_nbi_gt_100": (churned > 100).mean() * 100,
        "pct_nbi_near_zero": (churned.abs() < 1).mean() * 100,
    }

    print("\n--- Check 2: NBI Before Churn ---")
    print(f"  Churned  — mean: {stats['churned_mean']:>10.2f}  median: {stats['churned_median']:>10.2f}")
    print(f"  Active   — mean: {stats['active_mean']:>10.2f}  median: {stats['active_median']:>10.2f}")
    print(f"  Churned with NBI > 100 EUR : {stats['pct_nbi_gt_100']:.1f}%")
    print(f"  Churned with NBI ~ 0 EUR   : {stats['pct_nbi_near_zero']:.1f}%")

    if stats["pct_nbi_near_zero"] > 30:
        print("  Warning: >30% of churned had NBI~0. Churn flag may be lagging.")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.hist(churned.clip(-500, 5000), bins=50, alpha=0.7, color="red", density=True, label="Churned")
    ax1.hist(active.clip(-500, 5000), bins=50, alpha=0.5, color="blue", density=True, label="Active")
    ax1.axvline(0, color="black", ls="--", alpha=0.4)
    ax1.set_xlabel("Annual NBI (EUR)")
    ax1.set_ylabel("Density")
    ax1.set_title("NBI Distribution: Churned vs Active")
    ax1.legend()

    bp = ax2.boxplot(
        [churned.clip(-1000, 10000).dropna(), active.clip(-1000, 10000).dropna()],
        labels=["Churned", "Active"], patch_artist=True,
    )
    bp["boxes"][0].set(facecolor="red", alpha=0.5)
    bp["boxes"][1].set(facecolor="blue", alpha=0.5)
    ax2.set_ylabel("Annual NBI (EUR)")
    ax2.set_title("NBI Box Plot")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/h5_nbi_before_churn.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot saved: {output_dir}/h5_nbi_before_churn.png")

    return stats


# ---------------------------------------------------------------------------
# Check 3 — Feature comparison (churned vs active)
# ---------------------------------------------------------------------------

def check_feature_comparison(df: pd.DataFrame) -> pd.DataFrame:
    cc = _churn_col(df)

    # Pick available numeric columns (skip identifiers and flags)
    skip = {cc, "churned", "churned_next_year", "is_upstreamed", "client_id", "year"}
    num_cols = [c for c in df.select_dtypes(include="number").columns if c not in skip]

    if not num_cols:
        print("\n--- Check 3: Feature Comparison ---")
        print("  Skipped (no numeric features besides churn flags).")
        return pd.DataFrame()

    churned = df[df[cc] == 1]
    active = df[df[cc] == 0]

    rows = []
    for col in num_cols:
        cm, am = churned[col].mean(), active[col].mean()
        rows.append({
            "feature": col,
            "churned_mean": cm,
            "active_mean": am,
            "diff_pct": (cm - am) / am * 100 if am != 0 else np.nan,
        })

    comp = pd.DataFrame(rows).sort_values("diff_pct", key=abs, ascending=False)

    print("\n--- Check 3: Churned vs Active Features ---")
    print(comp.to_string(index=False, float_format="%.2f"))

    return comp


# ---------------------------------------------------------------------------
# Check 4 — Churn rate stability plot
# ---------------------------------------------------------------------------

def plot_churn_rate(summary: pd.DataFrame, output_dir: str = "plots"):
    if len(summary) < 2:
        return

    Path(output_dir).mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(summary))
    w = 0.35
    ax.bar(x - w / 2, summary["churn_rate"], w, label="Churn", color="coral")
    if summary["upstreamed"].sum() > 0:
        up_rate = summary["upstreamed"] / summary["total"]
        ax.bar(x + w / 2, up_rate, w, label="Upstream", color="teal")
    ax.set_xticks(x)
    ax.set_xticklabels(summary["year"].astype(str))
    ax.set_ylabel("Rate")
    ax.set_title("Annual Churn & Upstream Rates")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend()
    for i, row in summary.iterrows():
        ax.text(i - w / 2, row["churn_rate"] + 0.005, f"{row['churn_rate']:.1%}", ha="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/h5_churn_rate.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot saved: {output_dir}/h5_churn_rate.png")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def run_h5(data_path: str, output_dir: str = "plots"):
    df = pd.read_csv(data_path)

    print("=" * 55)
    print("  H5 — CHURN DEFINITION QUALITY")
    print("=" * 55)

    summary = check_churn_rate(df)
    check_nbi_before_churn(df, output_dir)
    check_feature_comparison(df)
    plot_churn_rate(summary, output_dir)

    print("\n" + "=" * 55)
    print("  H5 complete.")
    print("=" * 55)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--output-dir", default="plots")
    args = p.parse_args()
    run_h5(args.data, args.output_dir)
