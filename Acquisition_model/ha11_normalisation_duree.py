# =============================================================================
# HA11 — Normalisation du PNB par duree d'exposition
# =============================================================================
#
# Question : Le PNB mensuel moyen (pnb_total / n_mois_nbi) est-il constant
# quel que soit le nombre de mois d'observation (10, 11, 12), ou la duree
# biaise-t-elle le PNB moyen ?
#
# Si stable -> la normalisation est valide, le PNB est lineaire en duree.
# Si non -> le modele doit apprendre une correction non-lineaire.
#
# Impact : valide le choix de garder pnb_total brut + n_mois_nbi comme feature.
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


# %% ---- CELL 2: Distribution de n_mois_nbi ----

print("=" * 60)
print("HA11.1 — DISTRIBUTION DE n_mois_nbi")
print("=" * 60)

if "n_mois_nbi" not in df.columns:
    print("ERREUR : colonne n_mois_nbi manquante. Executer data_preparation.ipynb.")
else:
    nbi_counts = df["n_mois_nbi"].value_counts().sort_index()
    nbi_pcts = (nbi_counts / len(df) * 100).round(1)
    print("\nRepartition de n_mois_nbi :\n")
    for val in nbi_counts.index:
        print(f"  {val} mois : {nbi_counts[val]:,} clients ({nbi_pcts[val]:.1f}%)")

    fig, ax = plt.subplots(figsize=(8, 5))
    nbi_counts.plot(kind="bar", ax=ax, color="steelblue", edgecolor="white")
    ax.set_xlabel("n_mois_nbi")
    ax.set_ylabel("Nombre de clients")
    ax.set_title("Distribution du nombre de mois NBI")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()


# %% ---- CELL 3: PNB mensuel moyen par n_mois_nbi ----

print("\n" + "=" * 60)
print("HA11.2 — PNB MENSUEL MOYEN PAR n_mois_nbi")
print("=" * 60)

if "pnb_mensuel_moyen" in df.columns and "n_mois_nbi" in df.columns:
    norm_stats = df.groupby("n_mois_nbi")["pnb_mensuel_moyen"].agg(
        ["count", "mean", "median", "std"]
    ).round(1)
    print("\nPNB mensuel moyen par duree d'exposition :\n")
    print(norm_stats.to_string())

    # Also show raw pnb_total for comparison
    raw_stats = df.groupby("n_mois_nbi")["pnb_total"].agg(
        ["mean", "median", "std"]
    ).round(0)
    print("\nPNB total (brut) par duree d'exposition :\n")
    print(raw_stats.to_string())

    # Relative difference of pnb_mensuel_moyen across groups
    global_mean = df["pnb_mensuel_moyen"].mean()
    print(f"\nPNB mensuel moyen global : {global_mean:,.1f} EUR")
    for nbi in sorted(df["n_mois_nbi"].unique()):
        group_mean = df[df["n_mois_nbi"] == nbi]["pnb_mensuel_moyen"].mean()
        pct_diff = (group_mean / global_mean - 1) * 100
        print(f"  n_mois_nbi={nbi}: {group_mean:,.1f} EUR ({pct_diff:+.1f}% vs global)")


# %% ---- CELL 4: Test statistique — pnb_mensuel_moyen identique entre groupes ? ----

print("\n" + "=" * 60)
print("HA11.3 — TEST STATISTIQUE")
print("=" * 60)

if "pnb_mensuel_moyen" in df.columns and "n_mois_nbi" in df.columns:
    groups = [df[df["n_mois_nbi"] == nbi]["pnb_mensuel_moyen"].dropna()
              for nbi in sorted(df["n_mois_nbi"].unique())]
    groups = [g for g in groups if len(g) > 5]

    if len(groups) >= 2:
        h_stat, h_p = stats.kruskal(*groups)
        print(f"\nKruskal-Wallis (pnb_mensuel_moyen entre groupes n_mois_nbi) :")
        print(f"  H = {h_stat:.2f}, p = {h_p:.6f}")

        if h_p >= 0.05:
            print("  -> PAS de difference significative entre les groupes")
            print("  -> La normalisation PNB/mois est VALIDE")
            print("  -> Le PNB est approximativement lineaire en duree")
        else:
            print("  -> Difference significative detectee")
            print("  -> La normalisation PNB/mois n'est PAS parfaitement lineaire")
            print("  -> Le modele doit apprendre la correction via n_mois_nbi")

    # Pairwise Mann-Whitney for each pair
    nbi_vals = sorted(df["n_mois_nbi"].unique())
    if len(nbi_vals) >= 2:
        print("\nTests pairwise (Mann-Whitney U) :")
        for i in range(len(nbi_vals)):
            for j in range(i + 1, len(nbi_vals)):
                g1 = df[df["n_mois_nbi"] == nbi_vals[i]]["pnb_mensuel_moyen"].dropna()
                g2 = df[df["n_mois_nbi"] == nbi_vals[j]]["pnb_mensuel_moyen"].dropna()
                if len(g1) > 5 and len(g2) > 5:
                    u_stat, u_p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
                    sig = "OUI" if u_p < 0.05 else "NON"
                    print(f"  {nbi_vals[i]} vs {nbi_vals[j]}: U={u_stat:.0f}, p={u_p:.4f} (sig: {sig})")


