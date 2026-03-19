# =============================================================================
# H3 — CONSTANT HAZARD ASSUMPTION
# =============================================================================
#
# Tests whether churn hazard is constant over time (exponential survival)
# or varies (Weibull/Cox PH needed for V2).
#
# Approach:
#   1. Build per-client survival data (how many years before churn)
#   2. Compute Kaplan-Meier survival curve
#   3. Derive implied hazard from period-1 churn rate
#   4. Compare period-1 vs period-2 → hazard ratio
#   5. Plot empirical vs theoretical curves
#
# Prerequisite: run data_processing.py first to get `df`.
# Or load from CSV:  df = pd.read_csv("churn_dataset.csv")
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# %% ---- CELL 2: Pick the churn column ----

CHURN_COL = "churned" if "churned" in df.columns else "churned_next_year"
print(f"Using churn column: '{CHURN_COL}'")


# %% ---- CELL 3: Build survival data (one row per client) ----
# Duration = how many years the client appears before churning
# Event = 1 if churned, 0 if still active (censored)
# Upstreamed clients are excluded (they graduated, not churned)

work = df.copy()
if "is_upstreamed" in work.columns:
    n_up = (work["is_upstreamed"] == 1).sum()
    work = work[work["is_upstreamed"] == 0]
    print(f"Excluded {n_up} upstreamed rows")

records = []
for cid, grp in work.groupby("client_id"):
    grp = grp.sort_values("year")
    first_year = grp["year"].min()
    last_year  = grp["year"].max()
    ever_churned = grp[CHURN_COL].max()

    if ever_churned == 1:
        churn_year = grp[grp[CHURN_COL] == 1]["year"].min()
        duration = churn_year - first_year + 1
        event = 1
    else:
        duration = last_year - first_year + 1
        event = 0

    records.append({"client_id": cid, "duration_years": max(duration, 1), "event": event})

surv = pd.DataFrame(records)

print(f"\nSurvival data: {len(surv)} clients")
print(f"  Churned  : {surv['event'].sum()}")
print(f"  Censored : {(surv['event'] == 0).sum()}")
surv.head()


# %% ---- CELL 4: Kaplan-Meier estimator ----

def kaplan_meier(duration, event):
    """Compute Kaplan-Meier survival curve. Returns (times, survival_prob)."""
    order = np.argsort(duration)
    duration = duration[order]
    event = event[order]

    times, survival = [], []
    s = 1.0
    for t in np.unique(duration[event == 1]):
        at_risk = np.sum(duration >= t)
        events  = np.sum((duration == t) & (event == 1))
        if at_risk > 0:
            s *= 1 - events / at_risk
        times.append(t)
        survival.append(s)
    return np.array(times), np.array(survival)

dur = surv["duration_years"].values
evt = surv["event"].values

km_times, km_surv = kaplan_meier(dur, evt)


# %% ---- CELL 5: Compute hazard rates and ratio ----

n_total = len(surv)

# Period 1 churn rate
n_churn_p1 = ((evt == 1) & (dur <= 1)).sum()
p1 = n_churn_p1 / n_total if n_total else 0

# Implied constant hazard: h = -ln(1 - p)
h = -np.log(1 - p1) if 0 < p1 < 1 else 0

# Period 2 conditional churn rate (among those who survived period 1)
mask_survived_p1 = (dur > 1) | (evt == 0)
dur_survivors = dur[mask_survived_p1]
evt_survivors = evt[mask_survived_p1]

n_churn_p2 = ((evt_survivors == 1) & (dur_survivors > 1) & (dur_survivors <= 2)).sum()
at_risk_p2 = (dur_survivors > 1).sum()
p2 = n_churn_p2 / at_risk_p2 if at_risk_p2 else 0

hazard_ratio = p2 / p1 if p1 > 0 else np.nan

print(f"Period-1 churn rate  : {p1:.4f} ({p1:.2%})")
print(f"Implied hazard (h)   : {h:.4f} per year")
print(f"Period-2 cond. rate  : {p2:.4f} ({p2:.2%})")
print(f"Hazard ratio (P2/P1) : {hazard_ratio:.3f}")

if np.isnan(hazard_ratio):
    print("\nInsufficient data for hazard ratio.")
elif abs(hazard_ratio - 1.0) < 0.15:
    print("\nConstant hazard holds (ratio within 15% of 1.0).")
    print("-> V1 can use: retention_3yr = retention_score^3")
elif hazard_ratio < 0.85:
    print("\nHazard DECELERATES — survivors get stickier over time.")
    print("-> Consider Weibull model for V2.")
else:
    print("\nHazard ACCELERATES — older clients churn more.")
    print("-> Consider Cox PH model for V2.")


# %% ---- CELL 6: Plot — empirical vs theoretical survival ----

t_theory = np.linspace(0, max(km_times.max() if len(km_times) else 5, 5), 200)
s_theory = np.exp(-h * t_theory)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# Survival curves
if len(km_times):
    ax1.step(km_times, km_surv, where="post", lw=2, color="blue", label="Empirical (KM)")
ax1.plot(t_theory, s_theory, "--", lw=2, color="red", label=f"Theoretical exp(-{h:.3f}t)")
ax1.set_xlabel("Time (years)")
ax1.set_ylabel("Survival probability")
ax1.set_title("Empirical vs Exponential Survival")
ax1.set_ylim(0, 1.05)
ax1.legend()
ax1.grid(alpha=0.3)

# Deviation
if len(km_times):
    dev = km_surv - np.exp(-h * km_times)
    ax2.bar(km_times, dev, width=0.3, color="purple", alpha=0.6)
    ax2.axhline(0, color="black", lw=0.5)
ax2.set_xlabel("Time (years)")
ax2.set_ylabel("Deviation (empirical - theoretical)")
ax2.set_title("Deviation from Constant Hazard")
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.show()
