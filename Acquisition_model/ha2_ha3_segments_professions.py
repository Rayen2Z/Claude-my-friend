# =============================================================================
# HA2 + HA3 — Segments et Professions comme Predicteurs du PNB
# =============================================================================
#
# HA2 : Le segment (Mass Affluent / Mass Retail / MR with Potential) est-il
#        significativement correle au PNB a 12 mois ?
# HA3 : La profession (Jeune Actif / Salarie / Cadre / etc.) apporte-t-elle
#        un signal predictif au-dela du segment ?
#
# Prerequis : df avec colonnes segment, profession, pnb_12m_total
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats


# %% ---- CELL 2: PNB par segment ----

print("=" * 60)
print("HA2 — PNB PAR SEGMENT")
print("=" * 60)

if "segment" not in df.columns or "pnb_12m_total" not in df.columns:
    print("ERREUR : colonnes 'segment' et/ou 'pnb_12m_total' manquantes.")
else:
    seg_stats = df.groupby("segment")["pnb_12m_total"].agg(
        ["count", "mean", "median", "std", "min", "max"]
    ).round(0)
    seg_stats["cv"] = (seg_stats["std"] / seg_stats["mean"]).round(2)
    seg_stats["part_pnb_total"] = (
        df.groupby("segment")["pnb_12m_total"].sum()
        / df["pnb_12m_total"].sum() * 100
    ).round(1)

    print("\nStatistiques PNB 12 mois par segment :\n")
    print(seg_stats.to_string())

    # Part des clients vs part du PNB
    print("\n--- Concentration ---")
    for seg in df["segment"].unique():
        pct_clients = (df["segment"] == seg).mean() * 100
        pct_pnb = seg_stats.loc[seg, "part_pnb_total"]
        print(f"  {seg}: {pct_clients:.1f}% des clients, {pct_pnb:.1f}% du PNB")


# %% ---- CELL 3: Test statistique — differences entre segments ----

print("\n" + "=" * 60)
print("HA2 — TEST STATISTIQUE (Kruskal-Wallis)")
print("=" * 60)

segments = df["segment"].unique()
groups = [df[df["segment"] == s]["pnb_12m_total"].dropna() for s in segments]

if len(groups) >= 2:
    stat, p_value = stats.kruskal(*groups)
    print(f"\nKruskal-Wallis H-statistic : {stat:.2f}")
    print(f"p-value : {p_value:.6f}")

    if p_value < 0.05:
        print("RESULTAT : Les segments ont des PNB significativement differents (p < 0.05)")
        print("-> HA2 VALIDEE : le segment est un predicteur du PNB")
    else:
        print("RESULTAT : Pas de difference significative entre les segments (p >= 0.05)")
        print("-> HA2 NON VALIDEE")

    # Effect size (eta-squared)
    n = len(df["pnb_12m_total"].dropna())
    k = len(segments)
    eta_sq = (stat - k + 1) / (n - k)
    print(f"Eta-squared (taille d'effet) : {eta_sq:.4f}")
    if eta_sq > 0.14:
        print("  -> Effet large")
    elif eta_sq > 0.06:
        print("  -> Effet moyen")
    else:
        print("  -> Effet faible")


# %% ---- CELL 4: Visualisation — boxplots et violins ----

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Boxplot
bp = df.boxplot(column="pnb_12m_total", by="segment", ax=axes[0],
                patch_artist=True, showfliers=False)
axes[0].set_title("PNB 12 mois par segment (boxplot)")
axes[0].set_xlabel("Segment")
axes[0].set_ylabel("PNB 12 mois (EUR)")
axes[0].grid(alpha=0.3)
plt.sca(axes[0])
plt.xticks(rotation=15, ha="right")

# Bar chart des moyennes
seg_means = df.groupby("segment")["pnb_12m_total"].mean().sort_values(ascending=False)
seg_means.plot(kind="bar", ax=axes[1], color=["#e74c3c", "#3498db", "#2ecc71", "#f39c12"][:len(seg_means)],
               edgecolor="white")