# %% ---- CELL 5: Visualisation ----

if "pnb_mensuel_moyen" in df.columns and "n_mois_nbi" in df.columns:
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Boxplot PNB mensuel moyen by n_mois_nbi
    df.boxplot(column="pnb_mensuel_moyen", by="n_mois_nbi", ax=axes[0],
               showfliers=False, patch_artist=True)
    axes[0].set_xlabel("n_mois_nbi")
    axes[0].set_ylabel("PNB mensuel moyen (EUR)")
    axes[0].set_title("PNB mensuel moyen par duree d'exposition")
    axes[0].grid(alpha=0.3)

    # Bar chart des moyennes
    means_by_nbi = df.groupby("n_mois_nbi")["pnb_mensuel_moyen"].mean()
    means_by_nbi.plot(kind="bar", ax=axes[1], color="steelblue", edgecolor="white")
    axes[1].set_xlabel("n_mois_nbi")
    axes[1].set_ylabel("PNB mensuel moyen (EUR)")
    axes[1].set_title("Moyenne PNB/mois par n_mois_nbi")
    axes[1].grid(axis="y", alpha=0.3)
    plt.sca(axes[1])
    plt.xticks(rotation=0)

    # Histogram overlay
    for nbi in sorted(df["n_mois_nbi"].unique()):
        subset = df[df["n_mois_nbi"] == nbi]["pnb_mensuel_moyen"].dropna()
        axes[2].hist(subset.clip(-500, 2000), bins=50, alpha=0.4,
                     label=f"n_mois_nbi={nbi} (n={len(subset)})", density=True)
    axes[2].set_xlabel("PNB mensuel moyen (EUR)")
    axes[2].set_ylabel("Densite")
    axes[2].set_title("Distribution PNB/mois par n_mois_nbi")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    plt.suptitle("")
    plt.tight_layout()
    plt.show()


# %% ---- CELL 6: Stabilite par segment ----

print("\n" + "=" * 60)
print("HA11.4 — STABILITE PAR SEGMENT")
print("=" * 60)

if "segment" in df.columns and "pnb_mensuel_moyen" in df.columns and "n_mois_nbi" in df.columns:
    pivot = df.pivot_table(
        values="pnb_mensuel_moyen", index="n_mois_nbi", columns="segment",
        aggfunc="mean"
    ).round(1)
    print("\nPNB mensuel moyen par n_mois_nbi x segment :\n")
    print(pivot.to_string())

    # Check stability within each segment
    for seg in sorted(df["segment"].unique()):
        seg_df = df[df["segment"] == seg]
        seg_groups = [seg_df[seg_df["n_mois_nbi"] == nbi]["pnb_mensuel_moyen"].dropna()
                      for nbi in sorted(seg_df["n_mois_nbi"].unique())]
        seg_groups = [g for g in seg_groups if len(g) > 5]
        if len(seg_groups) >= 2:
            h, p = stats.kruskal(*seg_groups)
            verdict = "STABLE" if p >= 0.05 else "DIFFERE"
            print(f"  {seg}: KW p={p:.4f} -> {verdict}")

    fig, ax = plt.subplots(figsize=(10, 6))
    pivot.plot(kind="bar", ax=ax, edgecolor="white")
    ax.set_xlabel("n_mois_nbi")
    ax.set_ylabel("PNB mensuel moyen (EUR)")
    ax.set_title("PNB mensuel moyen par duree et segment")
    ax.legend(title="Segment")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()


# %% ---- CELL 7: Verdict ----

print("\n" + "=" * 60)
print("HA11 — VERDICT")
print("=" * 60)
print("""
A remplir :
  PNB mensuel moyen (n=10) : ____ EUR
  PNB mensuel moyen (n=11) : ____ EUR
  PNB mensuel moyen (n=12) : ____ EUR
  Kruskal-Wallis p-value :   ____

  HA11 VALIDEE si :
    - p >= 0.05 (pas de difference significative)
    - Ecart relatif < 10% entre les groupes
    - Stabilite uniforme entre segments

  Si VALIDEE :
    -> La normalisation PNB/mois est fiable
    -> pnb_mensuel_moyen peut etre utilise comme cible alternative
    -> n_mois_nbi reste utile comme feature de controle

  Si NON VALIDEE :
    -> Le PNB n'est pas lineaire en duree (ex: effets de seuil, cotisations annuelles)
    -> Garder pnb_total brut + n_mois_nbi (le modele apprend la correction)
    -> Ne PAS utiliser pnb_mensuel_moyen comme cible

  Conclusion : [VALIDEE / NON VALIDEE]
""")
