# %% [markdown]
# # Youngsters (< 25) — acquisition volumes & NBI
# Panel: one row per client per period, 2021 → Jul 2026.
# 1. Acquisitions per year per tranche d'âge + projection 2026 (full year) and 2027
# 2. Average NBI per year for clients aged [18, 25)

# %%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PATH = "stock_youngsters.xlsx"          # or .csv

COL_ID     = "Identifiant Tiers"
COL_PERIOD = "Periode"                   # snapshot period of the row
COL_YACQ   = "Annee acquisition"
COL_AGE    = "Age"
COL_NBI    = "NBI"

CUR_YEAR   = 2026
MONTHS_YTD = 7                           # data stops at July 2026
MIN_MOIS   = 2                           # drop client-years with fewer months (noisy run rate)

df = pd.read_excel(PATH)                 # pd.read_csv(PATH, sep=";", decimal=",")
df.columns = df.columns.str.strip()
print(df.shape)
df.head()

# %% [markdown]
# ## Cleaning

# %%
def to_year(s):
    """Accept datetime, 2026, 202607, '2026-07' ..."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.year
    v = pd.to_numeric(s, errors="coerce")
    if v.notna().mean() > 0.95:
        return np.where(v > 9999, v // 100, v).astype("Int64")
    return pd.to_datetime(s, errors="coerce").dt.year

df["period_year"] = to_year(df[COL_PERIOD])
df["year_acq"]    = pd.to_numeric(df[COL_YACQ], errors="coerce").astype("Int64")
df[COL_AGE]       = pd.to_numeric(df[COL_AGE], errors="coerce")
df[COL_NBI]       = pd.to_numeric(df[COL_NBI], errors="coerce")

df = df.dropna(subset=[COL_ID, "year_acq", COL_AGE])
df = df[df["year_acq"].between(2021, CUR_YEAR)]

print(df.groupby("period_year").size())          # sanity: rows per period
print(df[COL_AGE].describe())

# %% [markdown]
# ## 1. Acquisitions per year per tranche
# One row per client = his earliest observation, so age is the age at acquisition.

# %%
BINS   = [0, 12, 18, 25, np.inf]
LABELS = ["0-12", "12-18", "18-25", "25+"]

acq = (df.sort_values([COL_ID, "period_year"])
         .drop_duplicates(subset=COL_ID, keep="first")
         .copy())
acq["tranche"] = pd.cut(acq[COL_AGE], bins=BINS, labels=LABELS, right=False)

print("hors périmètre (>=25 à l'acquisition):", (acq["tranche"] == "25+").sum())
acq = acq[acq["tranche"] != "25+"]

vol = (acq.pivot_table(index="year_acq", columns="tranche",
                       values=COL_ID, aggfunc="count", observed=True)
          .reindex(range(2021, CUR_YEAR + 1))
          .fillna(0).astype(int))
vol["TOTAL"] = vol.sum(axis=1)
vol

# %% [markdown]
# ## Projection
# 2026 full year = YTD x 12/7 (assumes flat seasonality — check monthly if it matters).
# 2027 from a linear trend on 2021→2026e, with a 3-year CAGR as a second opinion.

# %%
scale = 12 / MONTHS_YTD
proj = vol.copy().astype(float)
proj.loc[CUR_YEAR] = (proj.loc[CUR_YEAR] * scale).round()

def linear_2027(col):
    x = proj.index.values.astype(float)
    a, b = np.polyfit(x, col.values, 1)
    return max(a * 2027 + b, 0)

def cagr_2027(col):
    v = col.values
    g = (v[-1] / v[-4]) ** (1 / 3) - 1 if v[-4] > 0 else 0   # 2023 -> 2026e
    return max(v[-1] * (1 + g), 0)

summary = pd.DataFrame({
    f"{CUR_YEAR} YTD ({MONTHS_YTD}m)": vol.loc[CUR_YEAR],
    f"{CUR_YEAR}e full year":          proj.loc[CUR_YEAR].round(),
    "2027 (trend)":                    proj.apply(linear_2027).round(),
    "2027 (CAGR 3y)":                  proj.apply(cagr_2027).round(),
})
summary

# %%
ax = proj.drop(columns="TOTAL").plot(marker="o", figsize=(9, 5))
ax.axvline(CUR_YEAR - 0.5, ls="--", c="grey", lw=1)
ax.set_title("Acquisitions youngsters par tranche d'âge (2026 annualisé)")
ax.set_ylabel("nb clients"); ax.set_xlabel("année d'acquisition")
plt.tight_layout(); plt.show()

# %% [markdown]
# ## 2. NBI — clients aged [18, 25)
# NBI is monthly, so: sum per client x year, then average across clients.
# `mois` = months actually observed in the band that year — handles acquisition
# mid-year, the 25th birthday, and the 7-month 2026 in one go.

# %%
band = df[(df[COL_AGE] >= 18) & (df[COL_AGE] < 25)].copy()

cy = (band.groupby([COL_ID, "period_year"])
          .agg(nbi_annee=(COL_NBI, "sum"), mois=(COL_PERIOD, "nunique"))
          .reset_index())
cy["nbi_run_rate"] = cy["nbi_annee"] / cy["mois"] * 12

print("client-années écartées (< MIN_MOIS):", (cy["mois"] < MIN_MOIS).sum())
cy = cy[cy["mois"] >= MIN_MOIS]

nbi = (cy.groupby("period_year")
         .agg(nb_clients=(COL_ID, "nunique"),
              mois_moyen=("mois", "mean"),
              nbi_total=("nbi_annee", "sum"),
              nbi_moyen_observe=("nbi_annee", "mean"),      # ce qui a réellement été encaissé
              nbi_moyen_annualise=("nbi_run_rate", "mean"), # comparable entre années
              nbi_median_annualise=("nbi_run_rate", "median"))
         .round(1))
nbi["evol_%"] = (nbi["nbi_moyen_annualise"].pct_change() * 100).round(1)
nbi

# %%
fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(nbi.index, nbi["nbi_moyen_annualise"], color="#4C72B0")
ax.set_title("NBI moyen annualisé par client 18-24 ans")
ax.set_ylabel("NBI / an"); ax.set_xlabel("année")
plt.tight_layout(); plt.show()

# %% [markdown]
# ## Bonus — NBI par âge (toutes années confondues)
# Shows the ramp as they age, which the yearly average hides.

# %%
ba = band.copy()
ba["age_int"] = ba[COL_AGE].astype(int)

ca = (ba.groupby([COL_ID, "age_int"])
        .agg(nbi=(COL_NBI, "sum"), mois=(COL_PERIOD, "nunique"))
        .reset_index())
ca = ca[ca["mois"] >= MIN_MOIS]
ca["run_rate"] = ca["nbi"] / ca["mois"] * 12

by_age = (ca.groupby("age_int")
            .agg(nb_clients=(COL_ID, "nunique"),
                 nbi_moyen_annualise=("run_rate", "mean"),
                 nbi_median_annualise=("run_rate", "median"))
            .round(1))
by_age
