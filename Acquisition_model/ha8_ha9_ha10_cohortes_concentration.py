# =============================================================================
# HA8 + HA9 + HA10 — Stabilite des Cohortes, Comparaison, Concentration
# =============================================================================
#
# HA8 : Les cohortes sont-elles stables dans le temps (pas de derive) ?
# HA9 : Le PNB des nouveaux clients est-il different des clients etablis ?
# HA10 : Le PNB suit-il une loi de Pareto (concentration) ?
#
# Prerequis : executer data_preparation.ipynb -> df_acquisitions.pkl
#   Pour HA9 : df_etabli (DataFrame des clients etablis avec nbi_annual)
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


# %% ---- CELL 2: HA8 — Stabilite des cohortes ----

print("=" * 60)
print("HA8 — STABILITE DES COHORTES DANS LE TEMPS")
print("=" * 60)

# annee_acquisition deja derive dans data_preparation
if "annee_acquisition" in df.columns:
    # PNB by cohort year
    cohort_stats = df.groupby("annee_acquisition")["pnb_total"].agg(
        ["count", "mean", "median", "std"]
    ).round(0)
    print("\nPNB 12 mois par cohorte annuelle :\n")
    print(cohort_stats.to_string())

    # Year-over-year change
    years = sorted(df["annee_acquisition"].unique())
    if len(years) >= 2:
        print("\nEvolution annuelle :")
        for i in range(1, len(years)):
            prev_mean = cohort_stats.loc[years[i-1], "mean"]
            curr_mean = cohort_stats.loc[years[i], "mean"]
            change = (curr_mean - prev_mean) / prev_mean * 100
            print(f"  {years[i-1]} -> {years[i]}: {change:+.1f}% (PNB moyen)")

    # KS test between consecutive cohorts
    print("\nTests de Kolmogorov-Smirnov (stabilite des distributions) :")
    for i in range(1, len(years)):
        g1 = df[df["annee_acquisition"] == years[i-1]]["pnb_total"].dropna()
        g2 = df[df["annee_acquisition"] == years[i]]["pnb_total"].dropna()
        if len(g1) > 10 and len(g2) > 10:
            ks_stat, ks_p = stats.ks_2samp(g1, g2)
            verdict = "DIFFERENTES" if ks_p < 0.05 else "SIMILAIRES"
            print(f"  {years[i-1]} vs {years[i]}: KS={ks_stat:.3f}, p={ks_p:.4f} -> {verdict}")

    # Distribution overlay plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for year in years:
        subset = df[df["annee_acquisition"] == year]["pnb_total"].dropna()
        if len(subset) > 0:
            axes[0].hist(subset.clip(-2000, 15000), bins=50, alpha=0.4, label=str(year))

    axes[0].set_xlabel("PNB 12 mois (EUR)")
    axes[0].set_ylabel("Frequence")
    axes[0].set_title("Distribution PNB par cohorte annuelle")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    # Box plot by cohort
    df.boxplot(column="pnb_total", by="annee_acquisition", ax=axes[1],
               showfliers=False, patch_artist=True)
    axes[1].set_xlabel("Annee d'acquisition")
    axes[1].set_ylabel("PNB 12 mois (EUR)")
    axes[1].set_title("PNB par cohorte")
    axes[1].grid(alpha=0.3)

    plt.suptitle("")
    plt.tight_layout()
    plt.show()

    # Segment mix evolution
    print("\nComposition des segments par cohorte :")
    if "segment" in df.columns:
        seg_mix = pd.crosstab(df["annee_acquisition"], df["segment"], normalize="index") * 100
        print(seg_mix.round(1).to_string())

        if seg_mix.std().max() > 5:
            print("\n  -> Le mix de segments a evolue (std > 5%). Cela peut expliquer")
            print("     des changements de PNB moyen entre cohortes.")
        else:
            print("\n  -> Le mix de segments est stable entre les cohortes.")


# %% ---- CELL 3: HA8.2 — Derive de la profession ----

