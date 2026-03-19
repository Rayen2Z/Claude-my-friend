"""
===============================================================================
  H3 — CONSTANT HAZARD ASSUMPTION (Priority: Medium)
===============================================================================
  Validates whether the churn hazard rate is approximately constant over time
  (exponential survival assumption) or if it varies (suggesting a need for a
  more complex survival model like Weibull or Cox PH).

  Works with Stock-based data (primary) or transaction-based data (fallback).

  Checks:
  1. Compute year-over-year churn rates — is the rate constant?
  2. Plot empirical survival curve (Kaplan-Meier)
  3. Compute implied constant hazard h = -ln(1 - P_churn)
  4. Overlay theoretical exponential curve exp(-h*t)
  5. Year-1 vs year-2 conditional churn rate comparison
  6. If curves diverge → flag survival model upgrade as V2 priority
===============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional


# =============================================================================
# Kaplan-Meier estimator
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
    order = np.argsort(duration)
    duration = duration[order]
    event = event[order]

    unique_times = np.unique(duration[event == 1])
    survival = []
    times = []
    s = 1.0

    for t in unique_times:
        at_risk = np.sum(duration >= t)
        events_at_t = np.sum((duration == t) & (event == 1))
        if at_risk > 0:
            s *= (1 - events_at_t / at_risk)
        times.append(t)
        survival.append(s)

    return np.array(times), np.array(survival)


# =============================================================================
# Build survival data from Stock-based churn dataset
# =============================================================================

def build_survival_from_stocks(
    churn_df: pd.DataFrame,
    clients_df: Optional[pd.DataFrame] = None,
    opening_col: str = "account_opening_date",
) -> pd.DataFrame:
    """
    Build survival data from the Stock-based churn dataset.

    For each client, we track how many years they appear before churning.
    The "duration" is in years (since we have annual snapshots).

    Parameters
    ----------
    churn_df : Output of build_churn_dataset() with columns:
        client_id, year, churned, is_upstreamed
    clients_df : Optional client demographics with account_opening_date
    opening_col : Column name for account opening date

    Returns
    -------
    DataFrame: client_id, duration_years, event (1=churned, 0=censored),
               first_year, last_year
    """
    churn_col = "churned" if "churned" in churn_df.columns else "churned_next_year"

    # Exclude upstreamed clients (they are censored, not churned)
    if "is_upstreamed" in churn_df.columns:
        df = churn_df[churn_df["is_upstreamed"] == 0].copy()
    else:
        df = churn_df.copy()

    records = []
    for client_id, client_data in df.groupby("client_id"):
        client_data = client_data.sort_values("year")
        first_year = client_data["year"].min()
        last_year = client_data["year"].max()
        ever_churned = client_data[churn_col].max()

        if ever_churned == 1:
            # Churned: duration = years from first appearance to churn year
            churn_year = client_data[client_data[churn_col] == 1]["year"].min()
            duration = churn_year - first_year + 1  # +1 because they were present that year
            event = 1
        else:
            # Still active: censored at last observation
            duration = last_year - first_year + 1
            event = 0

        # If we have account_opening_date, use real tenure
        if clients_df is not None and opening_col in clients_df.columns:
            client_info = clients_df[clients_df["client_id"].astype(str) == str(client_id)]
            if not client_info.empty:
                open_date = pd.to_datetime(client_info[opening_col].iloc[0])
                ref_year = churn_year if ever_churned else last_year
                duration = ref_year - open_date.year

        records.append({
            "client_id": client_id,
            "first_year": first_year,
            "last_year": last_year,
            "duration_years": max(duration, 1),
            "event": event,
        })

    return pd.DataFrame(records)


# =============================================================================
# Main constant hazard validation
# =============================================================================

def validate_constant_hazard(
    survival_df: pd.DataFrame,
    output_dir: str = "plots",
    time_unit: str = "years",
) -> dict:
    """
    Core H3 validation using annual or monthly data.
    """
    Path(output_dir).mkdir(exist_ok=True)

    if "duration_years" in survival_df.columns:
        duration = survival_df["duration_years"].values
        unit_label = "years"
        period_length = 1  # 1 year
    else:
        duration = survival_df["duration_months"].values
        unit_label = "months"
        period_length = 12

    event = survival_df["event"].values

    # Kaplan-Meier estimate
    km_times, km_survival = kaplan_meier_estimator(duration, event)

    # Compute 1-period churn rate
    total_clients = len(survival_df)
    churned_period1 = survival_df[
        (survival_df["event"] == 1) & (duration <= period_length)
    ].shape[0]
    at_risk_period1 = total_clients
    p_churn_1 = churned_period1 / at_risk_period1 if at_risk_period1 > 0 else 0

    # Implied constant hazard
    if 0 < p_churn_1 < 1:
        h = -np.log(1 - p_churn_1)
    else:
        h = 0

    # Theoretical exponential survival
    t_theory = np.linspace(0, max(km_times.max() if len(km_times) > 0 else 5, 5), 200)
    s_theory = np.exp(-h * t_theory)

    # Period-2 conditional churn rate
    survived_p1 = survival_df[
        (duration > period_length) | (survival_df["event"] == 0)
    ]
    churned_p2 = survived_p1[
        (survived_p1["event"] == 1) &
        (duration[survived_p1.index] > period_length) &
        (duration[survived_p1.index] <= 2 * period_length)
    ].shape[0]
    at_risk_p2 = survived_p1[duration[survived_p1.index] > period_length].shape[0]
    p_churn_2 = churned_p2 / at_risk_p2 if at_risk_p2 > 0 else 0

    hazard_ratio = p_churn_2 / p_churn_1 if p_churn_1 > 0 else np.nan

    results = {
        "total_clients": total_clients,
        "p_churn_period1": p_churn_1,
        "p_churn_period2_conditional": p_churn_2,
        "implied_hazard": h,
        "hazard_ratio_p2_vs_p1": hazard_ratio,
    }

    print("\n" + "=" * 70)
    print("  H3 — CONSTANT HAZARD ASSUMPTION VALIDATION")
    print("=" * 70)
    print(f"\n  Total clients: {total_clients}")
    print(f"  Period-1 churn rate: {p_churn_1:.4f} ({p_churn_1:.2%})")
    print(f"  Implied constant hazard: h = {h:.4f} per {unit_label[:-1]}")
    print(f"\n  Period-2 conditional churn rate: {p_churn_2:.4f} ({p_churn_2:.2%})")
    print(f"  Hazard ratio (Period 2 / Period 1): {hazard_ratio:.3f}")

    if np.isnan(hazard_ratio):
        print("\n  ⚠ Insufficient data to compute hazard ratio.")
    elif abs(hazard_ratio - 1.0) < 0.15:
        print("\n  ✓ Hazard appears roughly constant (ratio within 15% of 1.0)")
        print("    Exponential survival assumption is reasonable for V1.")
    elif hazard_ratio < 0.85:
        print("\n  ⚠ Churn DECELERATES over time (hazard ratio < 0.85)")
        print("    Clients who survive period 1 are less likely to churn later.")
        print("    → Consider Weibull or Cox PH model for V2.")
    else:
        print("\n  ⚠ Churn ACCELERATES over time (hazard ratio > 1.15)")
        print("    Clients become MORE likely to churn as they age.")
        print("    → Consider Weibull or Cox PH model for V2.")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    ax = axes[0]
    if len(km_times) > 0:
        ax.step(km_times, km_survival, where="post", label="Empirical (Kaplan-Meier)",
                color="blue", linewidth=2)
    ax.plot(t_theory, s_theory, "--", label=f"Theoretical exp(-{h:.4f}·t)",
            color="red", linewidth=2)
    ax.set_xlabel(f"Time ({unit_label})")
    ax.set_ylabel("Survival Probability")
    ax.set_title("H3: Empirical vs Exponential Survival Curve")
    ax.legend()
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)

    ax2 = axes[1]
    if len(km_times) > 0:
        s_theory_at_km = np.exp(-h * km_times)
        deviation = km_survival - s_theory_at_km
        ax2.bar(km_times, deviation, width=0.3, color="purple", alpha=0.6)
        ax2.axhline(0, color="black", linestyle="-", linewidth=0.5)
        ax2.set_xlabel(f"Time ({unit_label})")
        ax2.set_ylabel("Deviation (Empirical - Theoretical)")
        ax2.set_title("Deviation from Constant Hazard Assumption")
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/h3_constant_hazard.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Plot saved to {output_dir}/h3_constant_hazard.png")

    return results


# =============================================================================
# RUN ALL H3 CHECKS
# =============================================================================

def run_all_h3_checks_from_stocks(
    churn_data_path: str,
    clients_path: Optional[str] = None,
    output_dir: str = "plots",
) -> dict:
    """
    Run H3 validation using Stock-based churn data.

    Parameters
    ----------
    churn_data_path : Path to merged churn CSV (from build_churn_dataset)
    clients_path : Optional client demographics CSV
    output_dir : Plot output directory
    """
    print("Loading churn data...")
    churn_df = pd.read_csv(churn_data_path)

    clients_df = None
    if clients_path:
        clients_df = pd.read_csv(clients_path)

    print("Building survival data from annual stocks...")
    survival_df = build_survival_from_stocks(churn_df, clients_df)
    print(f"  {len(survival_df)} clients, {survival_df['event'].sum()} churned, "
          f"{(survival_df['event'] == 0).sum()} censored")

    results = {}
    results["constant_hazard"] = validate_constant_hazard(survival_df, output_dir)

    # Summary
    hr = results["constant_hazard"].get("hazard_ratio_p2_vs_p1", np.nan)
    print("\n" + "=" * 70)
    print("  H3 RECOMMENDATION")
    print("=" * 70)
    if np.isnan(hr):
        print("  Insufficient data to evaluate constant hazard assumption.")
        print("  → Need more years of data for reliable survival analysis.")
    elif abs(hr - 1.0) < 0.15:
        print("  Constant hazard assumption holds reasonably well.")
        print("  → V1 retention model can use: retention_3yr = retention_score^3")
    else:
        print("  Constant hazard assumption is VIOLATED.")
        print("  → V1: Still usable but document the limitation.")
        print("  → V2: Upgrade to Weibull or Cox PH survival model.")
        print(f"  → The hazard {'decelerates' if hr < 1 else 'accelerates'} over time.")

    return results


# Keep backward compatibility for transaction-based usage
def run_all_h3_checks(
    transactions_path: str = None,
    churn_path: str = None,
    churn_data_path: str = None,
    clients_path: Optional[str] = None,
    output_dir: str = "plots",
) -> dict:
    """
    Run H3 checks. Supports both Stock-based and transaction-based data.

    For Stock-based (primary): pass churn_data_path
    For transaction-based (legacy): pass transactions_path + churn_path
    """
    if churn_data_path:
        return run_all_h3_checks_from_stocks(churn_data_path, clients_path, output_dir)

    # Legacy transaction-based path
    if not transactions_path or not churn_path:
        raise ValueError("Provide either churn_data_path (Stock-based) or "
                         "transactions_path + churn_path (transaction-based)")

    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from data_pipeline.churn_data_pipeline import load_data

    print("Loading data...")
    transactions_df = load_data(transactions_path)
    churn_df = pd.read_csv(churn_path, parse_dates=["churn_month", "last_active_month"])

    clients_df = None
    if clients_path:
        clients_df = pd.read_csv(clients_path)

    # Build survival from transactions
    all_clients = transactions_df["client_id"].unique()
    observation_end = transactions_df["transaction_date"].max()
    churn_ids = set(churn_df["client_id"].unique())

    records = []
    for cid in all_clients:
        client_txns = transactions_df[transactions_df["client_id"] == cid]
        start = client_txns["transaction_date"].min()

        if cid in churn_ids:
            end = pd.to_datetime(churn_df[churn_df["client_id"] == cid]["churn_month"].iloc[0])
            event = 1
        else:
            end = observation_end
            event = 0

        records.append({
            "client_id": cid,
            "duration_months": max((end - start).days / 30.44, 0),
            "event": event,
            "start_date": start,
        })

    survival_df = pd.DataFrame(records)

    results = {}
    results["constant_hazard"] = validate_constant_hazard(survival_df, output_dir, time_unit="months")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="H3 Constant Hazard Assumption Validation")
    parser.add_argument("--churn-data", default=None,
                        help="[Stock mode] Path to merged churn dataset CSV")
    parser.add_argument("--transactions", default=None,
                        help="[Legacy] Path to transactions CSV")
    parser.add_argument("--churn", default=None,
                        help="[Legacy] Path to churn events CSV")
    parser.add_argument("--clients", default=None)
    parser.add_argument("--output-dir", default="plots")
    args = parser.parse_args()

    run_all_h3_checks(
        churn_data_path=args.churn_data,
        transactions_path=args.transactions,
        churn_path=args.churn,
        clients_path=args.clients,
        output_dir=args.output_dir,
    )
