# =============================================================================
# HA12 — Definition de la cible : PNB total vs PNB restant
# =============================================================================
#
# Question : Predire pnb_total (inclut la fenetre d'observation) est-il
# meilleur ou pire que predire pnb_remaining = pnb_total - pnb_cumul_obs ?
#
# pnb_cumul_obs est mecaniquement inclus dans pnb_total, ce qui gonfle
# artificiellement les metriques. Cette analyse quantifie le plancher
# mecanique et compare les deux approches de cible.
#
# Impact : si pnb_remaining donne un R2 similaire sur les features non-PNB,
# il est preferable car il isole le vrai signal predictif.
#
# Prerequis : executer data_preparation.ipynb -> df_acquisitions.pkl
# =============================================================================


# %% ---- CELL 0: Charger le DataFrame ----

import pickle
df = pickle.load(open("df_acquisitions.pkl", "rb"))
print(f"DataFrame charge : {df.shape[0]:,} lignes, {df.shape[1]} colonnes")


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error


# %% ---- CELL 2: Quantifier le plancher mecanique ----

print("=" * 60)
print("HA12.1 — PLANCHER MECANIQUE DE CORRELATION")
print("=" * 60)

if "pnb_cumul_obs" in df.columns and "pnb_total" in df.columns and "pnb_remaining" in df.columns:
    mask = df[["pnb_cumul_obs", "pnb_total", "pnb_remaining"]].notna().all(axis=1)

    r_brut, _ = stats.pearsonr(df.loc[mask, "pnb_cumul_obs"], df.loc[mask, "pnb_total"])
    r_net, _ = stats.pearsonr(df.loc[mask, "pnb_cumul_obs"], df.loc[mask, "pnb_remaining"])

    # Theoretical mechanical floor
    var_obs = df.loc[mask, "pnb_cumul_obs"].var()
    var_total = df.loc[mask, "pnb_total"].var()
    var_remaining = df.loc[mask, "pnb_remaining"].var()

    r_mechanical = np.sqrt(var_obs / var_total) if var_total > 0 else 0

    print(f"\nCorrelation pnb_cumul_obs vs pnb_total :     r = {r_brut:.4f}")
    print(f"Correlation pnb_cumul_obs vs pnb_remaining : r = {r_net:.4f}")
    print(f"\nPlancher mecanique estime (sqrt(var_obs/var_total)) : {r_mechanical:.4f}")
    print(f"Signal reel au-dela du plancher : {r_brut - r_mechanical:+.4f}")

    print(f"\nVariances :")
    print(f"  var(pnb_cumul_obs) = {var_obs:,.0f}")
    print(f"  var(pnb_total)     = {var_total:,.0f}")
    print(f"  var(pnb_remaining) = {var_remaining:,.0f}")

    # Part of total variance explained by overlap
    overlap_pct = var_obs / var_total * 100 if var_total > 0 else 0
    print(f"  Part de variance due a l'overlap : {overlap_pct:.1f}%")

else:
    print("Colonnes manquantes. Executer data_preparation.ipynb.")


# %% ---- CELL 3: R2 comparaison — pnb_cumul_obs comme predicteur ----

print("\n" + "=" * 60)
print("HA12.2 — R2 : pnb_cumul_obs -> pnb_total vs pnb_remaining")
print("=" * 60)

if "pnb_cumul_obs" in df.columns:
    mask = df[["pnb_cumul_obs", "pnb_total", "pnb_remaining"]].notna().all(axis=1)
    X = df.loc[mask, "pnb_cumul_obs"].values.reshape(-1, 1)

    # Target 1: pnb_total
    y_total = df.loc[mask, "pnb_total"].values
    lr_total = LinearRegression().fit(X, y_total)
    r2_total = r2_score(y_total, lr_total.predict(X))
    mae_total = mean_absolute_error(y_total, lr_total.predict(X))

    # Target 2: pnb_remaining
    y_rem = df.loc[mask, "pnb_remaining"].values
    lr_rem = LinearRegression().fit(X, y_rem)
    r2_rem = r2_score(y_rem, lr_rem.predict(X))
    mae_rem = mean_absolute_error(y_rem, lr_rem.predict(X))

    print(f"\nRegression simple : pnb_cumul_obs -> cible")
    print(f"  {'Cible':<20} {'R2':>8} {'MAE (EUR)':>12}")
    print(f"  {'-'*42}")
    print(f"  {'pnb_total':<20} {r2_total:>8.4f} {mae_total:>12,.0f}")
    print(f"  {'pnb_remaining':<20} {r2_rem:>8.4f} {mae_rem:>12,.0f}")

    print(f"\n  -> Le R2 sur pnb_total ({r2_total:.4f}) inclut le plancher mecanique.")
    print(f"  -> Le R2 sur pnb_remaining ({r2_rem:.4f}) mesure le vrai signal predictif.")
    print(f"  -> Ecart : {r2_total - r2_rem:+.4f}")


