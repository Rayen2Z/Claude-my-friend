# =============================================================================
# PROPOSITION B — Transition & Blending Logic
# =============================================================================
#
# Manages the lifecycle of a new client through three model phases:
#   Phase 1 (Day 0 - Month 3):  Declarative only
#   Phase 2 (Month 3 - Month 12): Declarative + early behavioral
#   Graduated (Month 12+):        Established CLV model
#
# Includes blending during the Month 10-14 transition window.
#
# Prerequisites:
#   - new_acq_phase1_model.py (phase1_artifacts)
#   - new_acq_phase2_model.py (phase2_artifacts)
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np


# %% ---- CELL 2: Configuration ----

# Transition timeline (months since signup)
PHASE1_END = 3          # Phase 1 ends at month 3
PHASE2_START = 3        # Phase 2 starts at month 3
BLEND_START = 10        # Start blending with established model
BLEND_END = 14          # Fully graduated to established model
MIN_QUARTERS_ACTIVE = 2  # Minimum active quarters for graduation


# %% ---- CELL 3: Determine model phase per client ----

def determine_phase(months_since_signup, quarters_active=None):
    """
    Determine which model phase applies to a client.

    Returns: 'phase1', 'phase2', 'blending', or 'graduated'
    """
    if months_since_signup < PHASE1_END:
        return "phase1"
    elif months_since_signup < BLEND_START:
        return "phase2"
    elif months_since_signup < BLEND_END:
        # Check graduation criteria
        if quarters_active is not None and quarters_active >= MIN_QUARTERS_ACTIVE:
            return "blending"
        else:
            return "phase2"  # stay on Phase 2 if not enough data for established
    else:
        if quarters_active is not None and quarters_active >= MIN_QUARTERS_ACTIVE:
            return "graduated"
        else:
            return "phase2"  # still not enough data


def assign_phases(df):
    """
    Assign model phase to each client based on their tenure.
    Expects columns: months_since_signup, quarters_active (optional).
    """
    df = df.copy()

    if "months_since_signup" not in df.columns:
        print("WARNING: 'months_since_signup' not found. Defaulting to Phase 1.")
        df["model_phase"] = "phase1"
        return df

    qa = df.get("quarters_active", None)
    df["model_phase"] = [
        determine_phase(m, q)
        for m, q in zip(
            df["months_since_signup"],
            qa if qa is not None else [None] * len(df)
        )
    ]

    # Summary
    phase_counts = df["model_phase"].value_counts()
    print("Client phase distribution:")
    for phase, count in phase_counts.items():
        print(f"  {phase}: {count} ({count/len(df)*100:.1f}%)")

    return df


# %% ---- CELL 4: Blending function ----

def compute_blend_weight(months_since_signup):
    """
    Compute the blending weight alpha for the new-client model.

    alpha = 1.0 at month 10 (100% new model)
    alpha = 0.0 at month 14 (100% established model)
    Linear interpolation between.

    Returns: alpha (weight for new model), 1-alpha (weight for established)
    """
    if months_since_signup <= BLEND_START:
        return 1.0  # fully new model
    elif months_since_signup >= BLEND_END:
        return 0.0  # fully established
    else:
        return 1.0 - (months_since_signup - BLEND_START) / (BLEND_END - BLEND_START)


def blend_clv(clv_new, clv_established, months_since_signup):
    """
    Blend CLV predictions from new-client and established models.
    """
    alpha = compute_blend_weight(months_since_signup)
    return alpha * clv_new + (1 - alpha) * clv_established


# %% ---- CELL 5: Unified scoring pipeline ----

