# =============================================================================
# HA13 — Impact de la longueur de la fenetre d'observation
# =============================================================================
#
# Question : Les clients avec n_mois_observation = 4 sont-ils aussi bien
# predits que ceux avec n_mois_observation = 6 ?
#
# La fenetre d'observation varie de 4 a 6 mois selon la position du client
# dans le trimestre d'acquisition. Cela affecte :
#   - La quantite de PNB mensuel disponible (4 vs 6 points)
#   - La fiabilite de la pente (obs_slope)
#   - Le nombre de produits au snapshot T+1
#
# Si la qualite diverge, envisager un traitement differencie.
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


# %% ---- CELL 2: Distribution de n_mois_observation ----

print("=" * 60)
print("HA13.1 — DISTRIBUTION DE n_mois_observation")
print("=" * 60)

if "n_mois_observation" not in df.columns:
    print("ERREUR : colonne n_mois_observation manquante. Executer data_preparation.ipynb.")
else:
    obs_counts = df["n_mois_observation"].value_counts().sort_index()
    obs_pcts = (obs_counts / len(df) * 100).round(1)
    print("\nRepartition de n_mois_observation :\n")
    for val in obs_counts.index:
        print(f"  {val} mois : {obs_counts[val]:,} clients ({obs_pcts[val]:.1f}%)")

    # Cross-tab with n_mois_nbi
    if "n_mois_nbi" in df.columns:
        ct = pd.crosstab(df["n_mois_observation"], df["n_mois_nbi"])
        print(f"\nCross-tab n_mois_observation x n_mois_nbi :\n")
        print(ct.to_string())


# %% ---- CELL 3: Profil des clients par tranche d'observation ----

print("\n" + "=" * 60)
print("HA13.2 — PROFIL PAR TRANCHE D'OBSERVATION")
print("=" * 60)

if "n_mois_observation" in df.columns:
    profile_stats = df.groupby("n_mois_observation").agg(
        n_clients=("client_id", "count"),
        pnb_total_mean=("pnb_total", "mean"),
        pnb_cumul_obs_mean=("pnb_cumul_obs", "mean"),
        n_produits_mean=("n_produits_total", "mean") if "n_produits_total" in df.columns else ("client_id", "count"),
    ).round(1)

    if "pnb_mensuel_moyen" in df.columns:
        profile_stats["pnb_mensuel_moyen"] = df.groupby("n_mois_observation")["pnb_mensuel_moyen"].mean().round(1)

    print("\nProfil moyen par tranche d'observation :\n")
    print(profile_stats.to_string())

    # Number of products by obs window
    if "n_produits_total" in df.columns:
        prod_by_obs = df.groupby("n_mois_observation")["n_produits_total"].agg(["mean", "median", "std"]).round(2)
        print(f"\nNombre de produits par n_mois_observation :\n")
        print(prod_by_obs.to_string())
        print("\n  -> Les clients avec 6 mois d'observation ont-ils plus de produits ?")
        print("     Si oui, n_produits_total est confonde avec n_mois_observation.")


# %% ---- CELL 4: Fiabilite de la pente (obs_slope) ----

print("\n" + "=" * 60)
print("HA13.3 — FIABILITE DE LA PENTE PAR TRANCHE")
print("=" * 60)

if "obs_slope" in df.columns and "n_mois_observation" in df.columns:
    slope_stats = df.groupby("n_mois_observation")["obs_slope"].agg(
        ["count", "mean", "median", "std"]
    ).round(2)
    print("\nStatistiques de obs_slope par n_mois_observation :\n")
    print(slope_stats.to_string())

    # Variance of slope (higher = less reliable)
    print("\n  Variance de la pente :")
    for obs in sorted(df["n_mois_observation"].unique()):
        var = df[df["n_mois_observation"] == obs]["obs_slope"].var()
        print(f"    n_obs={obs}: var(slope) = {var:,.1f}")

    print("\n  -> Une variance plus elevee pour n_obs=4 signifie que la pente")
    print("     est moins fiable (estimee sur moins de points).")

    # Correlation slope vs pnb_remaining by obs window
    print("\n  Correlation obs_slope vs pnb_remaining par tranche :")
    for obs in sorted(df["n_mois_observation"].unique()):
        sub = df[df["n_mois_observation"] == obs]
        mask = sub["obs_slope"].notna() & sub["pnb_remaining"].notna()
        if mask.sum() > 10:
            r, p = stats.pearsonr(sub.loc[mask, "obs_slope"], sub.loc[mask, "pnb_remaining"])
            print(f"    n_obs={obs}: r = {r:.4f} (p={p:.2e}, n={mask.sum()})")

    fig, ax = plt.subplots(figsize=(10, 6))
    df.boxplot(column="obs_slope", by="n_mois_observation", ax=ax,
               showfliers=False, patch_artist=True)
    ax.set_xlabel("n_mois_observation")
    ax.set_ylabel("obs_slope")
    ax.set_title("Distribution de la pente par fenetre d'observation")
    ax.grid(alpha=0.3)
    plt.suptitle("")
    plt.tight_layout()
    plt.show()


# %% ---- CELL 5: Erreur de prediction par tranche ----

print("\n" + "=" * 60)
print("HA13.4 — ERREUR DE PREDICTION PAR TRANCHE")
print("=" * 60)

