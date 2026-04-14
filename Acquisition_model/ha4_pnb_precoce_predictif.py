# =============================================================================
# HA4 — Le PNB des 3-6 premiers mois est predictif du PNB a 12 mois
# =============================================================================
#
# C'est l'hypothese FONDAMENTALE du modele. Si le PNB precoce n'est pas
# correle au PNB a 12 mois, le modele n'a aucune base.
#
# Analyse :
#   - Correlation PNB 3 mois vs PNB 12 mois
#   - Correlation PNB 6 mois vs PNB 12 mois
#   - R2 d'une regression lineaire simple
#   - Ratio PNB precoce / PNB 12 mois
#   - Stabilite de la correlation par segment
#
# Prerequis : df avec pnb_m1..pnb_m12, pnb_12m_total, pnb_cumul_3m, pnb_cumul_6m
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error


# %% ---- CELL 2: Calculer les PNB cumules si pas deja fait ----

pnb_monthly = [c for c in df.columns if c.startswith("pnb_m") and c[4:].isdigit()]
pnb_monthly = sorted(pnb_monthly, key=lambda x: int(x.split("_m")[1]))

if pnb_monthly:
    print(f"Colonnes PNB mensuelles detectees : {pnb_monthly}")

    # Cumul 3 mois
    if len(pnb_monthly) >= 3:
        df["pnb_cumul_3m"] = df[pnb_monthly[:3]].sum(axis=1)
    # Cumul 6 mois
    if len(pnb_monthly) >= 6:
        df["pnb_cumul_6m"] = df[pnb_monthly[:6]].sum(axis=1)
    # Total 12 mois
    if len(pnb_monthly) >= 12 and "pnb_12m_total" not in df.columns:
        df["pnb_12m_total"] = df[pnb_monthly[:12]].sum(axis=1)

print(f"PNB cumul 3m : {df['pnb_cumul_3m'].mean():,.0f} EUR (moyenne)")
print(f"PNB cumul 6m : {df['pnb_cumul_6m'].mean():,.0f} EUR (moyenne)")
print(f"PNB total 12m: {df['pnb_12m_total'].mean():,.0f} EUR (moyenne)")


# %% ---- CELL 3: Correlations PNB precoce vs PNB 12 mois ----

print("=" * 60)
print("HA4 — CORRELATIONS PNB PRECOCE vs PNB 12 MOIS")
print("=" * 60)

# Pearson correlations
for cumul_col, label in [("pnb_cumul_3m", "3 mois"), ("pnb_cumul_6m", "6 mois")]:
    if cumul_col in df.columns:
        mask = df[cumul_col].notna() & df["pnb_12m_total"].notna()
        r, p = stats.pearsonr(df.loc[mask, cumul_col], df.loc[mask, "pnb_12m_total"])
        rho, p_s = stats.spearmanr(df.loc[mask, cumul_col], df.loc[mask, "pnb_12m_total"])
        print(f"\nPNB {label} vs PNB 12 mois :")
        print(f"  Pearson r  = {r:.4f}  (p = {p:.2e})")
        print(f"  Spearman rho = {rho:.4f}  (p = {p_s:.2e})")

        if r > 0.7:
            print(f"  -> Correlation forte : le PNB {label} est un excellent predicteur")
        elif r > 0.5:
            print(f"  -> Correlation moderee-forte : bon signal")
        elif r > 0.3:
            print(f"  -> Correlation moderee : signal utile mais insuffisant seul")
        else:
            print(f"  -> Correlation faible : le PNB {label} seul ne suffit pas")

# Monthly correlations (progressive)
print("\nCorrelation progressive (PNB cumule du mois 1 au mois N vs PNB 12 mois) :")
correlations = []
for n in range(1, min(7, len(pnb_monthly) + 1)):
    cumul_n = df[pnb_monthly[:n]].sum(axis=1)
    mask = cumul_n.notna() & df["pnb_12m_total"].notna()
    r, _ = stats.pearsonr(cumul_n[mask], df.loc[mask, "pnb_12m_total"])
    correlations.append({"mois": n, "pearson_r": round(r, 4)})
    print(f"  Mois 1-{n}: r = {r:.4f}")

corr_df = pd.DataFrame(correlations)


# %% ---- CELL 4: Scatter plots ----

fig, axes = plt.subplots(1, 2, figsize=(16, 7))

for ax, col, label in [(axes[0], "pnb_cumul_3m", "3 mois"),
                         (axes[1], "pnb_cumul_6m", "6 mois")]:
    if col in df.columns:
        mask = df[col].notna() & df["pnb_12m_total"].notna()
        x, y = df.loc[mask, col], df.loc[mask, "pnb_12m_total"]

        ax.scatter(x, y, alpha=0.15, s=8, color="steelblue")

        # Regression line
        slope, intercept, r, p, se = stats.linregress(x, y)
        x_line = np.linspace(x.min(), x.max(), 100)
        ax.plot(x_line, slope * x_line + intercept, "r-", lw=2,
                label=f"y = {slope:.2f}x + {intercept:.0f}\nr = {r:.3f}")

        # Perfect predictor line (if 6m was exactly half of 12m)
        ax.plot(x_line, x_line * 2, "--", color="gray", alpha=0.5, label="x2 (reference)")

        ax.set_xlabel(f"PNB cumule {label} (EUR)")
        ax.set_ylabel("PNB 12 mois (EUR)")
        ax.set_title(f"PNB {label} vs PNB 12 mois")
        ax.legend()
        ax.grid(alpha=0.3)