def score_unified(df_clients, phase1_artifacts, phase2_artifacts,
                  established_model=None, established_features=None):
    """
    Score a batch of clients using the appropriate model phase.

    Parameters:
      df_clients: DataFrame with client data + months_since_signup
      phase1_artifacts: dict with pnb_model, retention_model, feature_cols
      phase2_artifacts: dict with pnb_model, retention_model, feature_cols
      established_model: optional, the existing retention model for graduated clients
      established_features: optional, feature columns for established model

    Returns: Unified DataFrame with CLV predictions.
    """
    from new_acq_phase1_model import score_phase1
    from new_acq_phase2_model import score_phase2

    df = assign_phases(df_clients)
    results = []

    # --- Phase 1 clients ---
    p1_mask = df["model_phase"] == "phase1"
    if p1_mask.any():
        p1_results = score_phase1(
            df[p1_mask], phase1_artifacts["feature_cols"],
            phase1_artifacts["pnb_model"], phase1_artifacts["retention_model"]
        )
        results.append(p1_results)

    # --- Phase 2 clients ---
    p2_mask = df["model_phase"] == "phase2"
    if p2_mask.any():
        p2_results = score_phase2(
            df[p2_mask], phase2_artifacts["feature_cols"],
            phase2_artifacts["pnb_model"], phase2_artifacts["retention_model"]
        )
        results.append(p2_results)

    # --- Blending clients (both models, then combine) ---
    blend_mask = df["model_phase"] == "blending"
    if blend_mask.any():
        p2_blend = score_phase2(
            df[blend_mask], phase2_artifacts["feature_cols"],
            phase2_artifacts["pnb_model"], phase2_artifacts["retention_model"]
        )

        if established_model is not None and established_features is not None:
            # Score with established model
            X_est = df[blend_mask][established_features].copy().fillna(0)
            est_retention = 1 - established_model.predict_proba(X_est)[:, 1]

            # Blend CLV
            for idx, row_idx in enumerate(p2_blend.index):
                months = df[blend_mask].iloc[idx].get("months_since_signup", 12)
                alpha = compute_blend_weight(months)
                p2_blend.loc[row_idx, "clv_total"] = (
                    alpha * p2_blend.loc[row_idx, "clv_total"]
                    + (1 - alpha) * est_retention[idx] * p2_blend.loc[row_idx, "pnb_pred_annee1"] * 2.5
                )
                p2_blend.loc[row_idx, "confiance"] = "moyenne-elevee"
                p2_blend.loc[row_idx, "type_modele"] = "nouvelle_acq_blended"

        results.append(p2_blend)

    # --- Graduated clients ---
    grad_mask = df["model_phase"] == "graduated"
    if grad_mask.any():
        if established_model is not None and established_features is not None:
            X_est = df[grad_mask][established_features].copy().fillna(0)
            est_retention = 1 - established_model.predict_proba(X_est)[:, 1]

            grad_results = pd.DataFrame({
                "client_id": df[grad_mask]["client_id"].values,
                "phase_modele": "graduated",
                "confiance": "elevee",
                "retention_score_new": est_retention,
                "type_modele": "modele_etabli",
            })
            results.append(grad_results)
        else:
            # Fallback: keep Phase 2 prediction
            p2_fallback = score_phase2(
                df[grad_mask], phase2_artifacts["feature_cols"],
                phase2_artifacts["pnb_model"], phase2_artifacts["retention_model"]
            )
            p2_fallback["confiance"] = "moyenne"
            p2_fallback["type_modele"] = "nouvelle_acq_phase2_extended"
            results.append(p2_fallback)

    if not results:
        return pd.DataFrame()

    unified = pd.concat(results, ignore_index=True)
    return unified


# %% ---- CELL 6: Demonstration ----

# Create a sample dataset with different tenures
print("=" * 60)
print("TRANSITION LOGIC DEMONSTRATION")
print("=" * 60)

demo_data = pd.DataFrame({
    "months_since_signup": [0, 1, 3, 6, 9, 10, 11, 12, 13, 14, 18, 24],
})

for _, row in demo_data.iterrows():
    m = row["months_since_signup"]
    phase = determine_phase(m, quarters_active=max(0, int(m / 3)))
    alpha = compute_blend_weight(m)
    print(f"  Month {m:2d}: phase={phase:12s}  alpha(new)={alpha:.2f}  alpha(est)={1-alpha:.2f}")

print("\nBlending weights over time:")
print("  Month 10: 100% new model")
print("  Month 11:  75% new / 25% established")
print("  Month 12:  50% new / 50% established")
print("  Month 13:  25% new / 75% established")
print("  Month 14:   0% new / 100% established")
