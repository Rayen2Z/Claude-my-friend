# =============================================================================
# UNIFIED SCORING PIPELINE — New Client Acquisition CLV
# =============================================================================
#
# Orchestrates scoring across both propositions:
#   - Proposition A: Single-stage look-alike model
#   - Proposition B: Phase 1 / Phase 2 / Transition
#
# Produces a final output DataFrame compatible with the existing CLV pipeline
# (same column structure as compute_clv_with_retention in model/retention_model.py).
#
# Prerequisites: trained models from model_a, phase1, phase2.
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# %% ---- CELL 2: Configuration ----

DISCOUNT_RATE = 0.05
RETENTION_ESTABLISHED = 0.95
GROWTH_FACTOR = 1.10


# %% ---- CELL 3: Score new clients — Proposition A ----

def score_proposition_a(df_new_clients, pnb_model, retention_model, feature_cols):
    """
    Score new clients using Proposition A (look-alike cohort model).
    Single-stage: one prediction at onboarding, valid for 12 months.

    Returns DataFrame compatible with existing CLV pipeline.
    """
    X = df_new_clients[feature_cols].copy()
    X = X.fillna(X.median())

    pnb_y1 = pnb_model.predict(X)
    p_churn = retention_model.predict_proba(X)[:, 1]
    ret = 1 - p_churn

    pnb_y2 = pnb_y1 * GROWTH_FACTOR
    pnb_y3 = pnb_y2 * GROWTH_FACTOR

    s1 = ret
    s2 = s1 * RETENTION_ESTABLISHED
    s3 = s2 * RETENTION_ESTABLISHED

    d = [(1 / (1 + DISCOUNT_RATE) ** t) for t in [1, 2, 3]]

    return pd.DataFrame({
        "client_id": df_new_clients["client_id"].values,
        "type_modele": "proposition_a",
        "confiance": "standard",
        "pnb_pred_annee1": pnb_y1,
        "pnb_pred_annee2": pnb_y2,
        "pnb_pred_annee3": pnb_y3,
        "retention_score_new": ret,
        "survie_annee1": s1,
        "survie_annee2": s2,
        "survie_annee3": s3,
        "clv_composante_annee1": pnb_y1 * s1 * d[0],
        "clv_composante_annee2": pnb_y2 * s2 * d[1],
        "clv_composante_annee3": pnb_y3 * s3 * d[2],
        "clv_total": pnb_y1 * s1 * d[0] + pnb_y2 * s2 * d[1] + pnb_y3 * s3 * d[2],
    })


# %% ---- CELL 4: Score new clients — Proposition B (auto-phase) ----

def score_proposition_b(df_new_clients, phase1_artifacts, phase2_artifacts):
    """
    Score new clients using Proposition B with automatic phase selection.

    If behavioral features are present (pnb_m1, n_txn_m1_m3, etc.),
    uses Phase 2. Otherwise falls back to Phase 1.

    Returns DataFrame with phase metadata.
    """
    from new_acq_phase1_model import score_phase1
    from new_acq_phase2_model import score_phase2, add_behavioral_features

    # Check if behavioral data is available
    behavioral_indicators = ["pnb_m1", "pnb_m2", "pnb_m3", "n_txn_m1_m3",
                              "a_domiciliation_salaire", "carte_activee"]
    has_behavioral = any(col in df_new_clients.columns for col in behavioral_indicators)

    if has_behavioral:
        print("Behavioral data detected -> using Phase 2")
        results = score_phase2(
            df_new_clients, phase2_artifacts["feature_cols"],
            phase2_artifacts["pnb_model"], phase2_artifacts["retention_model"]
        )
    else:
        print("No behavioral data -> using Phase 1")
        results = score_phase1(
            df_new_clients, phase1_artifacts["feature_cols"],
            phase1_artifacts["pnb_model"], phase1_artifacts["retention_model"]
        )

    return results


# %% ---- CELL 5: CLV computation with phase-specific survival curves ----

def compute_clv_new_client(pnb_year1, retention_score, phase="phase1",
                            discount_rate=DISCOUNT_RATE,
                            retention_established=RETENTION_ESTABLISHED,
                            growth_factor=GROWTH_FACTOR):
    """
    Compute 3-year CLV for a new client.

    The survival curve depends on the phase:
      Phase 1: S(1) = retention_score, S(2) = S(1)*0.95, S(3) = S(2)*0.95
      Phase 2: Same formula but retention_score is more accurate
      Graduated: Uses established model directly

    Returns dict with CLV components.
    """
    pnb = [pnb_year1, pnb_year1 * growth_factor, pnb_year1 * growth_factor ** 2]
    s = [retention_score,
         retention_score * retention_established,
         retention_score * retention_established ** 2]
    d = [1 / (1 + discount_rate) ** t for t in [1, 2, 3]]

    components = [pnb[i] * s[i] * d[i] for i in range(3)]

    return {
        "pnb_pred_annee1": pnb[0],
        "pnb_pred_annee2": pnb[1],
        "pnb_pred_annee3": pnb[2],
        "survie_annee1": s[0],
        "survie_annee2": s[1],
        "survie_annee3": s[2],
        "clv_composante_annee1": components[0],
        "clv_composante_annee2": components[1],
        "clv_composante_annee3": components[2],
        "clv_total": sum(components),
    }


# %% ---- CELL 6: Format output for existing pipeline compatibility ----

