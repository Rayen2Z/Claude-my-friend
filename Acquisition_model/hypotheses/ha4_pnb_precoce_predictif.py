# =============================================================================
# HA4 — Le PNB d'observation est predictif du PNB total
# =============================================================================
#
# C'est l'hypothese FONDAMENTALE du modele. Si le PNB de la fenetre
# d'observation (T→T+1) n'est pas correle au PNB total (T→T+3),
# le modele n'a aucune base.
#
# ATTENTION : pnb_cumul_obs est un sous-ensemble de pnb_total, ce qui cree
# un plancher mecanique de correlation. L'analyse distingue :
#   - HA4a : correlation brute pnb_cumul_obs vs pnb_total (reference)
#   - HA4b : correlation nette pnb_cumul_obs vs pnb_remaining (signal reel)
#
# Analyse :
#   - Correlation PNB 3 mois et PNB obs vs PNB total
#   - Correlation PNB obs vs PNB remaining (au-dela du plancher mecanique)
#   - R2 d'une regression lineaire simple (total et remaining)
#   - Ratio PNB obs / PNB total
#   - Stabilite de la correlation par segment
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
from sklearn.metrics import r2_score, mean_absolute_error


# %% ---- CELL 2: Calculer les PNB cumules si pas deja fait ----

pnb_monthly = [c for c in df.columns if c.startswith("pnb_m") and c[4:].isdigit()]
pnb_monthly = sorted(pnb_monthly, key=lambda x: int(x.split("_m")[1]))

if pnb_monthly:
    print(f"Colonnes PNB mensuelles detectees : {pnb_monthly}")

    if "pnb_cumul_3m" not in df.columns and len(pnb_monthly) >= 3:
        df["pnb_cumul_3m"] = df[pnb_monthly[:3]].sum(axis=1)
    if "pnb_cumul_obs" not in df.columns and len(pnb_monthly) >= 6:
        df["pnb_cumul_obs"] = df[pnb_monthly[:6]].sum(axis=1)
    if "pnb_total" not in df.columns and len(pnb_monthly) >= 10:
        df["pnb_total"] = df[pnb_monthly].sum(axis=1)

print(f"PNB cumul 3m :  {df['pnb_cumul_3m'].mean():,.0f} EUR (moyenne)")
print(f"PNB cumul obs : {df['pnb_cumul_obs'].mean():,.0f} EUR (moyenne)")
print(f"PNB total :     {df['pnb_total'].mean():,.0f} EUR (moyenne)")
if "n_mois_nbi" in df.columns:
    print(f"n_mois_nbi :    {df['n_mois_nbi'].value_counts().sort_index().to_string()}")


# %% ---- CELL 3: Correlations PNB precoce vs PNB 12 mois ----

print("=" * 60)
print("HA4 — CORRELATIONS PNB PRECOCE vs PNB 12 MOIS")
print("=" * 60)

# Pearson correlations
for cumul_col, label in [("pnb_cumul_3m", "3 mois"), ("pnb_cumul_obs", "obs (T+1)")]:
    if cumul_col in df.columns:
        mask = df[cumul_col].notna() & df["pnb_total"].notna()
        r, p = stats.pearsonr(df.loc[mask, cumul_col], df.loc[mask, "pnb_total"])
        rho, p_s = stats.spearmanr(df.loc[mask, cumul_col], df.loc[mask, "pnb_total"])
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
    mask = cumul_n.notna() & df["pnb_total"].notna()
    r, _ = stats.pearsonr(cumul_n[mask], df.loc[mask, "pnb_total"])
    correlations.append({"mois": n, "pearson_r": round(r, 4)})
    print(f"  Mois 1-{n}: r = {r:.4f}")

corr_df = pd.DataFrame(correlations)


# %% ---- CELL 4: Scatter plots ----

fig, axes = plt.subplots(1, 2, figsize=(16, 7))

for ax, col, label in [(axes[0], "pnb_cumul_3m", "3 mois"),
                         (axes[1], "pnb_cumul_obs", "obs (T+1)")]:
    if col in df.columns:
        mask = df[col].notna() & df["pnb_total"].notna()
        x, y = df.loc[mask, col], df.loc[mask, "pnb_total"]

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

for col, label in [("pnb_cumul_3m", "3 mois"), ("pnb_cumul_obs", "obs (T+1)")]:
    if col in df.columns:
        mask = df[col].notna() & df["pnb_total"].notna()
        X_lr = df.loc[mask, col].values.reshape(-1, 1)
        y_lr = df.loc[mask, "pnb_total"].values

        lr = LinearRegression().fit(X_lr, y_lr)
        y_pred = lr.predict(X_lr)

        r2 = r2_score(y_lr, y_pred)
        mae = mean_absolute_error(y_lr, y_pred)

        print(f"\nRegression PNB {label} -> PNB total :")
        print(f"  R2 :  {r2:.4f}")
        print(f"  MAE : {mae:,.0f} EUR")
        print(f"  -> Le PNB {label} seul explique {r2*100:.1f}% de la variance du PNB total")


# %% ---- CELL 6b: HA4b — Correlation nette : pnb_cumul_obs vs pnb_remaining ----

print("\n" + "=" * 60)
print("HA4b — SIGNAL REEL : PNB OBS vs PNB REMAINING")
print("=" * 60)

