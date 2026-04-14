# =============================================================================
# HA5 — Les Equipements (Produits) sont le Signal le Plus Fort
# =============================================================================
#
# Hypothese : le nombre et le type de produits souscrits dans les 6 premiers
# mois sont le meilleur predicteur du PNB a 12 mois.
#
# Cette analyse est cruciale car elle determine si les produits doivent
# etre les features principales du modele.
#
# Prerequis : df avec colonnes d'equipement (has_*, n_produits_total),
#   pnb_12m_total, segment
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats


# %% ---- CELL 2: Detecter les colonnes d'equipement ----

# Auto-detect equipment columns
equip_binary = [c for c in df.columns if c.startswith("has_")]
equip_count = [c for c in df.columns if "n_produits" in c or "n_familles" in c]

print("Colonnes equipement (binaires) :", equip_binary)
print("Colonnes equipement (comptage) :", equip_count)

# If equipment columns don't exist, try to detect product columns by name
if not equip_binary:
    possible_products = [c for c in df.columns if any(
        kw in c.lower() for kw in ["compte", "carte", "epargne", "credit",
                                     "assurance", "livret", "prevoyance", "vie"]
    )]
    print(f"Colonnes produit possibles : {possible_products}")


# %% ---- CELL 3: PNB moyen par nombre de produits ----

print("=" * 60)
print("HA5.1 — PNB PAR NOMBRE DE PRODUITS")
print("=" * 60)

count_col = None
if "n_produits_total" in df.columns:
    count_col = "n_produits_total"
elif equip_binary:
    df["n_produits_total"] = df[equip_binary].sum(axis=1)
    count_col = "n_produits_total"

if count_col:
    prod_stats = df.groupby(count_col)["pnb_12m_total"].agg(
        ["count", "mean", "median", "std"]
    ).round(0)
    print("\nPNB 12 mois par nombre de produits :\n")
    print(prod_stats.to_string())

    # Correlation
    mask = df[count_col].notna() & df["pnb_12m_total"].notna()
    r, p = stats.pearsonr(df.loc[mask, count_col], df.loc[mask, "pnb_12m_total"])
    rho, p_s = stats.spearmanr(df.loc[mask, count_col], df.loc[mask, "pnb_12m_total"])
    print(f"\nPearson r (n_produits vs PNB 12m) :  {r:.4f} (p={p:.2e})")
    print(f"Spearman rho :                       {rho:.4f} (p={p_s:.2e})")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    prod_means = df.groupby(count_col)["pnb_12m_total"].mean()
    prod_means.plot(kind="bar", ax=axes[0], color="steelblue", edgecolor="white")
    axes[0].set_xlabel("Nombre de produits")
    axes[0].set_ylabel("PNB moyen 12 mois (EUR)")
    axes[0].set_title("PNB moyen par nombre de produits")
    axes[0].grid(axis="y", alpha=0.3)

    df.boxplot(column="pnb_12m_total", by=count_col, ax=axes[1], showfliers=False,
               patch_artist=True)
    axes[1].set_xlabel("Nombre de produits")
    axes[1].set_ylabel("PNB 12 mois (EUR)")
    axes[1].set_title("Distribution PNB par nombre de produits")
    axes[1].grid(alpha=0.3)

    plt.suptitle("")
    plt.tight_layout()
    plt.show()


# %% ---- CELL 4: Impact de chaque produit individuellement ----

print("\n" + "=" * 60)
print("HA5.2 — IMPACT DE CHAQUE PRODUIT SUR LE PNB")
print("=" * 60)

if equip_binary:
    product_impact = []
    for prod in equip_binary:
        if df[prod].notna().any():
            with_prod = df[df[prod] == 1]["pnb_12m_total"]
            without_prod = df[df[prod] == 0]["pnb_12m_total"]

            if len(with_prod) > 5 and len(without_prod) > 5:
                diff = with_prod.mean() - without_prod.mean()
                # Mann-Whitney U test
                u_stat, u_p = stats.mannwhitneyu(with_prod, without_prod, alternative="two-sided")

                product_impact.append({
                    "produit": prod,
                    "n_avec": len(with_prod),
                    "pnb_moyen_avec": round(with_prod.mean(), 0),
                    "pnb_moyen_sans": round(without_prod.mean(), 0),
                    "difference": round(diff, 0),
                    "pct_diff": round(diff / without_prod.mean() * 100, 1) if without_prod.mean() != 0 else 0,
                    "p_value": round(u_p, 4),
                    "significatif": "OUI" if u_p < 0.05 else "NON",
                })

    impact_df = pd.DataFrame(product_impact).sort_values("difference", ascending=False)
    print("\nImpact de chaque produit sur le PNB 12 mois :\n")
    print(impact_df.to_string(index=False))

    # Ranking chart
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = ["#2ecc71" if row["significatif"] == "OUI" else "#95a5a6"
              for _, row in impact_df.iterrows()]
    impact_df_sorted = impact_df.sort_values("difference")
    ax.barh(impact_df_sorted["produit"], impact_df_sorted["difference"], color=colors)
    ax.set_xlabel("Difference de PNB moyen (EUR) : avec produit - sans produit")
    ax.set_title("Impact de chaque produit sur le PNB 12 mois")
    ax.axvline(0, color="black", lw=0.5)
    ax.grid(axis="x", alpha=0.3)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#2ecc71", label="Significatif (p < 0.05)"),
        Patch(facecolor="#95a5a6", label="Non significatif"),
    ]
    ax.legend(handles=legend_elements)
    plt.tight_layout()
    plt.show()

    print(f"\nTop 3 produits les plus impactants :")
    for _, row in impact_df.head(3).iterrows():
        print(f"  {row['produit']}: +{row['difference']:,.0f} EUR ({row['pct_diff']:+.1f}%)")


