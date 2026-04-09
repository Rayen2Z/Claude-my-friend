# =============================================================================
# DATA PREPARATION — New Client Acquisition CLV Model
# =============================================================================
#
# Shared data preparation for both Proposition A and Proposition B.
# Identifies new client cohorts from Stock files, builds training sets
# with sign-up features and 12-month PNB/churn outcomes.
#
# Prerequisite: Stock CSV files in CHURN_YYYY folders with client_id
#   and optionally demographic/product columns.
#
# Luxembourg context: clients include residents + frontaliers (FR/BE/DE).
# Geographic enrichment uses STATEC data, not INSEE.
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
import os
from pathlib import Path


# %% ---- CELL 2: Configuration ----

BASE_PATH = Path("../")  # adjust to your repo root

CHURN_FOLDERS = {
    2023: BASE_PATH / "CHURN_2023",
    2024: BASE_PATH / "CHURN_2024",
    2025: BASE_PATH / "CHURN_2025",
}

# Column name detection (flexible)
CLIENT_ID_CANDIDATES = [
    "client_id", "clientid", "id_client", "customer_id",
    "cust_id", "id", "no_client", "num_client",
]

# Known demographic columns (will be used if present in Stock CSVs)
DEMOGRAPHIC_COLS = [
    "age", "genre", "gender", "date_naissance", "date_of_birth",
    "situation_familiale", "family_situation",
    "nationalite", "nationality",
    "pays_residence", "country_of_residence",
    "est_frontalier", "is_cross_border",
]

DECLARATIVE_COLS = [
    "tranche_revenu", "income_range", "revenu_declare",
    "csp_category", "csp", "profession",
]

PRODUCT_COLS = [
    "has_compte_courant", "has_compte_epargne", "has_assurance_vie",
    "has_credit_immobilier", "has_credit_conso", "has_carte_bancaire",
    "has_assurance_habitation", "has_assurance_auto", "has_prevoyance",
]

CHANNEL_COLS = [
    "canal", "channel", "canal_digital", "channel_online",
]

NBI_COLS = [
    "nbi_annual", "pnb_annuel", "nbi_q1", "nbi_q2", "nbi_q3", "nbi_q4",
    "pnb_q1", "pnb_q2", "pnb_q3", "pnb_q4",
]


# %% ---- CELL 3: Helper — detect client_id column ----

def detect_client_id_col(df):
    """Auto-detect the client ID column name."""
    for col in CLIENT_ID_CANDIDATES:
        if col in df.columns:
            return col
    for col in df.columns:
        if "client" in col.lower() or "cust" in col.lower() or col.lower() == "id":
            return col
    raise ValueError(f"Cannot detect client_id column. Columns: {list(df.columns)}")


def standardize_client_id(df, id_col):
    """Clean and standardize the client ID column."""
    df = df.copy()
    df["client_id"] = df[id_col].astype(str).str.strip()
    df = df[df["client_id"].notna() & (df["client_id"] != "")]
    df = df.drop_duplicates(subset=["client_id"], keep="first")
    return df


# %% ---- CELL 4: Load Stock files for a given year ----

def load_stock(folder, filename_pattern=None):
    """Load a Stock CSV file from a folder. Tries multiple encodings."""
    folder = Path(folder)
    csv_files = list(folder.glob("*.csv"))

    if filename_pattern:
        csv_files = [f for f in csv_files if filename_pattern.lower() in f.name.lower()]

    if not csv_files:
        print(f"  WARNING: No CSV files found in {folder}")
        return pd.DataFrame()

    for f in csv_files:
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                df = pd.read_csv(f, encoding=enc, sep=None, engine="python")
                if len(df) > 0:
                    print(f"  Loaded {f.name}: {len(df)} rows, encoding={enc}")
                    return df
            except Exception:
                continue

    print(f"  WARNING: Could not read any CSV in {folder}")
    return pd.DataFrame()


# %% ---- CELL 5: Identify new client cohorts ----

