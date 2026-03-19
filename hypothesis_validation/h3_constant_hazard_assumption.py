"""
===============================================================================
  H3 — CONSTANT HAZARD ASSUMPTION (Priority: Medium)
===============================================================================
  Validates whether the churn hazard rate is approximately constant over time
  (exponential survival assumption) or if it varies (suggesting a need for a
  more complex survival model like Weibull or Cox PH).

  Checks:
  1. Compute time-to-churn from account opening date
  2. Plot empirical survival curve (Kaplan-Meier)
  3. Compute 1-year churn rate → derive implied constant hazard h = -ln(1 - P_churn)
  4. Overlay theoretical exponential curve exp(-h*t) on empirical
  5. Visual check: does churn accelerate or decelerate over time?
  6. Specific check: year-1 vs year-2 churn rates
  7. If curves diverge → flag survival model upgrade as V2 priority
===============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional


# =============================================================================
# CHECK 1: Compute time-to-churn
# =============================================================================

def compute_time_to_churn(
    transactions_df: pd.DataFrame,
    churn_df: pd.DataFrame,
    clients_df: Optional[pd.DataFrame] = None,
    opening_col: str = "account_opening_date",
    reference_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    For each client, compute time from account opening (or reference date) to churn.
    Clients who haven't churned are right-censored at the observation end date.

    Parameters
    ----------
    transactions_df : Raw transaction data
    churn_df : Output from derive_monthly_churn() with churn_month column
    clients_df : Client demographics with account_opening_date
    opening_col : Column name for account opening date
    reference_date : Fixed reference date (e.g., '2023-01-01') if no opening date

    Returns
    -------
    DataFrame with columns: client_id, duration_months, event (1=churned, 0=censored)
    """
    # Get all unique clients
    all_clients = transactions_df["client_id"].unique()
    observation_end = transactions_df["transaction_date"].max()

    records = []

    for client_id in all_clients:
        # Determine start date
        if clients_df is not None and opening_col in clients_df.columns:
            client_info = clients_df[clients_df["client_id"] == client_id]
            if not client_info.empty:
                start_date = pd.to_datetime(client_info[opening_col].iloc[0])
            else:
                start_date = pd.to_datetime(reference_date or "2023-01-01")
        else:
            # Use first transaction as proxy for account opening
            client_txns = transactions_df[transactions_df["client_id"] == client_id]
            start_date = client_txns["transaction_date"].min()

        # Determine end date and event
        churn_record = churn_df[churn_df["client_id"] == client_id]
        if not churn_record.empty:
            end_date = pd.to_datetime(churn_record["churn_month"].iloc[0])
            event = 1  # Churned
        else:
            end_date = observation_end
            event = 0  # Censored (still active)

        duration_months = (end_date - start_date).days / 30.44

        records.append({
            "client_id": client_id,
            "start_date": start_date,
            "end_date": end_date,
            "duration_months": max(duration_months, 0),
            "event": event,
        })

    return pd.DataFrame(records)


# =============================================================================
# CHECK 2: Kaplan-Meier Survival Curve
# =============================================================================

def kaplan_meier_estimator(
    duration: np.ndarray,
    event: np.ndarray,
) -> tuple:
    """
    Compute the Kaplan-Meier survival function estimate.

    Returns
    -------
    times : sorted unique event times
    survival : KM survival probability at each time
    """
    # Sort by duration
    order = np.argsort(duration)
    duration = duration[order]
    event = event[order]

    unique_times = np.unique(duration[event == 1])
    n = len(duration)

    survival = []
    times = []
    s = 1.0

    for t in unique_times:
        # Number at risk just before time t
        at_risk = np.sum(duration >= t)
        # Number of events at time t
        events_at_t = np.sum((duration == t) & (event == 1))

        if at_risk > 0:
            s *= (1 - events_at_t / at_risk)

        times.append(t)
        survival.append(s)

    return np.array(times), np.array(survival)


# =============================================================================
# CHECK 3-5: Full constant hazard validation
# =============================================================================