print("\n" + "=" * 60)
print("HA8.2 — EVOLUTION DU MIX DE PROFESSIONS")
print("=" * 60)

if "profession" in df.columns and "annee_acquisition" in df.columns:
    prof_mix = pd.crosstab(df["annee_acquisition"], df["profession"], normalize="index") * 100
    print(prof_mix.round(1).to_string())


# %% ---- CELL 4: HA9 — Nouveaux clients vs clients etablis ----

print("\n" + "=" * 60)
print("HA9 — NOUVEAUX CLIENTS vs CLIENTS ETABLIS")
print("=" * 60)

# Try to load established client data
# Adjust the path to match your repo structure
try:
    # Option 1: df_etabli is already in memory
    print(f"Clients etablis : {len(df_etabli):,}")
    pnb_etabli = df_etabli["nbi_annual"] if "nbi_annual" in df_etabli.columns else df_etabli["pnb_annuel"]
except NameError:
    print("DataFrame des clients etablis (df_etabli) non charge.")
    print("Pour comparer, charger les donnees du modele existant :")
    print("  from simplified.data_processing import build_new_client_training_set")
    print("  ou charger directement les Stock CSVs")
    pnb_etabli = None

if pnb_etabli is not None:
    pnb_new = df["pnb_total"].dropna()

    print(f"\nNouvelles acquisitions (n={len(pnb_new):,}):")
    print(f"  PNB moyen :  {pnb_new.mean():,.0f} EUR")
    print(f"  PNB median : {pnb_new.median():,.0f} EUR")

    print(f"\nClients etablis (n={len(pnb_etabli):,}):")
    print(f"  PNB moyen :  {pnb_etabli.mean():,.0f} EUR")
    print(f"  PNB median : {pnb_etabli.median():,.0f} EUR")

    ratio = pnb_new.mean() / pnb_etabli.mean()
    print(f"\nRatio nouveau / etabli : {ratio:.2f}")
    if ratio < 0.8:
        print("  -> Les nouveaux generent significativement moins de PNB")
        print("  -> Un modele separe est justifie")
    elif ratio > 1.2:
        print("  -> Les nouveaux generent plus de PNB (acquisitions ciblees ?)")
    else:
        print("  -> PNB comparable entre nouveaux et etablis")

    # KS test
    ks_stat, ks_p = stats.ks_2samp(pnb_new, pnb_etabli.dropna())
    print(f"\nKS test : stat={ks_stat:.3f}, p={ks_p:.6f}")
    if ks_p < 0.05:
        print("-> HA9 VALIDEE : distributions significativement differentes")
    else:
        print("-> HA9 NON VALIDEE : distributions similaires")

    # Overlay histogram
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(pnb_new.clip(-2000, 15000), bins=80, alpha=0.5, label="Nouveaux clients", density=True)
    ax.hist(pnb_etabli.clip(-2000, 15000), bins=80, alpha=0.5, label="Clients etablis", density=True)
    ax.set_xlabel("PNB annuel (EUR)")
    ax.set_ylabel("Densite")
    ax.set_title("Distribution PNB : nouveaux vs etablis")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()

else:
    print("\n  Analyse HA9 reportee — charger df_etabli pour comparer.")

    # Fallback: compare first-year vs second-year PNB for clients with 2+ years
    print("\n  Alternative : comparer PNB annee 1 vs annee 2 des memes clients")
    print("  (pour les cohortes 2023 qui ont 2 ans de recul)")


# %% ---- CELL 5: HA10 — Concentration du PNB (Pareto / Lorenz) ----

print("\n" + "=" * 60)
print("HA10 — CONCENTRATION DU PNB (LOI DE PARETO)")
print("=" * 60)

pnb = df["pnb_total"].dropna()
pnb_positive = pnb[pnb > 0].sort_values(ascending=False)

n = len(pnb_positive)
total_pnb = pnb_positive.sum()