def identify_new_clients(year):
    """
    Identify clients who are NEW in year Y:
    - Present in Stock Y+1 but NOT in Stock Y
    - This means they were acquired during year Y

    Returns a DataFrame of new client IDs with their year of acquisition.
    """
    folder = CHURN_FOLDERS.get(year)
    if folder is None or not folder.exists():
        print(f"  Folder for {year} not found: {folder}")
        return pd.DataFrame()

    # Load Stock Y (beginning of year) and Stock Y+1 (beginning of next year)
    stock_y = load_stock(folder, f"stock {year}")
    if stock_y.empty:
        stock_y = load_stock(folder, str(year))

    stock_y1 = load_stock(folder, f"stock {year + 1}")
    if stock_y1.empty:
        stock_y1 = load_stock(folder, str(year + 1))

    if stock_y.empty or stock_y1.empty:
        print(f"  Cannot identify new clients for {year}: missing Stock files")
        return pd.DataFrame()

    # Standardize IDs
    id_col_y = detect_client_id_col(stock_y)
    id_col_y1 = detect_client_id_col(stock_y1)

    stock_y = standardize_client_id(stock_y, id_col_y)
    stock_y1 = standardize_client_id(stock_y1, id_col_y1)

    # New clients = in Stock Y+1 but NOT in Stock Y
    ids_y = set(stock_y["client_id"].unique())
    ids_y1 = set(stock_y1["client_id"].unique())
    new_ids = ids_y1 - ids_y

    print(f"\n  Year {year}: {len(ids_y)} existing | {len(ids_y1)} next year | {len(new_ids)} NEW clients")

    # Build new clients DataFrame from Stock Y+1 (their first appearance)
    new_clients = stock_y1[stock_y1["client_id"].isin(new_ids)].copy()
    new_clients["acquisition_year"] = year

    return new_clients


# %% ---- CELL 6: Build churn flag for new clients ----

def add_churn_flag(new_clients_df, acquisition_year):
    """
    For new clients acquired in year Y, check if they are still present
    in Stock Y+2 (i.e., did they survive 12 months?).

    Also checks the Upstreaming file to exclude VIP migrations.
    """
    next_year = acquisition_year + 1
    next_folder = CHURN_FOLDERS.get(next_year)

    if next_folder is None or not next_folder.exists():
        print(f"  Cannot compute churn for cohort {acquisition_year}: no folder for {next_year}")
        new_clients_df["churned_year1"] = np.nan
        new_clients_df["is_upstreamed"] = 0
        return new_clients_df

    # Load Stock Y+2
    stock_y2 = load_stock(next_folder, f"stock {next_year + 1}")
    if stock_y2.empty:
        stock_y2 = load_stock(next_folder, str(next_year + 1))

    # Load upstreaming
    upstream = load_stock(next_folder, "upstream")

    df = new_clients_df.copy()

    if not stock_y2.empty:
        id_col = detect_client_id_col(stock_y2)
        stock_y2 = standardize_client_id(stock_y2, id_col)
        ids_y2 = set(stock_y2["client_id"].unique())
        df["in_stock_y2"] = df["client_id"].isin(ids_y2).astype(int)
    else:
        df["in_stock_y2"] = np.nan

    if not upstream.empty:
        id_col = detect_client_id_col(upstream)
        upstream = standardize_client_id(upstream, id_col)
        upstream_ids = set(upstream["client_id"].unique())
        df["is_upstreamed"] = df["client_id"].isin(upstream_ids).astype(int)
    else:
        df["is_upstreamed"] = 0

    # Churned = not in Stock Y+2 AND not upstreamed
    if "in_stock_y2" in df.columns and df["in_stock_y2"].notna().any():
        df["churned_year1"] = ((df["in_stock_y2"] == 0) & (df["is_upstreamed"] == 0)).astype(int)
    else:
        df["churned_year1"] = np.nan

    df = df.drop(columns=["in_stock_y2"], errors="ignore")
    return df


# %% ---- CELL 7: Extract available features from Stock columns ----