# Build a simple model and compare error by n_mois_observation
features = []
for col in ["pnb_cumul_obs", "pnb_cumul_3m", "obs_slope", "obs_volatility",
            "obs_active_months", "n_produits_total", "n_mois_nbi", "n_mois_observation"]:
    if col in df.columns:
        features.append(col)

if features and "n_mois_observation" in df.columns:
    mask = df[features + ["pnb_total"]].notna().all(axis=1)

    if mask.sum() > 50:
        X = df.loc[mask, features].values
        y = df.loc[mask, "pnb_total"].values
        obs_vals = df.loc[mask, "n_mois_observation"].values

        lr = LinearRegression().fit(X, y)
        y_pred = lr.predict(X)
        residuals = y - y_pred

        print(f"\nRegression lineaire (toutes features, n={mask.sum():,}) :")
        print(f"  R2 global = {r2_score(y, y_pred):.4f}")
        print(f"  MAE global = {mean_absolute_error(y, y_pred):,.0f} EUR\n")

        print(f"  {'n_mois_obs':>12} {'n':>8} {'R2':>8} {'MAE':>10} {'RMSE':>10}")
        print(f"  {'-'*50}")
        for obs in sorted(df["n_mois_observation"].unique()):
            idx = obs_vals == obs
            if idx.sum() > 10:
                r2_obs = r2_score(y[idx], y_pred[idx])
                mae_obs = mean_absolute_error(y[idx], y_pred[idx])
                rmse_obs = np.sqrt(mean_squared_error(y[idx], y_pred[idx]))
                print(f"  {obs:>12} {idx.sum():>8,} {r2_obs:>8.4f} {mae_obs:>10,.0f} {rmse_obs:>10,.0f}")

        # Plot error distribution by obs window
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        for obs in sorted(df["n_mois_observation"].unique()):
            idx = obs_vals == obs
            if idx.sum() > 10:
                axes[0].hist(residuals[idx], bins=50, alpha=0.4,
                             label=f"n_obs={obs} (n={idx.sum()})", density=True)

        axes[0].set_xlabel("Residu (EUR)")
        axes[0].set_ylabel("Densite")
        axes[0].set_title("Distribution des residus par fenetre d'observation")
        axes[0].legend()
        axes[0].grid(alpha=0.3)

        # MAE bar chart
        maes = {}
        for obs in sorted(df["n_mois_observation"].unique()):
            idx = obs_vals == obs
            if idx.sum() > 10:
                maes[obs] = mean_absolute_error(y[idx], y_pred[idx])
        pd.Series(maes).plot(kind="bar", ax=axes[1], color="steelblue", edgecolor="white")
        axes[1].set_xlabel("n_mois_observation")
        axes[1].set_ylabel("MAE (EUR)")
        axes[1].set_title("MAE par fenetre d'observation")
        axes[1].grid(axis="y", alpha=0.3)
        plt.sca(axes[1])
        plt.xticks(rotation=0)

        plt.tight_layout()
        plt.show()

        # Relative performance
        if maes:
            best_obs = min(maes, key=maes.get)
            worst_obs = max(maes, key=maes.get)
            pct_gap = (maes[worst_obs] / maes[best_obs] - 1) * 100
            print(f"\n  Meilleure tranche : n_obs={best_obs} (MAE={maes[best_obs]:,.0f})")
            print(f"  Plus faible tranche : n_obs={worst_obs} (MAE={maes[worst_obs]:,.0f})")
            print(f"  Ecart relatif : {pct_gap:+.1f}%")

            if pct_gap > 20:
                print("  -> Ecart significatif : envisager un traitement differencie")
            else:
                print("  -> Ecart modere : un modele unifie est acceptable")


# %% ---- CELL 6: Volatilite par tranche ----

print("\n" + "=" * 60)
print("HA13.5 — VOLATILITE DU PNB PAR TRANCHE")
print("=" * 60)

if "obs_volatility" in df.columns and "n_mois_observation" in df.columns:
    vol_stats = df.groupby("n_mois_observation")["obs_volatility"].agg(
        ["mean", "median", "std"]
    ).round(1)
    print("\nVolatilite PNB mensuel par tranche d'observation :\n")
    print(vol_stats.to_string())

    print("\n  -> La volatilite est-elle plus faible pour n_obs=4 ?")
    print("     Si oui, c'est parce qu'il y a moins de points (moins de variation visible).")


# %% ---- CELL 7: Verdict ----

print("\n" + "=" * 60)
print("HA13 — VERDICT")
print("=" * 60)
print("""
A remplir :
  MAE (n_obs=4) :    ____ EUR
  MAE (n_obs=5) :    ____ EUR
  MAE (n_obs=6) :    ____ EUR
  Ecart relatif :    ____%
  Variance slope (4 vs 6) : ____ vs ____

  HA13 VALIDEE (qualite diverge significativement) si :
    - Ecart MAE > 20% entre n_obs=4 et n_obs=6
    - Variance de la pente nettement superieure pour n_obs=4
    - R2 par tranche significativement different

  Si VALIDEE (qualite diverge) :
    -> Options : sous-modeles, features adaptees, ponderation
    -> La pente est moins fiable a 4 mois : reduire son poids ou la remplacer

  Si NON VALIDEE (qualite stable) :
    -> Un modele unifie avec n_mois_observation comme feature suffit
    -> Les features restent fiables quelle que soit la fenetre

  Conclusion : [QUALITE DIVERGE / QUALITE STABLE]
""")