def format_for_existing_pipeline(new_client_clv_df):
    """
    Reformat the new-client CLV DataFrame to match the column naming
    of the established model output (from model/retention_model.py).

    Maps:
      pnb_pred_annee1 -> nbi_year1 / clv_component_year1
      retention_score_new -> retention_score
      clv_total -> clv_total
    """
    mapping = {
        "pnb_pred_annee1": "nbi_year1",
        "pnb_pred_annee2": "nbi_year2",
        "pnb_pred_annee3": "nbi_year3",
        "retention_score_new": "retention_score",
        "survie_annee1": "retention_year1",
        "survie_annee2": "retention_year2",
        "survie_annee3": "retention_year3",
        "clv_composante_annee1": "clv_component_year1",
        "clv_composante_annee2": "clv_component_year2",
        "clv_composante_annee3": "clv_component_year3",
    }

    df = new_client_clv_df.copy()
    for old_name, new_name in mapping.items():
        if old_name in df.columns:
            df[new_name] = df[old_name]

    # Add retention_3yr (for compatibility with existing model)
    if "retention_score" in df.columns:
        df["retention_3yr"] = df["retention_score"] ** 3

    return df


# %% ---- CELL 7: Summary report ----

def print_scoring_summary(results_df, title="SCORING SUMMARY"):
    """Print a summary report of the scoring results."""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")
    print(f"Total clients scored: {len(results_df)}")

    if "type_modele" in results_df.columns:
        print(f"\nBy model type:")
        for mt, count in results_df["type_modele"].value_counts().items():
            print(f"  {mt}: {count}")

    if "confiance" in results_df.columns:
        print(f"\nBy confidence level:")
        for conf, count in results_df["confiance"].value_counts().items():
            print(f"  {conf}: {count}")

    print(f"\nCLV Statistics:")
    print(f"  Mean:   {results_df['clv_total'].mean():>12,.0f} EUR")
    print(f"  Median: {results_df['clv_total'].median():>12,.0f} EUR")
    print(f"  Std:    {results_df['clv_total'].std():>12,.0f} EUR")
    print(f"  Min:    {results_df['clv_total'].min():>12,.0f} EUR")
    print(f"  Max:    {results_df['clv_total'].max():>12,.0f} EUR")
    print(f"  Total:  {results_df['clv_total'].sum():>15,.0f} EUR")

    if "retention_score_new" in results_df.columns:
        print(f"\nRetention Statistics:")
        print(f"  Mean:   {results_df['retention_score_new'].mean():.3f}")
        print(f"  Median: {results_df['retention_score_new'].median():.3f}")

    if "risque_depart_precoce" in results_df.columns:
        n_risk = results_df["risque_depart_precoce"].sum()
        print(f"\nEarly churn risk: {n_risk} clients ({n_risk/len(results_df)*100:.1f}%)")

    if "a_domiciliation_salaire" in results_df.columns:
        domiciled = results_df["a_domiciliation_salaire"].sum()
        if not np.isnan(domiciled):
            print(f"Salary domiciliation: {int(domiciled)} clients ({domiciled/len(results_df)*100:.1f}%)")


# %% ---- CELL 8: Distribution comparison (Prop A vs Prop B) ----

def plot_comparison(results_a, results_b):
    """
    Compare CLV distributions between Proposition A and Proposition B.
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # CLV distribution
    axes[0].hist(results_a["clv_total"], bins=50, alpha=0.5, label="Prop A", color="blue")
    axes[0].hist(results_b["clv_total"], bins=50, alpha=0.5, label="Prop B", color="red")
    axes[0].set_xlabel("CLV 3 ans (EUR)")
    axes[0].set_ylabel("Nombre de clients")
    axes[0].set_title("Distribution CLV")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    # Retention distribution
    axes[1].hist(results_a["retention_score_new"], bins=50, alpha=0.5, label="Prop A", color="blue")
    axes[1].hist(results_b["retention_score_new"], bins=50, alpha=0.5, label="Prop B", color="red")
    axes[1].set_xlabel("Score de retention")
    axes[1].set_ylabel("Nombre de clients")
    axes[1].set_title("Distribution retention")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    # PNB predicted
    axes[2].hist(results_a["pnb_pred_annee1"], bins=50, alpha=0.5, label="Prop A", color="blue")
    axes[2].hist(results_b["pnb_pred_annee1"], bins=50, alpha=0.5, label="Prop B", color="red")
    axes[2].set_xlabel("PNB predit annee 1 (EUR)")
    axes[2].set_ylabel("Nombre de clients")
    axes[2].set_title("Distribution PNB predit")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    plt.tight_layout()
    plt.show()


# %% ---- CELL 9: Run scoring demonstration ----

# This cell demonstrates scoring with whatever data is available.
# In production, replace with actual new client data.

print("=" * 60)
print("UNIFIED SCORING PIPELINE")
print("=" * 60)

# If Proposition A artifacts are available:
try:
    results_a = score_proposition_a(
        df_training, pnb_model, retention_model, feature_cols
    )
    print_scoring_summary(results_a, "PROPOSITION A RESULTS")
except NameError:
    print("Proposition A models not loaded. Run new_acq_model_a.py first.")

# If Proposition B artifacts are available:
try:
    results_b = score_proposition_b(df_training, phase1_artifacts, phase2_artifacts)
    print_scoring_summary(results_b, "PROPOSITION B RESULTS")
except NameError:
    print("Proposition B models not loaded. Run phase1 and phase2 models first.")

# Compare if both available
try:
    if "results_a" in dir() and "results_b" in dir():
        plot_comparison(results_a, results_b)
except Exception:
    pass