# %% ---- CELL 4: R2 avec features non-PNB (equipements, segment, etc.) ----

print("\n" + "=" * 60)
print("HA12.3 — R2 AVEC FEATURES NON-PNB")
print("=" * 60)

# Build feature set without PNB columns
non_pnb_features = []
for col in df.columns:
    if col.startswith("qty_") or col in ["n_produits_total", "n_mois_nbi",
                                          "n_mois_observation", "obs_active_months"]:
        non_pnb_features.append(col)

# Add encoded segment if available
if "segment" in df.columns:
    df["segment_encoded"] = df["segment"].astype("category").cat.codes
    non_pnb_features.append("segment_encoded")

print(f"Features non-PNB utilisees : {non_pnb_features}")

if non_pnb_features:
    feat_cols = [c for c in non_pnb_features if c in df.columns]
    mask = df[feat_cols + ["pnb_total", "pnb_remaining"]].notna().all(axis=1)

    if mask.sum() > 50:
        X_np = df.loc[mask, feat_cols].values

        # Target 1: pnb_total
        y_total = df.loc[mask, "pnb_total"].values
        lr_t = LinearRegression().fit(X_np, y_total)
        r2_t = r2_score(y_total, lr_t.predict(X_np))
        mae_t = mean_absolute_error(y_total, lr_t.predict(X_np))

        # Target 2: pnb_remaining
        y_rem = df.loc[mask, "pnb_remaining"].values
        lr_r = LinearRegression().fit(X_np, y_rem)
        r2_r = r2_score(y_rem, lr_r.predict(X_np))
        mae_r = mean_absolute_error(y_rem, lr_r.predict(X_np))

        print(f"\nRegression : features non-PNB -> cible (n={mask.sum():,})")
        print(f"  {'Cible':<20} {'R2':>8} {'MAE (EUR)':>12}")
        print(f"  {'-'*42}")
        print(f"  {'pnb_total':<20} {r2_t:>8.4f} {mae_t:>12,.0f}")
        print(f"  {'pnb_remaining':<20} {r2_r:>8.4f} {mae_r:>12,.0f}")

        if abs(r2_t - r2_r) < 0.05:
            print(f"\n  -> R2 similaires : les features non-PNB predisent aussi bien les deux cibles.")
            print(f"  -> pnb_remaining est preferable (pas d'inflation par l'overlap).")
        elif r2_t > r2_r:
            print(f"\n  -> pnb_total a un R2 superieur, mais c'est potentiellement du a l'overlap.")
        else:
            print(f"\n  -> pnb_remaining a un R2 superieur — le signal est mieux isole.")
    else:
        print(f"Pas assez de donnees completes (n={mask.sum()}).")


# %% ---- CELL 5: R2 avec toutes les features (PNB + non-PNB) ----

print("\n" + "=" * 60)
print("HA12.4 — R2 AVEC TOUTES LES FEATURES")
print("=" * 60)

all_features = list(non_pnb_features)
for col in ["pnb_cumul_obs", "pnb_cumul_3m", "obs_slope", "obs_volatility"]:
    if col in df.columns:
        all_features.append(col)

feat_cols = [c for c in all_features if c in df.columns]
mask = df[feat_cols + ["pnb_total", "pnb_remaining"]].notna().all(axis=1)

