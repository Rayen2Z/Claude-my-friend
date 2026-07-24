"""
Délai moyen entre la ligne principale (acquisition/construction) et la ligne
de rénovation verte, au niveau du dossier de crédit (Contrat Principal).

Input : df avec les colonnes
    Identifiant Tiers | Réf. Contrat | Date d'ouverture | Destination du crédit | Contrat Principal
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- parameters
MAIN_DEST = {
    "ACQUIS. MAISON UNIF.",
    "ACQUIS.LOG.BATIMENT COLL.",
    "CONSTR. MAISON UNIF.",
    "AUTRES C.IMM/TERRAIN",
}
GREEN_DEST = {
    "IMMO CLIMATIQUE SUB INTER",
    "RENOVATION ENERGETIQUE",
}

KEY = ["Identifiant Tiers", "Contrat Principal", "Date d'ouverture", "dest"]


# ------------------------------------------------------------------ cleaning
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["Date d'ouverture"] = pd.to_datetime(d["Date d'ouverture"], errors="coerce")
    # normalise the label so trailing spaces / casing don't break the matching
    d["dest"] = (
        d["Destination du crédit"]
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\s+", " ", regex=True)
    )
    d = d.dropna(subset=["Date d'ouverture", "Contrat Principal"])
    return d


def dedupe(d: pd.DataFrame) -> pd.DataFrame:
    """
    Same client + same folder + same date + same destination = duplicate,
    UNLESS the rows carry different (non-null) contract references, which means
    the client really took two loans of the same type on the same day.

    Rule applied:
      1. inside such a group, if at least one row has a Réf. Contrat, the rows
         with a missing reference are dropped (they are the un-referenced echo
         of the same line);
      2. what remains is deduplicated on the reference itself (rows with a
         missing reference collapse into a single one).
    """
    d = d.copy()
    d["has_ref"] = d["Réf. Contrat"].notna()
    keep = d["has_ref"] | ~d.groupby(KEY, dropna=False)["has_ref"].transform("any")
    d = d[keep]
    d = d.drop_duplicates(subset=KEY + ["Réf. Contrat"])
    return d.drop(columns="has_ref")


def tag_roles(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["role"] = np.select(
        [d["dest"].isin(MAIN_DEST), d["dest"].isin(GREEN_DEST)],
        ["main", "green"],
        default="other",
    )
    return d.sort_values(["Contrat Principal", "Date d'ouverture", "dest"])


# ------------------------------------------------------------------- pairing
def build_pairs(d: pd.DataFrame) -> pd.DataFrame:
    """One row per dossier: main line date + first / last green line date."""
    main = (
        d[d["role"] == "main"]
        .groupby("Contrat Principal")
        .agg(
            date_main=("Date d'ouverture", "min"),
            dest_main=("dest", "first"),
            n_main=("dest", "size"),
            tiers=("Identifiant Tiers", "first"),
        )
    )
    green = (
        d[d["role"] == "green"]
        .groupby("Contrat Principal")
        .agg(
            date_green_first=("Date d'ouverture", "min"),
            date_green_last=("Date d'ouverture", "max"),
            n_green=("dest", "size"),
        )
    )
    pairs = main.join(green, how="inner").reset_index()
    pairs["delai_jours"] = (pairs["date_green_first"] - pairs["date_main"]).dt.days
    pairs["delai_annees"] = pairs["delai_jours"] / 365.25
    return pairs.sort_values("delai_jours")


def build_pairs_all_green(d: pd.DataFrame) -> pd.DataFrame:
    """One row per green line (a dossier with 2 green lines counts twice)."""
    main = (
        d[d["role"] == "main"]
        .groupby("Contrat Principal")["Date d'ouverture"]
        .min()
        .rename("date_main")
    )
    g = d[d["role"] == "green"].merge(main, on="Contrat Principal", how="inner")
    g["delai_jours"] = (g["Date d'ouverture"] - g["date_main"]).dt.days
    return g


# ---------------------------------------------------------------------- main
def run(df: pd.DataFrame):
    d = tag_roles(dedupe(prepare(df)))
    pairs = build_pairs(d)

    n_folders = d["Contrat Principal"].nunique()
    n_green_folders = d.loc[d["role"] == "green", "Contrat Principal"].nunique()
    negatives = pairs[pairs["delai_jours"] < 0]
    clean = pairs[pairs["delai_jours"] >= 0]

    print(f"Dossiers                              : {n_folders}")
    print(f"Dossiers avec une ligne verte         : {n_green_folders}")
    print(f"Dossiers appariés (principale + verte): {len(pairs)}")
    print(f"  dont délai négatif (verte avant)    : {len(negatives)}")
    print()
    print("Délai principale -> 1ère ligne verte (jours)")
    print(clean["delai_jours"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]))
    print()
    print(f"Moyenne : {clean['delai_jours'].mean():.0f} j "
          f"({clean['delai_annees'].mean():.1f} ans)")
    print(f"Médiane : {clean['delai_jours'].median():.0f} j")

    # délai moyen par type de ligne principale
    print()
    print(clean.groupby("dest_main")["delai_jours"].agg(["size", "mean", "median"]))

    return d, pairs


# df = pd.read_excel(".../Renov energitique.xlsx", sheet_name="credit_immo_delais")
# d, pairs = run(df)
