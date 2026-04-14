# =============================================================================
# HA1 — Qualite et Completude des Donnees
# =============================================================================
#
# Verifie que les donnees sont suffisamment propres pour entrainer un modele :
#   - Valeurs manquantes
#   - Doublons
#   - Coherence des dates et du PNB
#   - Couverture des equipements
#   - Distribution des variables categorielles
#
# Prerequis : df = DataFrame unifie avec colonnes client_id, date_creation,
#   segment, profession, pnb_m1..pnb_m12, equipements, etc.
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# %% ---- CELL 2: Valeurs manquantes par colonne ----

print("=" * 60)
print("HA1.1 — VALEURS MANQUANTES")
print("=" * 60)

missing = df.isnull().sum()
missing_pct = (missing / len(df) * 100).round(1)
missing_report = pd.DataFrame({
    "n_manquants": missing,
    "pct_manquants": missing_pct,
}).sort_values("pct_manquants", ascending=False)

print(missing_report[missing_report["n_manquants"] > 0].to_string())
print(f"\nColonnes 100% remplies : {(missing == 0).sum()} / {len(df.columns)}")
print(f"Colonnes avec > 50% manquants : {(missing_pct > 50).sum()}")

# Plot
fig, ax = plt.subplots(figsize=(12, 6))
cols_with_missing = missing_pct[missing_pct > 0].sort_values(ascending=True)
if len(cols_with_missing) > 0:
    cols_with_missing.plot(kind="barh", ax=ax, color="salmon")
    ax.set_xlabel("% de valeurs manquantes")
    ax.set_title("Taux de valeurs manquantes par colonne")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.show()
else:
    print("Aucune valeur manquante detectee.")


# %% ---- CELL 3: Doublons sur client_id ----

print("\n" + "=" * 60)
print("HA1.2 — DOUBLONS")
print("=" * 60)

n_total = len(df)
n_unique = df["client_id"].nunique()
n_doublons = n_total - n_unique

print(f"Lignes totales :     {n_total:,}")
print(f"Clients uniques :    {n_unique:,}")
print(f"Doublons client_id : {n_doublons:,} ({n_doublons/n_total*100:.2f}%)")

if n_doublons > 0:
    dupes = df[df.duplicated(subset=["client_id"], keep=False)]
    print(f"\nExemple de doublons :")
    print(dupes.head(10)[["client_id", "date_creation", "segment"]].to_string())
    print("\nACTION : verifier si ce sont des multi-entrees ou des erreurs.")


# %% ---- CELL 4: Coherence des dates de creation ----

print("\n" + "=" * 60)
print("HA1.3 — COHERENCE DES DATES")
print("=" * 60)

if "date_creation" in df.columns:
    df["date_creation"] = pd.to_datetime(df["date_creation"], errors="coerce")

    dates_null = df["date_creation"].isnull().sum()
    dates_future = (df["date_creation"] > pd.Timestamp("2026-04-01")).sum()
    dates_before = (df["date_creation"] < pd.Timestamp("2023-01-01")).sum()

    print(f"Dates nulles :        {dates_null}")
    print(f"Dates dans le futur : {dates_future}")
    print(f"Dates avant 2023 :    {dates_before}")
    print(f"Date min :            {df['date_creation'].min()}")
    print(f"Date max :            {df['date_creation'].max()}")

    # Distribution par mois
    df["mois_creation"] = df["date_creation"].dt.to_period("M")
    acquisitions_par_mois = df.groupby("mois_creation").size()
    print(f"\nAcquisitions par mois :")
    print(acquisitions_par_mois.to_string())

    fig, ax = plt.subplots(figsize=(14, 5))
    acquisitions_par_mois.plot(kind="bar", ax=ax, color="steelblue")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Nombre de nouveaux clients")
    ax.set_title("Volume d'acquisitions par mois")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()
else:
    print("Colonne 'date_creation' non trouvee.")


# %% ---- CELL 5: Coherence du PNB ----

print("\n" + "=" * 60)
print("HA1.4 — COHERENCE DU PNB")
print("=" * 60)

# Detect PNB columns
pnb_cols = [c for c in df.columns if "pnb" in c.lower() or "nbi" in c.lower()]
print(f"Colonnes PNB detectees : {pnb_cols}")

