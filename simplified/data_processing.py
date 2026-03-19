# =============================================================================
# DATA PROCESSING — Load Stock CSVs, derive churn, build unified DataFrame
# =============================================================================
#
# Expected folder structure:
#   CHURN_2023/  Stock 2023.csv, Stock 2024.csv, Upstreaming.csv
#   CHURN_2024/  Stock 2024.csv, Stock 2025.csv, Upstreaming.csv
#   CHURN_2025/  Stock 2025.csv, Stock 2026.csv, Upstreaming.csv
#
# Churn logic:
#   In Stock Y but NOT Stock Y+1 and NOT Upstreaming  →  churned = 1
#   In Upstreaming                                     →  churned = 0, is_upstreamed = 1
#   In both Stock Y and Stock Y+1                      →  churned = 0
#
# Copy each cell block into your notebook and run them independently.
# =============================================================================


# %% ---- CELL 1: Imports ----

import pandas as pd
import numpy as np
from pathlib import Path


# %% ---- CELL 2: Config ----
# Change these paths to match your setup

BASE_PATH = ".."          # directory that contains the CHURN_YYYY folders
ENCODING  = "utf-8"       # try "latin-1" if you get encoding errors
YEARS     = [2023, 2024, 2025]  # set to None to auto-detect from folder names


# %% ---- CELL 3: Helper — read a CSV with encoding fallback ----

def read_csv_safe(path, encoding="utf-8"):
    """Read CSV with auto-delimiter detection and encoding fallback."""
    try:
        return pd.read_csv(path, encoding=encoding, sep=None, engine="python")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", sep=None, engine="python")


# %% ---- CELL 4: Helper — find a file by candidate names ----

def find_csv(folder, candidates):
    """Return first existing file from candidate list, or first CSV in folder."""
    folder = Path(folder)
    for name in candidates:
        path = folder / name
        if path.exists():
            return path
    csvs = sorted(folder.glob("*.csv")) + sorted(folder.glob("*.CSV"))
    return csvs[0] if csvs else None


# %% ---- CELL 5: Helper — clean client_id column ----

def clean_ids(df):
    """Find the client_id column, standardise it, deduplicate."""
    df = df.copy()

    # Find client_id column (case-insensitive, flexible naming)
    id_col = None
    for col in df.columns:
        normalised = col.strip().lower().replace(" ", "_").replace("-", "_")
        if normalised in ("client_id", "clientid", "id_client", "customer_id",
                          "cust_id", "id", "no_client", "num_client"):
            id_col = col
            break
    if id_col is None:
        id_col = df.columns[0]

    df = df.rename(columns={id_col: "client_id"})
    df["client_id"] = df["client_id"].astype(str).str.strip()
    df = df[df["client_id"].notna() & (df["client_id"] != "") & (df["client_id"] != "nan")]
    df = df.drop_duplicates(subset=["client_id"])
    return df


# %% ---- CELL 6: Load one year — reads 3 CSVs and derives churn ----

def load_year(folder, year, encoding="utf-8"):
    """
    Load Stock Y, Stock Y+1, Upstreaming from one CHURN_YYYY folder.
    Returns a DataFrame with: client_id, year, churned, is_upstreamed + extra cols.
    """
    folder = Path(folder)

    stock_y_path  = find_csv(folder, [f"Stock {year}.csv",   f"Stock_{year}.csv",   f"stock {year}.csv"])
    stock_y1_path = find_csv(folder, [f"Stock {year+1}.csv", f"Stock_{year+1}.csv", f"stock {year+1}.csv"])
    upstream_path = find_csv(folder, ["Upstreaming.csv", "upstreaming.csv"])

    stock_y  = clean_ids(read_csv_safe(stock_y_path, encoding))
    stock_y1 = clean_ids(read_csv_safe(stock_y1_path, encoding))
    upstream = clean_ids(read_csv_safe(upstream_path, encoding))

    ids_y1 = set(stock_y1["client_id"])
    ids_up = set(upstream["client_id"])

    result = stock_y.copy()
    result["year"] = year
    result["is_upstreamed"] = result["client_id"].isin(ids_up).astype(int)
    result["churned"] = (
        (~result["client_id"].isin(ids_y1)) & (~result["client_id"].isin(ids_up))
    ).astype(int)

    n = len(result)
    n_churned = result["churned"].sum()
    n_up = result["is_upstreamed"].sum()
    print(f"  {year}: {n} clients | {n_churned} churned ({n_churned/n:.1%}) | {n_up} upstreamed")

    return result


# %% ---- CELL 7: Build full dataset — stack all years ----

# Auto-detect years from folder names if YEARS is None
if YEARS is None:
    base = Path(BASE_PATH)
    YEARS = sorted(
        int(f.name.split("_")[1])
        for f in base.glob("CHURN_*")
        if f.is_dir() and f.name.split("_")[1].isdigit()
    )

print(f"Loading years: {YEARS}\n")

frames = []
for y in YEARS:
    folder = Path(BASE_PATH) / f"CHURN_{y}"
    frames.append(load_year(folder, y, ENCODING))

df = pd.concat(frames, ignore_index=True)


# %% ---- CELL 8: Summary ----

print(f"\nTotal rows  : {len(df)} (client-years)")
print(f"Unique IDs  : {df['client_id'].nunique()}")
print(f"Churn rate  : {df['churned'].mean():.2%}")
print(f"Upstreamed  : {df['is_upstreamed'].sum()}")
print(f"Columns     : {list(df.columns)}")

df.groupby("year").agg(
    total=("client_id", "count"),
    churned=("churned", "sum"),
    upstreamed=("is_upstreamed", "sum"),
    churn_rate=("churned", "mean"),
).reset_index()


# %% ---- CELL 9: Preview the data ----

df.head(10)


# %% ---- CELL 10: Save (optional) ----

# df.to_csv("churn_dataset.csv", index=False)
# print("Saved to churn_dataset.csv")