# %% ---- CELL 5: Domiciliation du salaire (signal cle) ----

print("\n" + "=" * 60)
print("HA5.3 — DOMICILIATION DU SALAIRE")
print("=" * 60)

dom_col = None
for c in ["a_domiciliation_salaire", "has_domiciliation", "domiciliation_salaire",
           "salary_domiciliation"]:
    if c in df.columns:
        dom_col = c
        break

if dom_col:
    with_dom = df[df[dom_col] == 1]["pnb_12m_total"]
    without_dom = df[df[dom_col] == 0]["pnb_12m_total"]

    print(f"Avec domiciliation :   n={len(with_dom):,}, PNB moyen={with_dom.mean():,.0f} EUR")
    print(f"Sans domiciliation :   n={len(without_dom):,}, PNB moyen={without_dom.mean():,.0f} EUR")
    print(f"Difference :           {with_dom.mean() - without_dom.mean():+,.0f} EUR ({(with_dom.mean()/without_dom.mean()-1)*100:+.1f}%)")

    u, p = stats.mannwhitneyu(with_dom, without_dom, alternative="two-sided")
    print(f"Mann-Whitney U test :  p = {p:.6f} {'(SIGNIFICATIF)' if p < 0.05 else '(non significatif)'}")
else:
    print("Colonne domiciliation non trouvee.")
    print("Si disponible, c'est potentiellement le signal le plus fort.")


# %% ---- CELL 6: Interaction produits x segment ----

print("\n" + "=" * 60)
print("HA5.4 — PRODUITS x SEGMENT")
print("=" * 60)

if "segment" in df.columns and count_col:
    pivot_prod_seg = df.pivot_table(
        values="pnb_12m_total", index=count_col, columns="segment",
        aggfunc="mean"
    ).round(0)

    print("PNB moyen par n_produits x segment :\n")
    print(pivot_prod_seg.to_string())

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    pivot_prod_seg.plot(kind="bar", ax=ax, edgecolor="white")
    ax.set_xlabel("Nombre de produits")
    ax.set_ylabel("PNB moyen 12 mois (EUR)")
    ax.set_title("PNB par nombre de produits et segment")
    ax.legend(title="Segment")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.show()


# %% ---- CELL 7: Evolution de l'equipement dans les premiers mois ----

print("\n" + "=" * 60)
print("HA5.5 — COURBE D'EQUIPEMENT (premiers 6 mois)")
print("=" * 60)

# If we have monthly product data
prod_monthly = [c for c in df.columns if "n_produits_m" in c or "equip_m" in c]
if prod_monthly:
    print("Colonnes produits mensuels :", prod_monthly)
    monthly_means = df[prod_monthly].mean()
    print("\nNombre moyen de produits par mois :")
    print(monthly_means.round(2).to_string())

    fig, ax = plt.subplots(figsize=(10, 5))
    monthly_means.plot(kind="line", marker="o", ax=ax, color="steelblue")
    ax.set_ylabel("Nombre moyen de produits")
    ax.set_title("Evolution de l'equipement dans les premiers mois")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()
else:
    print("Pas de donnees d'equipement mensuel.")
    print("Analyse possible si les dates de souscription des produits sont disponibles.")

    # Alternative: early vs late equipment
    if count_col:
        print(f"\nDistribution du nombre de produits (snapshot) :")
        print(df[count_col].describe().round(1).to_string())


# %% ---- CELL 8: Combinaisons de produits ----

print("\n" + "=" * 60)
print("HA5.6 — COMBINAISONS DE PRODUITS")
print("=" * 60)