if "pnb_remaining" in df.columns and "pnb_cumul_obs" in df.columns:
    mask = df["pnb_cumul_obs"].notna() & df["pnb_remaining"].notna()
    r_net, p_net = stats.pearsonr(df.loc[mask, "pnb_cumul_obs"], df.loc[mask, "pnb_remaining"])
    rho_net, p_s_net = stats.spearmanr(df.loc[mask, "pnb_cumul_obs"], df.loc[mask, "pnb_remaining"])

    print(f"\nPNB obs vs PNB remaining (partie non observee) :")
    print(f"  Pearson r  = {r_net:.4f}  (p = {p_net:.2e})")
    print(f"  Spearman rho = {rho_net:.4f}  (p = {p_s_net:.2e})")

    # R2 regression pnb_cumul_obs -> pnb_remaining
    X_rem = df.loc[mask, "pnb_cumul_obs"].values.reshape(-1, 1)
    y_rem = df.loc[mask, "pnb_remaining"].values
    lr_rem = LinearRegression().fit(X_rem, y_rem)
    r2_rem = r2_score(y_rem, lr_rem.predict(X_rem))
    mae_rem = mean_absolute_error(y_rem, lr_rem.predict(X_rem))

    print(f"\nRegression PNB obs -> PNB remaining :")
    print(f"  R2 :  {r2_rem:.4f}")
    print(f"  MAE : {mae_rem:,.0f} EUR")

    # Compare with brute correlation
    r_brut, _ = stats.pearsonr(df.loc[mask, "pnb_cumul_obs"], df.loc[mask, "pnb_total"])
    print(f"\nComparaison :")
    print(f"  r(obs, total)     = {r_brut:.4f}  (inclut le plancher mecanique)")
    print(f"  r(obs, remaining) = {r_net:.4f}  (signal reel)")
    print(f"  -> Le plancher mecanique gonfle la correlation de {r_brut - r_net:+.4f}")

    # Mechanical floor estimate
    if "n_mois_observation" in df.columns and "n_mois_nbi" in df.columns:
        avg_ratio = (df["n_mois_observation"] / df["n_mois_nbi"]).mean()
        print(f"\n  Ratio moyen n_obs/n_nbi = {avg_ratio:.2f}")
        print(f"  Plancher mecanique estime (sqrt) = {np.sqrt(avg_ratio):.3f}")

    # Scatter plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    axes[0].scatter(df.loc[mask, "pnb_cumul_obs"], df.loc[mask, "pnb_total"],
                    alpha=0.15, s=8, color="steelblue")
    axes[0].set_xlabel("PNB obs (EUR)")
    axes[0].set_ylabel("PNB total (EUR)")
    axes[0].set_title(f"PNB obs vs PNB total (r={r_brut:.3f})")
    axes[0].grid(alpha=0.3)

    axes[1].scatter(df.loc[mask, "pnb_cumul_obs"], df.loc[mask, "pnb_remaining"],
                    alpha=0.15, s=8, color="coral")
    axes[1].set_xlabel("PNB obs (EUR)")
    axes[1].set_ylabel("PNB remaining (EUR)")
    axes[1].set_title(f"PNB obs vs PNB remaining (r={r_net:.3f})")
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.show()

else:
    print("Colonnes pnb_remaining ou pnb_cumul_obs manquantes.")
    print("Executer data_preparation.ipynb pour generer pnb_remaining.")


# %% ---- CELL 7: Ratio PNB precoce / PNB total ----

print("\n" + "=" * 60)
print("HA4 — RATIO PNB OBS / PNB TOTAL")
print("=" * 60)

for col, label in [("pnb_cumul_3m", "3 mois"), ("pnb_cumul_obs", "obs (T+1)")]:
    if col in df.columns:
        mask = (df["pnb_total"] > 0) & df[col].notna()
        ratio = df.loc[mask, col] / df.loc[mask, "pnb_total"]

        print(f"\nRatio PNB {label} / PNB total (clients PNB > 0) :")
        print(f"  Mean :   {ratio.mean():.2%}")
        print(f"  Median : {ratio.median():.2%}")
        print(f"  Std :    {ratio.std():.2%}")

        if label == "obs (T+1)":
            print(f"  -> En moyenne, {ratio.mean():.0%} du PNB total est realise dans la fenetre d'observation")


# %% ---- CELL 8: Stabilite par segment ----

print("\n" + "=" * 60)
print("HA4 — CORRELATION PAR SEGMENT")
print("=" * 60)

if "segment" in df.columns and "pnb_cumul_obs" in df.columns:
    for seg in sorted(df["segment"].unique()):
        seg_df = df[df["segment"] == seg]
        mask = seg_df["pnb_cumul_obs"].notna() & seg_df["pnb_total"].notna()
        if mask.sum() > 10:
            r, p = stats.pearsonr(seg_df.loc[mask, "pnb_cumul_obs"],
                                   seg_df.loc[mask, "pnb_total"])
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
  Correlation PNB obs vs total :       r = ____
  Correlation PNB obs vs remaining :   r = ____ (signal reel)
  R2 regression obs -> total :         ____
  R2 regression obs -> remaining :     ____
  Ratio moyen PNB obs / PNB total :    ____%

  HA4 VALIDEE si :
    - r(obs, total) > 0.60
    - r(obs, remaining) > 0.30 (au-dela du plancher mecanique)
    - R2(remaining) > 0.10
    - Correlation stable entre segments

  Conclusion : [VALIDEE / PARTIELLEMENT / NON VALIDEE]
""")
