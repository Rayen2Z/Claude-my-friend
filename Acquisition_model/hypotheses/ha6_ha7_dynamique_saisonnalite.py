# =============================================================================
# HA6 + HA7 — Dynamique Temporelle du PNB et Saisonnalite
# =============================================================================
#
# HA6 : La trajectoire du PNB mensuel pendant la fenetre d'observation
#        (croissante, stable, decroissante) apporte-t-elle un signal au-dela
#        du niveau cumule ?
#        NOTE : la pente est estimee sur 4 a 6 points selon n_mois_observation,
#        ce qui affecte la fiabilite.
#
# HA7 : Le trimestre d'acquisition influence-t-il le PNB ?
#        ATTENTION : comparer le PNB brut melange le signal saisonnier et
#        l'artefact de duree (n_mois_nbi varie de 10 a 12). Toujours utiliser
#        pnb_mensuel_moyen pour les comparaisons inter-trimestres.
#
# Prerequis : executer data_preparation.ipynb -> df_acquisitions.pkl
# =============================================================================


# %% ---- CELL 0: Charger le DataFrame ----

import pickle
df = pickle.load(open("../df_acquisitions.pkl", "rb"))
print(f"DataFrame charge : {df.shape[0]:,} lignes, {df.shape[1]} colonnes")


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.linear_model import LinearRegression


# %% ---- CELL 2: Classifier les trajectoires PNB ----

print("=" * 60)
print("HA6 — PROFILS DE TRAJECTOIRE PNB")
print("=" * 60)

pnb_monthly = [c for c in df.columns if c.startswith("pnb_m") and c[4:].isdigit()]
pnb_monthly = sorted(pnb_monthly, key=lambda x: int(x.split("_m")[1]))

if len(pnb_monthly) >= 3:
    # Use available months (up to 6)
    months_to_use = pnb_monthly[:min(6, len(pnb_monthly))]
    n_months = len(months_to_use)

    # Compute trend (slope of linear regression over monthly PNB)
    def compute_slope(row):
        vals = [row[c] for c in months_to_use if pd.notna(row[c])]
        if len(vals) < 2:
            return 0
        x = np.arange(len(vals)).reshape(-1, 1)
        y = np.array(vals)
        lr = LinearRegression().fit(x, y)
        return lr.coef_[0]

    df["obs_slope"] = df.apply(compute_slope, axis=1)

    # Volatility (std of monthly PNB)
    df["obs_volatility"] = df[months_to_use].std(axis=1)

    # Number of active months (PNB > 0)
    df["obs_active_months"] = (df[months_to_use] > 0).sum(axis=1)

    # Classify trajectory profiles
    def classify_trajectory(row):
        slope = row["obs_slope"]
        n_active = row["obs_active_months"]
        if n_active <= 1:
            return "dormant"
        elif slope > 50:
            return "croissant"
        elif slope < -50:
            return "decroissant"
        else:
            return "stable"

    df["profil_trajectoire"] = df.apply(classify_trajectory, axis=1)

    # Stats per profile
    traj_stats = df.groupby("profil_trajectoire").agg(
        n_clients=("client_id", "count"),
        pnb_moyen_12m=("pnb_total", "mean"),
        pnb_median_12m=("pnb_total", "median"),
        obs_slope_moy=("obs_slope", "mean"),
    ).round(0)

    print("\nPNB 12 mois par profil de trajectoire :\n")
    print(traj_stats.to_string())

    # Kruskal-Wallis between trajectory profiles
    profiles = df["profil_trajectoire"].unique()
    groups = [df[df["profil_trajectoire"] == p]["pnb_total"].dropna() for p in profiles]
    groups = [g for g in groups if len(g) > 5]
    if len(groups) >= 2:
        h_stat, h_p = stats.kruskal(*groups)
        print(f"\nKruskal-Wallis : H={h_stat:.2f}, p={h_p:.6f}")
        if h_p < 0.05:
            print("-> HA6 VALIDEE : la trajectoire apporte un signal significatif")
        else:
            print("-> HA6 NON VALIDEE")

    # Plot average trajectory per profile
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for profil in sorted(df["profil_trajectoire"].unique()):
        subset = df[df["profil_trajectoire"] == profil]
        avg_monthly = subset[months_to_use].mean()
        axes[0].plot(range(1, len(months_to_use) + 1), avg_monthly,
                     "o-", label=f"{profil} (n={len(subset)})", lw=2)

    axes[0].set_xlabel("Mois depuis acquisition")
    axes[0].set_ylabel("PNB mensuel moyen (EUR)")
    axes[0].set_title("Trajectoire PNB moyenne par profil")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    # Bar chart PNB 12m by profile
    traj_means = df.groupby("profil_trajectoire")["pnb_total"].mean().sort_values(ascending=True)
    colors = {"dormant": "#e74c3c", "decroissant": "#f39c12",
              "stable": "#3498db", "croissant": "#2ecc71"}
    bar_colors = [colors.get(p, "#95a5a6") for p in traj_means.index]
    traj_means.plot(kind="barh", ax=axes[1], color=bar_colors, edgecolor="white")
    axes[1].set_xlabel("PNB moyen 12 mois (EUR)")
    axes[1].set_title("PNB 12 mois par profil de trajectoire")
    axes[1].grid(axis="x", alpha=0.3)

    plt.tight_layout()
    plt.show()