def validate_constant_hazard(
    survival_df: pd.DataFrame,
    output_dir: str = "plots",
) -> dict:
    """
    Core H3 validation:
    - Plot Kaplan-Meier curve
    - Compute implied constant hazard from 1-year churn rate
    - Overlay exponential survival curve
    - Check alignment
    """
    Path(output_dir).mkdir(exist_ok=True)

    duration = survival_df["duration_months"].values
    event = survival_df["event"].values

    # Kaplan-Meier estimate
    km_times, km_survival = kaplan_meier_estimator(duration, event)

    # Compute 1-year churn rate
    total_clients = len(survival_df)
    churned_year1 = survival_df[
        (survival_df["event"] == 1) & (survival_df["duration_months"] <= 12)
    ].shape[0]
    at_risk_year1 = survival_df[survival_df["duration_months"] >= 0].shape[0]
    p_churn_year1 = churned_year1 / at_risk_year1 if at_risk_year1 > 0 else 0

    # Implied constant hazard: h = -ln(1 - P_churn) for 12-month period
    if p_churn_year1 > 0 and p_churn_year1 < 1:
        h_annual = -np.log(1 - p_churn_year1)
        h_monthly = h_annual / 12
    else:
        h_annual = 0
        h_monthly = 0

    # Theoretical exponential survival: S(t) = exp(-h * t)
    t_theory = np.linspace(0, km_times.max() if len(km_times) > 0 else 60, 200)
    s_theory = np.exp(-h_monthly * t_theory)

    # Year-2 conditional churn rate (among those who survived year 1)
    survived_year1 = survival_df[
        (survival_df["duration_months"] > 12) | (survival_df["event"] == 0)
    ]
    churned_year2 = survived_year1[
        (survived_year1["event"] == 1) &
        (survived_year1["duration_months"] > 12) &
        (survived_year1["duration_months"] <= 24)
    ].shape[0]
    at_risk_year2 = survived_year1[survived_year1["duration_months"] > 12].shape[0]
    p_churn_year2 = churned_year2 / at_risk_year2 if at_risk_year2 > 0 else 0

    # Results
    results = {
        "total_clients": total_clients,
        "p_churn_year1": p_churn_year1,
        "p_churn_year2_conditional": p_churn_year2,
        "implied_annual_hazard": h_annual,
        "implied_monthly_hazard": h_monthly,
        "hazard_ratio_y2_vs_y1": p_churn_year2 / p_churn_year1 if p_churn_year1 > 0 else np.nan,
    }

    print("\n" + "=" * 70)
    print("  H3 — CONSTANT HAZARD ASSUMPTION VALIDATION")
    print("=" * 70)

    print(f"\n  Total clients: {total_clients}")
    print(f"  1-year churn rate (P_churn): {p_churn_year1:.4f} ({p_churn_year1:.2%})")
    print(f"  Implied constant hazard (annual): h = -ln(1 - {p_churn_year1:.4f}) = {h_annual:.4f}")
    print(f"  Implied constant hazard (monthly): {h_monthly:.6f}")
    print(f"\n  Year-2 conditional churn rate: {p_churn_year2:.4f} ({p_churn_year2:.2%})")
    print(f"  Hazard ratio (Year 2 / Year 1): {results['hazard_ratio_y2_vs_y1']:.3f}")

    if abs(results["hazard_ratio_y2_vs_y1"] - 1.0) < 0.15:
        print("\n  ✓ Hazard appears roughly constant (ratio within 15% of 1.0)")
        print("    Exponential survival assumption is reasonable for V1.")
    elif results["hazard_ratio_y2_vs_y1"] < 0.85:
        print("\n  ⚠ Churn DECELERATES over time (hazard ratio < 0.85)")
        print("    Clients who survive year 1 are less likely to churn in year 2.")
        print("    → Consider Weibull or Cox PH model for V2.")
    else:
        print("\n  ⚠ Churn ACCELERATES over time (hazard ratio > 1.15)")
        print("    Clients become MORE likely to churn as they age.")
        print("    → Consider Weibull or Cox PH model for V2.")

    # =========================================================================
    # PLOT: Empirical vs Theoretical Survival Curves
    # =========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Main survival curve comparison
    ax = axes[0]
    if len(km_times) > 0:
        ax.step(km_times, km_survival, where="post", label="Empirical (Kaplan-Meier)",
                color="blue", linewidth=2)
    ax.plot(t_theory, s_theory, "--", label=f"Theoretical exp(-{h_monthly:.4f}·t)",
            color="red", linewidth=2)
    ax.set_xlabel("Time (months)")
    ax.set_ylabel("Survival Probability")
    ax.set_title("H3: Empirical vs Exponential Survival Curve")
    ax.legend()
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)

    # Deviation plot
    ax2 = axes[1]
    if len(km_times) > 0:
        # Interpolate theoretical at KM times
        s_theory_at_km = np.exp(-h_monthly * km_times)
        deviation = km_survival - s_theory_at_km

        ax2.bar(km_times, deviation, width=0.5, color="purple", alpha=0.6)
        ax2.axhline(0, color="black", linestyle="-", linewidth=0.5)
        ax2.set_xlabel("Time (months)")
        ax2.set_ylabel("Deviation (Empirical - Theoretical)")
        ax2.set_title("Deviation from Constant Hazard Assumption")
        ax2.grid(True, alpha=0.3)

        # Annotate if deviation exceeds threshold
        max_dev = np.max(np.abs(deviation))
        if max_dev > 0.05:
            ax2.annotate(
                f"Max deviation: {max_dev:.3f}",
                xy=(km_times[np.argmax(np.abs(deviation))], max_dev),
                fontsize=10, color="red",
            )

    plt.tight_layout()
    plt.savefig(f"{output_dir}/h3_constant_hazard.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Plot saved to {output_dir}/h3_constant_hazard.png")

    return results


