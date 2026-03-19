# =============================================================================
# H5 — CHURN DEFINITION QUALITY
# =============================================================================
#
# Validates that the churn flag is meaningful:
#   Check 1: Churn rate per year (stable? reasonable?)
#   Check 2: NBI before churn — churned vs active distribution
#   Check 3: Churned vs active feature comparison
#   Check 4: Churn rate bar chart
#
# Prerequisite: run data_processing.py first to get `df`.
# Or load from CSV:  df = pd.read_csv("churn_dataset.csv")
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


# %% ---- CELL 2: Pick the churn column (works with both data formats) ----

# Auto-detect: Stock-based data uses 'churned', transaction-based uses 'churned_next_year'
CHURN_COL = "churned" if "churned" in df.columns else "churned_next_year"
print(f"Using churn column: '{CHURN_COL}'")


# %% ---- CELL 3: Check 1 — Churn rate per year ----

rows = []
for year in sorted(df["year"].unique()):
    yd = df[df["year"] == year]
    n = len(yd)
    n_churned = (yd[CHURN_COL] == 1).sum()
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
print(summary.to_string(index=False))

# Stability check
if len(summary) >= 2:
    rates = summary["churn_rate"].values
    max_diff = np.max(np.abs(np.diff(rates)))
    print(f"\nMax year-over-year churn rate delta: {max_diff:.2%}")
    if max_diff > 0.05:
        print("Warning: churn rate swings by >5pp between years.")
    else:
        print("Churn rate is stable across years.")


# %% ---- CELL 4: Check 2 — NBI before churn (skip if no NBI column) ----

if "nbi_annual" in df.columns:
    churned_nbi = df[df[CHURN_COL] == 1]["nbi_annual"]
    active_nbi  = df[df[CHURN_COL] == 0]["nbi_annual"]

    print(f"Churned  — mean: {churned_nbi.mean():>10.2f}  median: {churned_nbi.median():>10.2f}")
    print(f"Active   — mean: {active_nbi.mean():>10.2f}  median: {active_nbi.median():>10.2f}")
    print(f"Churned with NBI > 100 EUR : {(churned_nbi > 100).mean()*100:.1f}%")
    print(f"Churned with NBI ~ 0 EUR   : {(churned_nbi.abs() < 1).mean()*100:.1f}%")

    if (churned_nbi.abs() < 1).mean() > 0.30:
        print("Warning: >30% of churned had NBI~0. Flag may be lagging.")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.hist(churned_nbi.clip(-500, 5000), bins=50, alpha=0.7, color="red", density=True, label="Churned")
    ax1.hist(active_nbi.clip(-500, 5000), bins=50, alpha=0.5, color="blue", density=True, label="Active")
    ax1.axvline(0, color="black", ls="--", alpha=0.4)
    ax1.set_xlabel("Annual NBI (EUR)")
    ax1.set_ylabel("Density")
    ax1.set_title("NBI Distribution: Churned vs Active")
    ax1.legend()

    bp = ax2.boxplot(
        [churned_nbi.clip(-1000, 10000).dropna(), active_nbi.clip(-1000, 10000).dropna()],
        labels=["Churned", "Active"], patch_artist=True,
    )
    bp["boxes"][0].set(facecolor="red", alpha=0.5)
    bp["boxes"][1].set(facecolor="blue", alpha=0.5)
    ax2.set_ylabel("Annual NBI (EUR)")
    ax2.set_title("NBI Box Plot")
    plt.tight_layout()
    plt.show()

else:
    print("No 'nbi_annual' column — skipping NBI analysis.")
    print("Add NBI to your Stock CSVs to enable this check.")


# %% ---- CELL 5: Check 3 — Feature comparison (churned vs active) ----

skip = {CHURN_COL, "churned", "churned_next_year", "is_upstreamed", "client_id", "year"}
num_cols = [c for c in df.select_dtypes(include="number").columns if c not in skip]

if num_cols:
    churned = df[df[CHURN_COL] == 1]
    active  = df[df[CHURN_COL] == 0]

    rows = []
    for col in num_cols:
        cm = churned[col].mean()
        am = active[col].mean()
        rows.append({
            "feature": col,
            "churned_mean": cm,
            "active_mean": am,
            "diff_pct": (cm - am) / am * 100 if am != 0 else np.nan,
        })

    comp = pd.DataFrame(rows).sort_values("diff_pct", key=abs, ascending=False)
    print(comp.to_string(index=False, float_format="%.2f"))
else:
    print("No numeric features beyond churn flags — skipping comparison.")
    print("Add NBI, transaction, or product columns to enable this check.")


# %% ---- CELL 6: Check 4 — Churn rate bar chart ----

if len(summary) >= 2:
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(summary))
    w = 0.35

    ax.bar(x - w/2, summary["churn_rate"], w, label="Churn", color="coral")
    if summary["upstreamed"].sum() > 0:
        up_rate = summary["upstreamed"] / summary["total"]
        ax.bar(x + w/2, up_rate, w, label="Upstream", color="teal")

    ax.set_xticks(x)
    ax.set_xticklabels(summary["year"].astype(str))
    ax.set_ylabel("Rate")
    ax.set_title("Annual Churn & Upstream Rates")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend()

    for i, row in summary.iterrows():
        ax.text(i - w/2, row["churn_rate"] + 0.005, f"{row['churn_rate']:.1%}", ha="center", fontsize=9)

    plt.tight_layout()
    plt.show()