plt.tight_layout()
plt.show()


# %% ---- CELL 5: Correlation progressive — plot ----

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(corr_df["mois"], corr_df["pearson_r"], "o-", lw=2, markersize=8, color="steelblue")
ax.set_xlabel("Nombre de mois de PNB cumule")
ax.set_ylabel("Correlation Pearson avec PNB 12 mois")
ax.set_title("Gain de correlation en ajoutant des mois de PNB")
ax.set_xticks(corr_df["mois"])
ax.set_ylim(0, 1)
ax.grid(alpha=0.3)
ax.axhline(0.7, color="green", ls="--", alpha=0.5, label="Seuil bon (r=0.7)")
ax.axhline(0.5, color="orange", ls="--", alpha=0.5, label="Seuil modere (r=0.5)")
ax.legend()
plt.tight_layout()
plt.show()


# %% ---- CELL 6: R2 d'une regression simple ----

print("\n" + "=" * 60)
print("HA4 — REGRESSION LINEAIRE SIMPLE")
print("=" * 60)

for col, label in [("pnb_cumul_3m", "3 mois"), ("pnb_cumul_6m", "6 mois")]:
    if col in df.columns:
        mask = df[col].notna() & df["pnb_12m_total"].notna()
        X_lr = df.loc[mask, col].values.reshape(-1, 1)
        y_lr = df.loc[mask, "pnb_12m_total"].values

        lr = LinearRegression().fit(X_lr, y_lr)
        y_pred = lr.predict(X_lr)

        r2 = r2_score(y_lr, y_pred)
        mae = mean_absolute_error(y_lr, y_pred)

        print(f"\nRegression PNB {label} -> PNB 12 mois :")
        print(f"  R2 :  {r2:.4f}")
        print(f"  MAE : {mae:,.0f} EUR")
        print(f"  -> Le PNB {label} seul explique {r2*100:.1f}% de la variance du PNB 12 mois")


# %% ---- CELL 7: Ratio PNB precoce / PNB 12 mois ----

print("\n" + "=" * 60)
print("HA4 — RATIO PNB PRECOCE / PNB 12 MOIS")
print("=" * 60)

for col, label in [("pnb_cumul_3m", "3 mois"), ("pnb_cumul_6m", "6 mois")]:
    if col in df.columns:
        mask = (df["pnb_12m_total"] > 0) & df[col].notna()
        ratio = df.loc[mask, col] / df.loc[mask, "pnb_12m_total"]

        print(f"\nRatio PNB {label} / PNB 12 mois (clients PNB > 0) :")
        print(f"  Mean :   {ratio.mean():.2%}")
        print(f"  Median : {ratio.median():.2%}")
        print(f"  Std :    {ratio.std():.2%}")

        if label == "6 mois":
            print(f"  -> En moyenne, {ratio.mean():.0%} du PNB 12 mois est realise dans les 6 premiers mois")


# %% ---- CELL 8: Stabilite par segment ----

print("\n" + "=" * 60)
print("HA4 — CORRELATION PAR SEGMENT")
print("=" * 60)

if "segment" in df.columns and "pnb_cumul_6m" in df.columns:
    for seg in sorted(df["segment"].unique()):
        seg_df = df[df["segment"] == seg]
        mask = seg_df["pnb_cumul_6m"].notna() & seg_df["pnb_12m_total"].notna()
        if mask.sum() > 10:
            r, p = stats.pearsonr(seg_df.loc[mask, "pnb_cumul_6m"],
                                   seg_df.loc[mask, "pnb_12m_total"])
            print(f"  {seg}: r = {r:.4f} (n={mask.sum()}, p={p:.2e})")

    print("\n  -> Si les correlations sont stables entre segments,")
    print("     un modele unifie est justifie.")
    print("  -> Si elles varient fortement, envisager des sous-modeles par segment.")


# %% ---- CELL 9: Verdict ----

print("\n" + "=" * 60)
print("HA4 — VERDICT")
print("=" * 60)
print("""
A remplir :
  Correlation PNB 3m vs 12m :  r = ____
  Correlation PNB 6m vs 12m :  r = ____
  R2 regression simple 6m :    ____
  Ratio moyen PNB 6m / 12m :   ____%

  HA4 VALIDEE si :
    - r(6m, 12m) > 0.60
    - R2 > 0.30
    - Correlation stable entre segments

  Conclusion : [VALIDEE / PARTIELLEMENT / NON VALIDEE]
""")