axes[1].set_title("PNB moyen 12 mois par segment")
axes[1].set_ylabel("PNB moyen (EUR)")
axes[1].set_xlabel("")
axes[1].grid(axis="y", alpha=0.3)
plt.xticks(rotation=15, ha="right")

plt.suptitle("")  # remove auto title from boxplot
plt.tight_layout()
plt.show()


# %% ---- CELL 5: PNB par profession ----

print("\n" + "=" * 60)
print("HA3 — PNB PAR PROFESSION")
print("=" * 60)

if "profession" in df.columns:
    prof_stats = df.groupby("profession")["pnb_12m_total"].agg(
        ["count", "mean", "median", "std"]
    ).round(0).sort_values("mean", ascending=False)

    print("\nStatistiques PNB 12 mois par profession :\n")
    print(prof_stats.to_string())

    # Kruskal-Wallis
    professions = df["profession"].unique()
    groups_prof = [df[df["profession"] == p]["pnb_12m_total"].dropna() for p in professions]

    if len(groups_prof) >= 2:
        stat_p, p_val_p = stats.kruskal(*groups_prof)
        print(f"\nKruskal-Wallis : H={stat_p:.2f}, p={p_val_p:.6f}")
        if p_val_p < 0.05:
            print("-> HA3 VALIDEE : la profession est un predicteur du PNB")
        else:
            print("-> HA3 NON VALIDEE")

    # Bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    prof_means = df.groupby("profession")["pnb_12m_total"].mean().sort_values(ascending=True)
    prof_means.plot(kind="barh", ax=ax, color="teal", edgecolor="white")
    ax.set_xlabel("PNB moyen 12 mois (EUR)")
    ax.set_title("PNB moyen par profession")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.show()


# %% ---- CELL 6: Interaction segment x profession ----

print("\n" + "=" * 60)
print("HA3 — INTERACTION SEGMENT x PROFESSION")
print("=" * 60)

if "segment" in df.columns and "profession" in df.columns:
    # Heatmap des PNB moyens
    pivot = df.pivot_table(
        values="pnb_12m_total", index="profession", columns="segment",
        aggfunc="mean"
    ).round(0)

    print("PNB moyen par segment x profession :\n")
    print(pivot.to_string())

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("PNB moyen — Segment x Profession")
    plt.colorbar(im, label="PNB moyen (EUR)")

    # Annotate cells
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:,.0f}", ha="center", va="center", fontsize=8)

    plt.tight_layout()
    plt.show()

    # Cramer's V — mesure d'association entre segment et profession
    contingency = pd.crosstab(df["segment"], df["profession"])
    chi2, p, dof, expected = stats.chi2_contingency(contingency)
    n = contingency.sum().sum()
    k = min(contingency.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * k)) if k > 0 else 0

    print(f"\nCramer's V (segment vs profession) : {cramers_v:.3f}")
    if cramers_v > 0.5:
        print("  -> Association forte : risque de multicolinearite")
        print("  -> Considerer n'utiliser qu'une seule des deux variables")
    elif cramers_v > 0.3:
        print("  -> Association moderee : les deux variables apportent un signal complementaire")
    else:
        print("  -> Association faible : les deux variables sont independantes, garder les deux")


# %% ---- CELL 7: Resume ----

print("\n" + "=" * 60)
print("HA2 + HA3 — RESUME")
print("=" * 60)
print("""
Resultats a remplir :
  HA2 (Segment -> PNB) :     [VALIDEE / NON VALIDEE]
  HA3 (Profession -> PNB) :  [VALIDEE / NON VALIDEE]
  Interaction sig x prof :   [FORTE / MODEREE / FAIBLE]
  Recommandation :           [Garder les deux / Fusionner / Retirer une]
""")