if "pnb_12m_total" in df.columns:
    pnb = df["pnb_12m_total"]
    print(f"\nPNB 12 mois :")
    print(f"  Count :   {pnb.notna().sum():,}")
    print(f"  Mean :    {pnb.mean():,.0f} EUR")
    print(f"  Median :  {pnb.median():,.0f} EUR")
    print(f"  Std :     {pnb.std():,.0f} EUR")
    print(f"  Min :     {pnb.min():,.0f} EUR")
    print(f"  Max :     {pnb.max():,.0f} EUR")
    print(f"  PNB <= 0: {(pnb <= 0).sum()} ({(pnb <= 0).mean()*100:.1f}%)")
    print(f"  PNB = 0 : {(pnb == 0).sum()} ({(pnb == 0).mean()*100:.1f}%)")

    # Outliers (IQR method)
    q1, q3 = pnb.quantile(0.25), pnb.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 3 * iqr, q3 + 3 * iqr
    outliers = ((pnb < lower) | (pnb > upper)).sum()
    print(f"\n  Outliers (3x IQR) : {outliers} ({outliers/len(pnb)*100:.1f}%)")
    print(f"  Seuil bas :  {lower:,.0f} EUR")
    print(f"  Seuil haut : {upper:,.0f} EUR")

    # Distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].hist(pnb.clip(-5000, 20000), bins=100, edgecolor="white", alpha=0.8)
    axes[0].set_xlabel("PNB 12 mois (EUR)")
    axes[0].set_title("Distribution du PNB 12 mois (clippe)")
    axes[0].axvline(0, color="red", ls="--", alpha=0.5)
    axes[0].grid(alpha=0.3)

    axes[1].hist(np.log1p(pnb.clip(lower=0)), bins=100, edgecolor="white", alpha=0.8, color="green")
    axes[1].set_xlabel("log(PNB + 1)")
    axes[1].set_title("Distribution log-transformee (PNB > 0)")
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.show()


# %% ---- CELL 6: Distribution des segments et professions ----

print("\n" + "=" * 60)
print("HA1.5 — DISTRIBUTION DES CATEGORIES")
print("=" * 60)

for col in ["segment", "profession"]:
    if col in df.columns:
        counts = df[col].value_counts()
        pcts = (counts / len(df) * 100).round(1)
        print(f"\n--- {col.upper()} ---")
        for val, cnt in counts.items():
            print(f"  {val}: {cnt:,} ({pcts[val]:.1f}%)")

        fig, ax = plt.subplots(figsize=(10, 5))
        counts.plot(kind="bar", ax=ax, color="teal", edgecolor="white")
        ax.set_title(f"Distribution des {col}s")
        ax.set_ylabel("Nombre de clients")
        ax.grid(axis="y", alpha=0.3)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.show()


# %% ---- CELL 7: Couverture des equipements ----

print("\n" + "=" * 60)
print("HA1.6 — COUVERTURE DES EQUIPEMENTS")
print("=" * 60)

equip_cols = [c for c in df.columns if c.startswith("has_") or c.startswith("equip_")
              or c in ["n_produits_total", "n_familles_produits"]]

if equip_cols:
    print(f"Colonnes equipements trouvees : {equip_cols}")
    for col in equip_cols:
        if df[col].dtype in [np.float64, np.int64, float, int]:
            non_null = df[col].notna().sum()
            non_zero = (df[col] > 0).sum()
            print(f"  {col}: {non_null} non-null, {non_zero} > 0 ({non_zero/len(df)*100:.1f}%)")
else:
    print("Aucune colonne d'equipement detectee.")
    print("ACTION : verifier si les equipements sont dans un fichier separe.")


# %% ---- CELL 8: Resume et verdict ----

print("\n" + "=" * 60)
print("HA1 — VERDICT")
print("=" * 60)
print("""
Criteres de validation :
  [  ] Moins de 5% de valeurs manquantes sur les colonnes cles
  [  ] Pas de doublons significatifs (< 1%)
  [  ] Dates de creation coherentes (2023-2026)
  [  ] PNB sans outliers extremes inexpliques
  [  ] Segments et professions bien distribues (pas de categorie > 90%)
  [  ] Equipements renseignes pour > 80% des clients

Remplir manuellement apres execution.
""")