if equip_binary and len(equip_binary) >= 2:
    # Create a product combo signature
    df["combo_produits"] = df[equip_binary].apply(
        lambda row: "+".join([col.replace("has_", "") for col in equip_binary if row[col] == 1]),
        axis=1
    )
    df["combo_produits"] = df["combo_produits"].replace("", "aucun")

    combo_stats = df.groupby("combo_produits").agg(
        n_clients=("client_id", "count"),
        pnb_moyen=("pnb_12m_total", "mean"),
        pnb_median=("pnb_12m_total", "median"),
    ).round(0).sort_values("n_clients", ascending=False)

    # Top 15 combinations
    top_combos = combo_stats.head(15)
    print("\nTop 15 combinaisons de produits :\n")
    print(top_combos.to_string())

    fig, ax = plt.subplots(figsize=(14, 7))
    top_combos_sorted = top_combos.sort_values("pnb_moyen")
    ax.barh(top_combos_sorted.index, top_combos_sorted["pnb_moyen"], color="teal")
    # Add client count annotation
    for idx, row in top_combos_sorted.iterrows():
        ax.text(row["pnb_moyen"] + 50, list(top_combos_sorted.index).index(idx),
                f"n={int(row['n_clients'])}", va="center", fontsize=8)
    ax.set_xlabel("PNB moyen 12 mois (EUR)")
    ax.set_title("PNB moyen par combinaison de produits (Top 15)")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.show()


# %% ---- CELL 9: Comparaison pouvoir predictif : PNB cumule vs equipements ----

print("\n" + "=" * 60)
print("HA5.7 — PNB CUMULE vs EQUIPEMENTS : QUI PREDIT MIEUX ?")
print("=" * 60)

from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

results_comparison = []

# Model 1: PNB cumule seul
if "pnb_cumul_6m" in df.columns:
    mask = df["pnb_cumul_6m"].notna() & df["pnb_12m_total"].notna()
    X1 = df.loc[mask, "pnb_cumul_6m"].values.reshape(-1, 1)
    y = df.loc[mask, "pnb_12m_total"].values
    lr1 = LinearRegression().fit(X1, y)
    r2_pnb = r2_score(y, lr1.predict(X1))
    results_comparison.append({"modele": "PNB 6 mois seul", "r2": r2_pnb})

# Model 2: Equipements seuls
if count_col and equip_binary:
    feat_equip = [count_col] + equip_binary
    feat_equip = [c for c in feat_equip if c in df.columns]
    mask = df[feat_equip + ["pnb_12m_total"]].notna().all(axis=1)
    X2 = df.loc[mask, feat_equip].values
    y2 = df.loc[mask, "pnb_12m_total"].values
    lr2 = LinearRegression().fit(X2, y2)
    r2_equip = r2_score(y2, lr2.predict(X2))
    results_comparison.append({"modele": "Equipements seuls", "r2": r2_equip})

# Model 3: PNB + Equipements combines
if "pnb_cumul_6m" in df.columns and equip_binary:
    feat_all = ["pnb_cumul_6m"] + [count_col] + equip_binary
    feat_all = [c for c in feat_all if c in df.columns]
    mask = df[feat_all + ["pnb_12m_total"]].notna().all(axis=1)
    X3 = df.loc[mask, feat_all].values
    y3 = df.loc[mask, "pnb_12m_total"].values
    lr3 = LinearRegression().fit(X3, y3)
    r2_combined = r2_score(y3, lr3.predict(X3))
    results_comparison.append({"modele": "PNB + Equipements", "r2": r2_combined})

comp_df = pd.DataFrame(results_comparison)
print("\nComparaison du pouvoir predictif (R2, regression lineaire) :\n")
print(comp_df.to_string(index=False, float_format="%.4f"))
print(f"\n-> Le modele le plus performant est : {comp_df.loc[comp_df['r2'].idxmax(), 'modele']}")


# %% ---- CELL 10: Verdict ----

print("\n" + "=" * 60)
print("HA5 — VERDICT")
print("=" * 60)
print("""
A remplir :
  Correlation n_produits vs PNB 12m :  r = ____
  Produit le plus impactant :          __________ (+____ EUR)
  Domiciliation salaire impact :       +____ EUR
  R2 equipements seuls :               ____
  R2 PNB cumule seul :                 ____
  R2 combine :                         ____

  HA5 VALIDEE si :
    - L'impact des produits est significatif
    - R2 equipements >= R2 PNB cumule (ou complementaire)
    - Au moins 2-3 produits avec un effet > 500 EUR sur le PNB

  Conclusion : [VALIDEE / PARTIELLEMENT / NON VALIDEE]
  Les equipements sont-ils le signal le plus fort ? [OUI / NON / COMPARABLE AU PNB]
""")