else:
    print("Pas assez de colonnes PNB mensuelles pour analyser les trajectoires.")


# %% ---- CELL 3: Slow starters vs early peaks ----

print("\n" + "=" * 60)
print("HA6.2 — SLOW STARTERS vs EARLY PEAKS")
print("=" * 60)

if len(pnb_monthly) >= 3:
    # Slow starter: PNB m1 < median AND PNB m3 > median
    median_m1 = df[pnb_monthly[0]].median()
    median_m3 = df[pnb_monthly[2]].median() if len(pnb_monthly) >= 3 else 0

    df["is_slow_starter"] = (
        (df[pnb_monthly[0]] < median_m1) &
        (df[pnb_monthly[2]] > median_m3)
    ).astype(int)

    df["is_early_peak"] = (
        (df[pnb_monthly[0]] > df[pnb_monthly[0]].quantile(0.75)) &
        (df["obs_slope"] < -20)
    ).astype(int)

    n_slow = df["is_slow_starter"].sum()
    n_peak = df["is_early_peak"].sum()
    n_total = len(df)

    print(f"Slow starters :   {n_slow:,} ({n_slow/n_total*100:.1f}%)")
    print(f"  PNB 12m moyen : {df[df['is_slow_starter']==1]['pnb_total'].mean():,.0f} EUR")

    print(f"\nEarly peaks :     {n_peak:,} ({n_peak/n_total*100:.1f}%)")
    print(f"  PNB 12m moyen : {df[df['is_early_peak']==1]['pnb_total'].mean():,.0f} EUR")

    print(f"\nAutres :          {n_total - n_slow - n_peak:,}")
    others_mask = (df["is_slow_starter"] == 0) & (df["is_early_peak"] == 0)
    print(f"  PNB 12m moyen : {df[others_mask]['pnb_total'].mean():,.0f} EUR")

    print("\n-> Les slow starters rattrapent-ils leur retard sur 12 mois ?")
    print("   Si oui, le modele ne doit pas penaliser un PNB faible au mois 1.")


# %% ---- CELL 4: Valeur ajoutee de la tendance vs cumul seul ----

print("\n" + "=" * 60)
print("HA6.3 — TENDANCE vs CUMUL : GAIN PREDICTIF")
print("=" * 60)

from sklearn.metrics import r2_score

if "pnb_cumul_obs" in df.columns and "obs_slope" in df.columns:
    mask = df[["pnb_cumul_obs", "obs_slope", "pnb_total"]].notna().all(axis=1)

    # Model 1: cumul seul
    X1 = df.loc[mask, ["pnb_cumul_obs"]].values
    y = df.loc[mask, "pnb_total"].values
    lr1 = LinearRegression().fit(X1, y)
    r2_cumul = r2_score(y, lr1.predict(X1))

    # Model 2: cumul + tendance + volatilite
    feat = ["pnb_cumul_obs", "obs_slope", "obs_volatility", "obs_active_months"]
    feat = [f for f in feat if f in df.columns]
    X2 = df.loc[mask, feat].values
    lr2 = LinearRegression().fit(X2, y)
    r2_combined = r2_score(y, lr2.predict(X2))

    print(f"R2 (cumul seul) :               {r2_cumul:.4f}")
    print(f"R2 (cumul + tendance + vol) :    {r2_combined:.4f}")
    print(f"Gain :                           {(r2_combined - r2_cumul):.4f} (+{(r2_combined-r2_cumul)/r2_cumul*100:.1f}%)")

    if r2_combined - r2_cumul > 0.02:
        print("-> La tendance apporte un gain significatif. La garder comme feature.")
    else:
        print("-> La tendance apporte un gain marginal. Le cumul suffit peut-etre.")


# %% ---- CELL 5: Saisonnalite — PNB par trimestre d'acquisition ----

print("\n" + "=" * 60)
print("HA7 — SAISONNALITE D'ACQUISITION")
print("=" * 60)

# trimestre_acquisition et annee_acquisition deja derives dans data_preparation
if "trimestre_acquisition" not in df.columns:
    print("Colonne trimestre_acquisition non trouvee. Executer data_preparation.ipynb.")

