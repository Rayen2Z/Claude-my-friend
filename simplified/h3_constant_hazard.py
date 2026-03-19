"""
H3 — Constant Hazard Assumption

Tests whether the churn hazard rate is approximately constant over time
(exponential survival: S(t) = exp(-h*t)) or varies (Weibull/Cox PH needed).

Approach (from annual Stock data):
  1. Track how many years each client survives before churning
  2. Compute Kaplan-Meier survival curve
  3. Derive implied constant hazard from period-1 churn rate
  4. Compare period-1 vs period-2 hazard ratio
  5. If ratio ~ 1.0 → constant hazard OK for V1
     If ratio deviates → flag survival model upgrade for V2

Run standalone:
    python h3_constant_hazard.py --data churn_dataset.csv
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path


def _churn_col(df: pd.DataFrame) -> str:
    for c in ("churned", "churned_next_year"):
        if c in df.columns:
            return c
    raise ValueError("No churn column found")


# ---------------------------------------------------------------------------
# Build survival data from annual Stock snapshots
# ---------------------------------------------------------------------------

def build_survival(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per client: duration_years + event (1=churned, 0=censored).

    Duration = number of years the client appears before churning.
    Upstreamed clients are excluded (they didn't churn, they graduated).
    """
    cc = _churn_col(df)

    # Exclude upstreamed
    if "is_upstreamed" in df.columns:
        df = df[df["is_upstreamed"] == 0]

    records = []
    for cid, grp in df.groupby("client_id"):
        grp = grp.sort_values("year")
        first = grp["year"].min()
        last = grp["year"].max()
        ever_churned = grp[cc].max()

        if ever_churned == 1:
            churn_year = grp[grp[cc] == 1]["year"].min()
            duration = churn_year - first + 1
            event = 1
        else:
            duration = last - first + 1
            event = 0

        records.append({"client_id": cid, "duration_years": max(duration, 1), "event": event})

    surv = pd.DataFrame(records)
    print(f"  Survival data: {len(surv)} clients, {surv['event'].sum()} churned, "
          f"{(surv['event']==0).sum()} censored")
    return surv


# ---------------------------------------------------------------------------
# Kaplan-Meier estimator
# ---------------------------------------------------------------------------

def kaplan_meier(duration: np.ndarray, event: np.ndarray):
    """Returns (times, survival_prob) arrays."""
    order = np.argsort(duration)
    duration, event = duration[order], event[order]

    times, survival = [], []
    s = 1.0
    for t in np.unique(duration[event == 1]):
        at_risk = np.sum(duration >= t)
        events = np.sum((duration == t) & (event == 1))
        if at_risk > 0:
            s *= 1 - events / at_risk
        times.append(t)
        survival.append(s)
    return np.array(times), np.array(survival)


# ---------------------------------------------------------------------------
# Validate constant hazard
# ---------------------------------------------------------------------------

def validate(surv: pd.DataFrame, output_dir: str = "plots") -> dict:
    Path(output_dir).mkdir(exist_ok=True)

    dur = surv["duration_years"].values
    evt = surv["event"].values

    km_t, km_s = kaplan_meier(dur, evt)

    # Period-1 churn rate
    n_total = len(surv)
    n_churn_p1 = ((evt == 1) & (dur <= 1)).sum()
    p1 = n_churn_p1 / n_total if n_total else 0

    # Implied constant hazard
    h = -np.log(1 - p1) if 0 < p1 < 1 else 0

    # Period-2 conditional churn rate
    survived_p1 = surv[(dur > 1) | (evt == 0)]
    dur2 = dur[survived_p1.index]
    n_churn_p2 = ((survived_p1["event"] == 1) & (dur2 > 1) & (dur2 <= 2)).sum()
    at_risk_p2 = (dur2 > 1).sum()
    p2 = n_churn_p2 / at_risk_p2 if at_risk_p2 else 0

    hr = p2 / p1 if p1 > 0 else np.nan

    # Print results
    print(f"\n  Period-1 churn rate : {p1:.4f} ({p1:.2%})")
    print(f"  Implied hazard (h)  : {h:.4f} per year")
    print(f"  Period-2 cond. rate : {p2:.4f} ({p2:.2%})")
    print(f"  Hazard ratio (P2/P1): {hr:.3f}")

    if np.isnan(hr):
        print("\n  Insufficient data for hazard ratio.")
    elif abs(hr - 1.0) < 0.15:
        print("\n  Constant hazard holds (ratio within 15% of 1.0).")
        print("  -> V1 can use retention_3yr = retention_score^3")
    elif hr < 0.85:
        print("\n  Hazard DECELERATES. Survivors are stickier over time.")
        print("  -> Consider Weibull model for V2.")
    else:
        print("\n  Hazard ACCELERATES. Older clients churn more.")
        print("  -> Consider Cox PH model for V2.")

    # Plot
    t_theory = np.linspace(0, max(km_t.max() if len(km_t) else 5, 5), 200)
    s_theory = np.exp(-h * t_theory)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    if len(km_t):
        ax1.step(km_t, km_s, where="post", lw=2, color="blue", label="Empirical (KM)")
    ax1.plot(t_theory, s_theory, "--", lw=2, color="red", label=f"Theoretical exp(-{h:.3f}t)")
    ax1.set_xlabel("Time (years)")
    ax1.set_ylabel("Survival probability")
    ax1.set_title("Empirical vs Exponential Survival")
    ax1.set_ylim(0, 1.05)
    ax1.legend()
    ax1.grid(alpha=0.3)

    if len(km_t):
        dev = km_s - np.exp(-h * km_t)
        ax2.bar(km_t, dev, width=0.3, color="purple", alpha=0.6)
        ax2.axhline(0, color="black", lw=0.5)
    ax2.set_xlabel("Time (years)")
    ax2.set_ylabel("Deviation (empirical - theoretical)")
    ax2.set_title("Deviation from Constant Hazard")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/h3_constant_hazard.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Plot saved: {output_dir}/h3_constant_hazard.png")

    return {"p_churn_p1": p1, "p_churn_p2": p2, "hazard": h, "hazard_ratio": hr}


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def run_h3(data_path: str, output_dir: str = "plots"):
    df = pd.read_csv(data_path)

    print("=" * 55)
    print("  H3 — CONSTANT HAZARD ASSUMPTION")
    print("=" * 55)

    surv = build_survival(df)
    results = validate(surv, output_dir)

    print("\n" + "=" * 55)
    print("  H3 complete.")
    print("=" * 55)
    return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--output-dir", default="plots")
    args = p.parse_args()
    run_h3(args.data, args.output_dir)