# =============================================================================
# CHECK 6: Cohort-based hazard rates
# =============================================================================

def check_cohort_hazard_rates(
    survival_df: pd.DataFrame,
    output_dir: str = "plots",
) -> pd.DataFrame:
    """
    Compute churn rates by yearly cohorts to see if hazard varies by
    client vintage.
    """
    Path(output_dir).mkdir(exist_ok=True)

    survival_df = survival_df.copy()
    survival_df["start_year"] = survival_df["start_date"].dt.year

    cohort_stats = []
    for year in sorted(survival_df["start_year"].unique()):
        cohort = survival_df[survival_df["start_year"] == year]
        n = len(cohort)
        n_churned = cohort["event"].sum()
        avg_duration = cohort["duration_months"].mean()
        churn_rate = n_churned / n if n > 0 else 0

        cohort_stats.append({
            "cohort_year": year,
            "n_clients": n,
            "n_churned": n_churned,
            "churn_rate": churn_rate,
            "avg_duration_months": avg_duration,
        })

    cohort_df = pd.DataFrame(cohort_stats)

    print("\n=== Cohort-Based Hazard Rates ===")
    print(cohort_df.to_string(index=False, float_format="%.3f"))

    # Plot
    if len(cohort_df) >= 2:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(cohort_df["cohort_year"].astype(str), cohort_df["churn_rate"],
               color="teal", alpha=0.7)
        ax.set_xlabel("Cohort Year")
        ax.set_ylabel("Churn Rate")
        ax.set_title("Churn Rate by Client Cohort (Vintage)")
        plt.tight_layout()
        plt.savefig(f"{output_dir}/h3_cohort_hazard.png", dpi=150, bbox_inches="tight")
        plt.close()

    return cohort_df


# =============================================================================
# RUN ALL H3 CHECKS
# =============================================================================

def run_all_h3_checks(
    transactions_path: str,
    churn_path: str,
    clients_path: Optional[str] = None,
    output_dir: str = "plots",
) -> dict:
    """
    Run the full H3 constant hazard assumption validation.

    Parameters
    ----------
    transactions_path : Path to raw transaction data CSV
    churn_path : Path to churn events CSV (output of derive_monthly_churn)
    clients_path : Path to client demographics CSV (optional)
    output_dir : Directory for plot output
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from data_pipeline.churn_data_pipeline import load_data, derive_monthly_churn

    print("Loading data...")
    transactions_df = load_data(transactions_path)
    churn_df = pd.read_csv(churn_path, parse_dates=["churn_month", "last_active_month"])

    clients_df = None
    if clients_path:
        clients_df = pd.read_csv(clients_path)

    print("Computing time-to-churn...")
    survival_df = compute_time_to_churn(
        transactions_df, churn_df, clients_df
    )

    results = {}
    results["constant_hazard"] = validate_constant_hazard(survival_df, output_dir)
    results["cohort_hazard"] = check_cohort_hazard_rates(survival_df, output_dir)

    # Summary recommendation
    hr = results["constant_hazard"].get("hazard_ratio_y2_vs_y1", np.nan)
    print("\n" + "=" * 70)
    print("  H3 RECOMMENDATION")
    print("=" * 70)
    if np.isnan(hr):
        print("  Insufficient data to evaluate constant hazard assumption.")
    elif abs(hr - 1.0) < 0.15:
        print("  Constant hazard assumption holds reasonably well.")
        print("  → V1 retention model can use simple exponential survival.")
        print("  → retention_score = exp(-h * t) is a valid simplification.")
    else:
        print("  Constant hazard assumption is VIOLATED.")
        print("  → V1: Still usable but document the limitation.")
        print("  → V2: Upgrade to Weibull or Cox PH survival model.")
        print(f"  → The hazard {'decelerates' if hr < 1 else 'accelerates'} over time.")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H3 Constant Hazard Assumption Validation")
    parser.add_argument("--transactions", required=True)
    parser.add_argument("--churn", required=True, help="Path to churn events CSV")
    parser.add_argument("--clients", default=None)
    parser.add_argument("--output-dir", default="plots")
    args = parser.parse_args()

    run_all_h3_checks(args.transactions, args.churn, args.clients, args.output_dir)