def extract_signup_features(df):
    """
    Extract demographic, declarative, product, and channel features
    from the columns available in the Stock CSV.
    Returns the DataFrame with standardized feature names.
    """
    features = df.copy()

    # --- Age ---
    if "age" in features.columns:
        features["age"] = pd.to_numeric(features["age"], errors="coerce")
    elif "date_naissance" in features.columns or "date_of_birth" in features.columns:
        dob_col = "date_naissance" if "date_naissance" in features.columns else "date_of_birth"
        features[dob_col] = pd.to_datetime(features[dob_col], errors="coerce")
        acq_year = features["acquisition_year"].iloc[0] if "acquisition_year" in features.columns else 2024
        features["age"] = acq_year - features[dob_col].dt.year

    # --- Gender ---
    for col in ["genre", "gender"]:
        if col in features.columns:
            features["genre_encoded"] = features[col].map(
                {"M": 0, "F": 1, "m": 0, "f": 1, "H": 0, "Homme": 0, "Femme": 1}
            ).fillna(0).astype(int)
            break

    # --- Income range encoding (Luxembourg brackets) ---
    INCOME_MIDPOINTS = {
        "0-30k": 15000, "0-30K": 15000, "<30k": 15000, "<30K": 15000,
        "30-50k": 40000, "30-50K": 40000, "30k-50k": 40000,
        "50-80k": 65000, "50-80K": 65000, "50k-80k": 65000,
        "80-120k": 100000, "80-120K": 100000, "80k-120k": 100000,
        "120k+": 140000, ">120k": 140000, ">120K": 140000,
    }
    for col in ["tranche_revenu", "income_range"]:
        if col in features.columns:
            features["income_midpoint"] = features[col].map(INCOME_MIDPOINTS)
            if features["income_midpoint"].isna().all():
                features["income_midpoint"] = pd.to_numeric(features[col], errors="coerce")
            break

    # --- CSP one-hot encoding ---
    for col in ["csp_category", "csp", "profession"]:
        if col in features.columns:
            csp_dummies = pd.get_dummies(features[col], prefix="csp", dummy_na=False)
            features = pd.concat([features, csp_dummies], axis=1)
            break

    # --- Nationality ---
    for col in ["nationalite", "nationality"]:
        if col in features.columns:
            nat_dummies = pd.get_dummies(features[col], prefix="nat", dummy_na=False)
            features = pd.concat([features, nat_dummies], axis=1)
            break

    # --- Frontalier flag ---
    for col in ["est_frontalier", "is_cross_border"]:
        if col in features.columns:
            features["est_frontalier"] = features[col].astype(int)
            break

    # --- Channel ---
    for col in ["canal_digital", "channel_online", "canal", "channel"]:
        if col in features.columns:
            if features[col].dtype == object:
                features["canal_digital"] = features[col].isin(
                    ["digital", "online", "app", "web", "mobile"]
                ).astype(int)
            else:
                features["canal_digital"] = features[col].astype(int)
            break

    # --- Product flags ---
    product_flags = [c for c in PRODUCT_COLS if c in features.columns]
    if product_flags:
        for pf in product_flags:
            features[pf] = features[pf].astype(int)

        features["n_produits_onboarding"] = features[product_flags].sum(axis=1)

        # Product family aggregates
        everyday_cols = [c for c in ["has_compte_courant", "has_carte_bancaire"] if c in features.columns]
        savings_cols = [c for c in ["has_compte_epargne", "has_assurance_vie"] if c in features.columns]
        lending_cols = [c for c in ["has_credit_immobilier", "has_credit_conso"] if c in features.columns]
        insurance_cols = [c for c in ["has_assurance_habitation", "has_assurance_auto", "has_prevoyance"] if c in features.columns]

        features["fam_banque_quotidienne"] = (features[everyday_cols].sum(axis=1) > 0).astype(int) if everyday_cols else 0
        features["fam_epargne_investissement"] = (features[savings_cols].sum(axis=1) > 0).astype(int) if savings_cols else 0
        features["fam_credit"] = (features[lending_cols].sum(axis=1) > 0).astype(int) if lending_cols else 0
        features["fam_assurance_protection"] = (features[insurance_cols].sum(axis=1) > 0).astype(int) if insurance_cols else 0

        fam_cols = ["fam_banque_quotidienne", "fam_epargne_investissement", "fam_credit", "fam_assurance_protection"]
        features["n_familles_produits"] = features[fam_cols].sum(axis=1)

    # --- Situation familiale one-hot ---
    for col in ["situation_familiale", "family_situation"]:
        if col in features.columns:
            sit_dummies = pd.get_dummies(features[col], prefix="sit_fam", dummy_na=False)
            features = pd.concat([features, sit_dummies], axis=1)
            break

    return features