if mask.sum() > 50:
    X_all = df.loc[mask, feat_cols].values

    y_total = df.loc[mask, "pnb_total"].values
    lr_t = LinearRegression().fit(X_all, y_total)
    r2_t_all = r2_score(y_total, lr_t.predict(X_all))
    mae_t_all = mean_absolute_error(y_total, lr_t.predict(X_all))

    y_rem = df.loc[mask, "pnb_remaining"].values
    lr_r = LinearRegression().fit(X_all, y_rem)
    r2_r_all = r2_score(y_rem, lr_r.predict(X_all))
    mae_r_all = mean_absolute_error(y_rem, lr_r.predict(X_all))

    print(f"\nRegression : toutes features -> cible (n={mask.sum():,})")
    print(f"  {'Cible':<20} {'R2':>8} {'MAE (EUR)':>12}")
    print(f"  {'-'*42}")
    print(f"  {'pnb_total':<20} {r2_t_all:>8.4f} {mae_t_all:>12,.0f}")
    print(f"  {'pnb_remaining':<20} {r2_r_all:>8.4f} {mae_r_all:>12,.0f}")


# %% ---- CELL 6: Analyse des residus ----

print("\n" + "=" * 60)
print("HA12.5 — ANALYSE DES RESIDUS")
print("=" * 60)

if mask.sum() > 50:
    resid_total = y_total - lr_t.predict(X_all)
    resid_rem = y_rem - lr_r.predict(X_all)

    print(f"\nResidus (toutes features) :")
    print(f"  {'Metrique':<25} {'pnb_total':>12} {'pnb_remaining':>15}")
    print(f"  {'-'*54}")
    print(f"  {'Mean':<25} {resid_total.mean():>12,.0f} {resid_rem.mean():>15,.0f}")
    print(f"  {'Std':<25} {resid_total.std():>12,.0f} {resid_rem.std():>15,.0f}")
    print(f"  {'Skewness':<25} {stats.skew(resid_total):>12.2f} {stats.skew(resid_rem):>15.2f}")
    print(f"  {'Kurtosis':<25} {stats.kurtosis(resid_total):>12.2f} {stats.kurtosis(resid_rem):>15.2f}")

    # Residual plots
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    axes[0].scatter(lr_t.predict(X_all), resid_total, alpha=0.1, s=5)
    axes[0].axhline(0, color="red", ls="--", alpha=0.5)
    axes[0].set_xlabel("Prediction (EUR)")
    axes[0].set_ylabel("Residu (EUR)")
    axes[0].set_title("Residus — cible = pnb_total")
    axes[0].grid(alpha=0.3)

    axes[1].scatter(lr_r.predict(X_all), resid_rem, alpha=0.1, s=5, color="coral")
    axes[1].axhline(0, color="red", ls="--", alpha=0.5)
    axes[1].set_xlabel("Prediction (EUR)")
    axes[1].set_ylabel("Residu (EUR)")
    axes[1].set_title("Residus — cible = pnb_remaining")
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.show()


# %% ---- CELL 7: Synthese comparative ----

print("\n" + "=" * 60)
print("HA12.6 — SYNTHESE COMPARATIVE")
print("=" * 60)

print("""
Tableau recapitulatif :

  Modele                    | Cible          | R2    | MAE
  ========================= | ============== | ===== | ========
  pnb_obs seul              | pnb_total      | ____  | ____
  pnb_obs seul              | pnb_remaining  | ____  | ____
  Features non-PNB          | pnb_total      | ____  | ____
  Features non-PNB          | pnb_remaining  | ____  | ____
  Toutes features           | pnb_total      | ____  | ____
  Toutes features           | pnb_remaining  | ____  | ____

(A remplir apres execution)
""")


# %% ---- CELL 8: Verdict ----

print("\n" + "=" * 60)
print("HA12 — VERDICT")
print("=" * 60)
print("""
A remplir :
  Plancher mecanique :              ____
  R2(obs -> total) :                ____
  R2(obs -> remaining) :            ____
  R2(all features -> total) :       ____
  R2(all features -> remaining) :   ____

  RECOMMANDATION :
    Si R2(remaining) est proche de R2(total) avec toutes les features :
      -> Utiliser pnb_remaining comme cible (plus propre, pas d'inflation)
      -> En production, PNB predit = pnb_remaining_predit + pnb_cumul_obs

    Si R2(total) est nettement superieur :
      -> Garder pnb_total comme cible
      -> Le modele exploite legitimement la continuite entre obs et total

  Conclusion : [pnb_total / pnb_remaining / A TESTER PLUS EN DETAIL]
""")