if "trimestre_acquisition" in df.columns:
    # PNB brut (reference)
    q_stats = df.groupby("trimestre_acquisition")["pnb_total"].agg(
        ["count", "mean", "median", "std"]
    ).round(0)
    print("\nPNB total (brut) par trimestre d'acquisition :\n")
    print(q_stats.to_string())

    # PNB mensuel moyen (controle pour n_mois_nbi)
    if "pnb_mensuel_moyen" in df.columns:
        q_stats_norm = df.groupby("trimestre_acquisition")["pnb_mensuel_moyen"].agg(
            ["count", "mean", "median", "std"]
        ).round(0)
        print("\nPNB mensuel moyen (normalise par n_mois_nbi) par trimestre :\n")
        print(q_stats_norm.to_string())

        # Distribution de n_mois_nbi par trimestre (pour montrer le biais potentiel)
        if "n_mois_nbi" in df.columns:
            nbi_by_q = df.groupby("trimestre_acquisition")["n_mois_nbi"].mean().round(2)
            print(f"\nn_mois_nbi moyen par trimestre : {nbi_by_q.to_dict()}")

    # Kruskal-Wallis sur PNB mensuel moyen (plus fiable que PNB brut)
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    target_col = "pnb_mensuel_moyen" if "pnb_mensuel_moyen" in df.columns else "pnb_total"
    q_groups = [df[df["trimestre_acquisition"] == q][target_col].dropna()
                for q in quarters if q in df["trimestre_acquisition"].values]
    if len(q_groups) >= 2:
        h_stat, h_p = stats.kruskal(*q_groups)
        print(f"\nKruskal-Wallis (sur {target_col}) : H={h_stat:.2f}, p={h_p:.6f}")
        if h_p < 0.05:
            print("-> HA7 VALIDEE : la saisonnalite impacte significativement le PNB")
        else:
            print("-> HA7 NON VALIDEE : pas d'effet saisonnier significatif")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    plot_col = "pnb_mensuel_moyen" if "pnb_mensuel_moyen" in df.columns else "pnb_total"
    q_means = df.groupby("trimestre_acquisition")[plot_col].mean()
    q_means.reindex(["Q1", "Q2", "Q3", "Q4"]).plot(kind="bar", ax=axes[0],
        color=["#3498db", "#2ecc71", "#f39c12", "#e74c3c"], edgecolor="white")
    axes[0].set_ylabel("PNB mensuel moyen (EUR)")
    axes[0].set_title("PNB mensuel moyen par trimestre d'acquisition")
    axes[0].grid(axis="y", alpha=0.3)
    plt.sca(axes[0])
    plt.xticks(rotation=0)

    # By year and quarter
    if "annee_acquisition" in df.columns:
        pivot_yq = df.pivot_table(
            values=plot_col, index="trimestre_acquisition",
            columns="annee_acquisition", aggfunc="mean"
        ).round(0)
        pivot_yq.reindex(["Q1", "Q2", "Q3", "Q4"]).plot(kind="bar", ax=axes[1], edgecolor="white")
        axes[1].set_ylabel("PNB mensuel moyen (EUR)")
        axes[1].set_title("PNB mensuel moyen par trimestre et annee")
        axes[1].legend(title="Annee")
        axes[1].grid(axis="y", alpha=0.3)
        plt.sca(axes[1])
        plt.xticks(rotation=0)

    plt.tight_layout()
    plt.show()


# %% ---- CELL 6: Saisonnalite stable dans le temps ? ----

print("\n" + "=" * 60)
print("HA7.2 — STABILITE DE LA SAISONNALITE")
print("=" * 60)

if "annee_acquisition" in df.columns and "trimestre_acquisition" in df.columns:
    years = sorted(df["annee_acquisition"].unique())
    for year in years:
        yr_data = df[df["annee_acquisition"] == year]
        q_means_yr = yr_data.groupby("trimestre_acquisition")["pnb_total"].mean()
        best_q = q_means_yr.idxmax() if len(q_means_yr) > 0 else "?"
        worst_q = q_means_yr.idxmin() if len(q_means_yr) > 0 else "?"
        print(f"  {year}: meilleur={best_q}, plus faible={worst_q}")

    print("\n  -> Si le meilleur/pire trimestre est stable, la saisonnalite est fiable.")
    print("  -> Si elle varie, c'est un effet aleatoire et non structurel.")


# %% ---- CELL 7: Volume d'acquisitions par trimestre ----

print("\n" + "=" * 60)
print("HA7.3 — VOLUME D'ACQUISITIONS PAR TRIMESTRE")
print("=" * 60)

if "trimestre_acquisition" in df.columns and "annee_acquisition" in df.columns:
    vol_pivot = df.pivot_table(
        values="client_id", index="trimestre_acquisition",
        columns="annee_acquisition", aggfunc="count"
    ).reindex(["Q1", "Q2", "Q3", "Q4"])

    print("Nombre de nouveaux clients par trimestre :\n")
    print(vol_pivot.to_string())

    print("\n  -> Un trimestre avec beaucoup plus d'acquisitions peut avoir")
    print("     un PNB moyen different si les campagnes ciblent des profils differents.")


# %% ---- CELL 8: Resume ----

print("\n" + "=" * 60)
print("HA6 + HA7 — RESUME")
print("=" * 60)
print("""
HA6 (Dynamique temporelle) :
  Kruskal-Wallis trajectoires : p = ____
  Gain R2 tendance vs cumul :   +____
  Slow starters (% du total) :  ____%
  Conclusion : [VALIDEE / NON VALIDEE]

HA7 (Saisonnalite) :
  Kruskal-Wallis trimestres : p = ____
  Meilleur trimestre :        ____
  Plus faible trimestre :     ____
  Stable entre les annees :   [OUI / NON]
  Conclusion : [VALIDEE / NON VALIDEE]
""")