# Concentration table
print("\nConcentration du PNB des nouveaux clients :\n")
for pct in [1, 5, 10, 20, 50]:
    top_n = max(int(n * pct / 100), 1)
    top_pnb = pnb_positive.head(top_n).sum()
    print(f"  Top {pct:2d}% des clients ({top_n:,}) : {top_pnb/total_pnb*100:.1f}% du PNB total")

# Gini coefficient
def gini_coefficient(values):
    sorted_vals = np.sort(values)
    n = len(sorted_vals)
    cumvals = np.cumsum(sorted_vals)
    return (2 * np.sum((np.arange(1, n+1) * sorted_vals)) / (n * cumvals[-1])) - (n + 1) / n

gini = gini_coefficient(pnb_positive.values)
print(f"\nCoefficient de Gini : {gini:.3f}")
if gini > 0.6:
    print("  -> Forte concentration (comparable au portefeuille etabli)")
elif gini > 0.4:
    print("  -> Concentration moderee")
else:
    print("  -> Concentration faible (PNB assez egalitaire)")

# Lorenz curve
fig, ax = plt.subplots(figsize=(10, 8))

cumulative_pnb = np.cumsum(pnb_positive.values) / total_pnb * 100
cumulative_clients = np.arange(1, n + 1) / n * 100

ax.plot(cumulative_clients, cumulative_pnb, lw=2, label=f"Nouveaux clients (Gini={gini:.2f})")
ax.plot([0, 100], [0, 100], "--", color="gray", alpha=0.5, label="Egalite parfaite")

# Mark key points
for pct in [10, 20]:
    idx = max(int(n * pct / 100), 1) - 1
    ax.plot(pct, cumulative_pnb[idx], "ro", markersize=8)
    ax.annotate(f"Top {pct}%: {cumulative_pnb[idx]:.0f}% du PNB",
                (pct, cumulative_pnb[idx]), textcoords="offset points",
                xytext=(10, -10), fontsize=9)

ax.set_xlabel("% des clients (classes par PNB decroissant)")
ax.set_ylabel("% du PNB total cumule")
ax.set_title("Courbe de Lorenz — PNB des nouveaux clients")
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()


# %% ---- CELL 6: HA10.2 — Concentration par segment ----

print("\n" + "=" * 60)
print("HA10.2 — CONCENTRATION PAR SEGMENT")
print("=" * 60)

if "segment" in df.columns:
    for seg in sorted(df["segment"].unique()):
        seg_pnb = df[df["segment"] == seg]["pnb_total"].dropna()
        seg_positive = seg_pnb[seg_pnb > 0].sort_values(ascending=False)
        if len(seg_positive) > 10:
            seg_gini = gini_coefficient(seg_positive.values)
            top10_pct = seg_positive.head(max(int(len(seg_positive) * 0.1), 1)).sum() / seg_positive.sum() * 100
            print(f"  {seg}: Gini={seg_gini:.3f}, top 10% = {top10_pct:.1f}% du PNB")


# %% ---- CELL 7: Resume ----

print("\n" + "=" * 60)
print("HA8 + HA9 + HA10 — RESUME")
print("=" * 60)
print("""
HA8 (Stabilite cohortes) :
  KS test entre cohortes :     [STABLES / DERIVE DETECTEE]
  Mix segments stable :        [OUI / NON]
  Conclusion :                 [VALIDEE / NON VALIDEE]
  Impact : si derive -> le re-entrainement trimestriel est essentiel

HA9 (Nouveaux vs etablis) :
  Ratio PNB nouveau/etabli :   ____
  KS test :                    p = ____
  Conclusion :                 [VALIDEE / NON VALIDEE]
  Impact : si differents -> modele separe justifie

HA10 (Concentration Pareto) :
  Gini :                       ____
  Top 10% concentrent :        ____% du PNB
  Top 20% concentrent :        ____% du PNB
  Conclusion :                 [VALIDEE / NON VALIDEE]
  Impact : si concentre -> le modele doit bien predire les hauts PNB
""")