# %% ---- CELL 8: STATEC geographic enrichment ----

def load_statec_commune_data(statec_csv_path=None):
    """
    Load STATEC commune-level data for geographic enrichment.

    Expected columns in the STATEC CSV:
      - code_commune (or code_postal)
      - revenu_median (median disposable income, EUR)
      - densite_population (inhabitants/km2)
      - taux_chomage (unemployment rate, %)
      - categorie_urbaine (urban/periurban/rural)
      - pib_par_habitant (GDP per capita of canton)
      - pct_frontaliers (% cross-border workers)

    If no file provided, returns an empty DataFrame (features will be NaN).
    Download from: https://data.public.lu or https://statistiques.public.lu
    """
    if statec_csv_path is None or not Path(statec_csv_path).exists():
        print("  STATEC data not found. Geographic features will be NaN.")
        print("  To enable: download commune data from https://data.public.lu")
        return pd.DataFrame()

    statec = pd.read_csv(statec_csv_path, sep=None, engine="python")
    print(f"  Loaded STATEC data: {len(statec)} communes, columns: {list(statec.columns)}")
    return statec


def enrich_with_geography(df, statec_df, join_col="code_postal"):
    """
    Join client data with STATEC commune-level statistics.
    Adds geographic features to the DataFrame.
    """
    if statec_df.empty:
        df["revenu_median_commune"] = np.nan
        df["densite_population"] = np.nan
        df["taux_chomage_canton"] = np.nan
        df["categorie_urbaine_encoded"] = np.nan
        df["pib_par_habitant_canton"] = np.nan
        df["pct_frontaliers_commune"] = np.nan
        return df

    if join_col not in df.columns:
        print(f"  WARNING: {join_col} not in client data. Skipping geographic enrichment.")
        return df

    geo_cols = ["revenu_median", "densite_population", "taux_chomage",
                "categorie_urbaine", "pib_par_habitant", "pct_frontaliers"]
    available_geo = [c for c in geo_cols if c in statec_df.columns]

    if join_col in statec_df.columns:
        df = df.merge(
            statec_df[[join_col] + available_geo],
            on=join_col,
            how="left",
        )
    # Rename for clarity
    rename_map = {
        "revenu_median": "revenu_median_commune",
        "taux_chomage": "taux_chomage_canton",
        "pib_par_habitant": "pib_par_habitant_canton",
        "pct_frontaliers": "pct_frontaliers_commune",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Encode urban category
    if "categorie_urbaine" in df.columns:
        urban_map = {"rural": 0, "periurbain": 1, "urbain": 2}
        df["categorie_urbaine_encoded"] = df["categorie_urbaine"].map(urban_map).fillna(1)

    return df


# %% ---- CELL 9: Build interaction features ----

def build_interaction_features(df):
    """Create interaction features from available columns."""

    if "income_midpoint" in df.columns and "n_produits_onboarding" in df.columns:
        df["revenu_x_produits"] = df["income_midpoint"] * df["n_produits_onboarding"]

    if "age" in df.columns and "fam_credit" in df.columns:
        df["age_x_credit"] = df["age"] * df["fam_credit"]

    if "canal_digital" in df.columns and "age" in df.columns:
        df["digital_x_age"] = df["canal_digital"] * df["age"]

    if "income_midpoint" in df.columns and "revenu_median_commune" in df.columns:
        df["revenu_vs_commune"] = df["income_midpoint"] - df["revenu_median_commune"]

    if "est_frontalier" in df.columns and "income_midpoint" in df.columns:
        df["frontalier_x_revenu"] = df["est_frontalier"] * df["income_midpoint"]

    return df


# %% ---- CELL 10: NBI target variable ----

def extract_nbi_target(df):
    """
    Extract the NBI/PNB target from available columns.
    Priority: nbi_annual > sum of quarterly > pnb_annuel
    """
    if "nbi_annual" in df.columns:
        df["pnb_annee1"] = pd.to_numeric(df["nbi_annual"], errors="coerce").fillna(0)
    elif "pnb_annuel" in df.columns:
        df["pnb_annee1"] = pd.to_numeric(df["pnb_annuel"], errors="coerce").fillna(0)
    elif all(f"nbi_q{q}" in df.columns for q in range(1, 5)):
        df["pnb_annee1"] = sum(
            pd.to_numeric(df[f"nbi_q{q}"], errors="coerce").fillna(0) for q in range(1, 5)
        )
    elif all(f"pnb_q{q}" in df.columns for q in range(1, 5)):
        df["pnb_annee1"] = sum(
            pd.to_numeric(df[f"pnb_q{q}"], errors="coerce").fillna(0) for q in range(1, 5)
        )
    else:
        print("  WARNING: No NBI/PNB columns found. Target will be NaN.")
        df["pnb_annee1"] = np.nan

    return df


# %% ---- CELL 11: Full pipeline — build training set ----

def build_new_client_training_set(statec_csv_path=None):
    """
    Complete pipeline: identify new client cohorts, add churn flags,
    extract features, enrich with geography, build interactions.

    Returns a single DataFrame ready for model training.
    """
    print("=" * 60)
    print("BUILDING NEW CLIENT TRAINING SET")
    print("=" * 60)

    statec = load_statec_commune_data(statec_csv_path)
    all_cohorts = []

    for year in sorted(CHURN_FOLDERS.keys()):
        print(f"\n--- Processing cohort {year} ---")

        # Step 1: identify new clients
        new_clients = identify_new_clients(year)
        if new_clients.empty:
            continue

        # Step 2: add churn flag (did they leave within 12 months?)
        new_clients = add_churn_flag(new_clients, year)

        # Step 3: extract sign-up features
        new_clients = extract_signup_features(new_clients)

        # Step 4: geographic enrichment
        new_clients = enrich_with_geography(new_clients, statec)

        # Step 5: interaction features
        new_clients = build_interaction_features(new_clients)

        # Step 6: NBI target
        new_clients = extract_nbi_target(new_clients)

        all_cohorts.append(new_clients)
        print(f"  Cohort {year}: {len(new_clients)} new clients, "
              f"churn rate = {new_clients['churned_year1'].mean():.2%}" if new_clients['churned_year1'].notna().any()
              else f"  Cohort {year}: {len(new_clients)} new clients, churn unknown")

    if not all_cohorts:
        print("\nERROR: No cohorts could be built. Check your Stock file paths.")
        return pd.DataFrame()

    df = pd.concat(all_cohorts, ignore_index=True)

    print(f"\n{'=' * 60}")
    print(f"TRAINING SET SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total new clients: {len(df)}")
    print(f"Cohorts: {sorted(df['acquisition_year'].unique())}")
    print(f"Columns: {len(df.columns)}")
    if df["churned_year1"].notna().any():
        print(f"Overall churn rate: {df['churned_year1'].mean():.2%}")
    if df["pnb_annee1"].notna().any():
        print(f"Mean PNB year 1: {df['pnb_annee1'].mean():,.0f} EUR")
        print(f"Median PNB year 1: {df['pnb_annee1'].median():,.0f} EUR")
    print(f"\nFeature columns:")
    for col in sorted(df.columns):
        non_null = df[col].notna().sum()
        print(f"  {col}: {non_null}/{len(df)} non-null ({non_null/len(df)*100:.0f}%)")

    return df


# %% ---- CELL 12: Run pipeline ----

# Uncomment and adjust the path to your STATEC data file:
# STATEC_PATH = "../data/statec_communes.csv"
# df_training = build_new_client_training_set(statec_csv_path=STATEC_PATH)

# Without STATEC data (geographic features will be NaN):
df_training = build_new_client_training_set()
