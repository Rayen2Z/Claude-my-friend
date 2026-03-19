"""
===============================================================================
  CHURN DATA LOADER — CSV Cleaning & Merging
===============================================================================
  Loads the 3 CSV files per year from the CHURN_YYYY folders and produces a
  single unified dataset with one row per client per year and a churn flag.

  Folder structure expected:
    CHURN_2023/
      Stock 2023.csv        ← clients present in Jan 2023 (start of year)
      Stock 2024.csv        ← clients present in Jan 2024 (start of next year)
      Upstreaming.csv       ← clients who upstreamed during 2023

  Churn logic:
    - In Stock Y but NOT in Stock Y+1 and NOT in Upstreaming → churned (1)
    - In Upstreaming → retained, flagged as upstreamed
    - In both Stock Y and Stock Y+1 → retained (0)
===============================================================================
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


def clean_client_ids(df: pd.DataFrame, id_col: str = "client_id") -> pd.DataFrame:
    """
    Clean a client CSV: standardize the client_id column.
    Handles common issues from SAP BI exports.
    """
    df = df.copy()

    # Find the client_id column (case-insensitive, flexible naming)
    id_col_found = None
    for col in df.columns:
        col_lower = col.strip().lower().replace(" ", "_").replace("-", "_")
        if col_lower in ("client_id", "clientid", "id_client", "customer_id",
                         "cust_id", "id", "no_client", "num_client"):
            id_col_found = col
            break

    if id_col_found is None:
        # Fall back to first column
        id_col_found = df.columns[0]
        print(f"  Warning: No 'client_id' column found, using '{id_col_found}'")

    # Rename to standard name
    df = df.rename(columns={id_col_found: "client_id"})

    # Clean: strip whitespace, convert to string, drop nulls
    df["client_id"] = df["client_id"].astype(str).str.strip()
    df = df[df["client_id"].notna() & (df["client_id"] != "") & (df["client_id"] != "nan")]

    # Drop exact duplicates on client_id
    n_before = len(df)
    df = df.drop_duplicates(subset=["client_id"])
    n_dupes = n_before - len(df)
    if n_dupes > 0:
        print(f"  Removed {n_dupes} duplicate client_ids")

    return df


def load_year_csvs(
    folder_path: str,
    year: int,
    encoding: str = "utf-8",
) -> dict:
    """
    Load the 3 CSVs for a given year from a CHURN_YYYY folder.

    Parameters
    ----------
    folder_path : Path to CHURN_YYYY folder
    year : The year (e.g. 2023)
    encoding : CSV encoding (try 'latin-1' if utf-8 fails)

    Returns
    -------
    dict with keys: stock_y, stock_y1, upstreamed
    """
    folder = Path(folder_path)

    # Find Stock Y file (flexible naming)
    stock_y_candidates = [
        f"Stock {year}.csv",
        f"Stock_{year}.csv",
        f"stock {year}.csv",
        f"stock_{year}.csv",
        f"Stock{year}.csv",
    ]

    stock_y1_candidates = [
        f"Stock {year + 1}.csv",
        f"Stock_{year + 1}.csv",
        f"stock {year + 1}.csv",
        f"stock_{year + 1}.csv",
        f"Stock{year + 1}.csv",
    ]

    upstream_candidates = [
        "Upstreaming.csv",
        "upstreaming.csv",
        "Upstreaming.CSV",
        "upstream.csv",
    ]

    def find_file(candidates):
        for name in candidates:
            path = folder / name
            if path.exists():
                return path
        # Fallback: list all CSVs and try fuzzy match
        csvs = list(folder.glob("*.csv")) + list(folder.glob("*.CSV"))
        return csvs[0] if csvs else None

    stock_y_path = find_file(stock_y_candidates)
    stock_y1_path = find_file(stock_y1_candidates)
    upstream_path = find_file(upstream_candidates)

    result = {}

    for label, path in [("stock_y", stock_y_path), ("stock_y1", stock_y1_path),
                         ("upstreamed", upstream_path)]:
        if path and path.exists():
            try:
                df = pd.read_csv(path, encoding=encoding, sep=None, engine="python")
            except UnicodeDecodeError:
                df = pd.read_csv(path, encoding="latin-1", sep=None, engine="python")

            df = clean_client_ids(df)
            result[label] = df
            print(f"  {label}: {len(df)} clients from {path.name}")
        else:
            print(f"  Warning: {label} file not found in {folder}")
            result[label] = pd.DataFrame(columns=["client_id"])

    return result


def derive_churn_from_stocks(
    stock_y: pd.DataFrame,
    stock_y1: pd.DataFrame,
    upstreamed: pd.DataFrame,
    year: int,
) -> pd.DataFrame:
    """
    Derive churn by comparing Stock Y vs Stock Y+1, excluding upstreamed.

    Logic:
      - In Stock Y AND in Stock Y+1 → retained (churned=0)
      - In Stock Y AND in Upstreaming → retained (churned=0, upstreamed=1)
      - In Stock Y AND NOT in Stock Y+1 AND NOT in Upstreaming → churned (churned=1)

    Parameters
    ----------
    stock_y : Clients at start of year Y
    stock_y1 : Clients at start of year Y+1
    upstreamed : Clients who upstreamed during year Y
    year : The year being processed

    Returns
    -------
    DataFrame with columns: client_id, year, churned, is_upstreamed
    Plus any extra columns from the Stock Y file.
    """
    ids_y = set(stock_y["client_id"].unique())
    ids_y1 = set(stock_y1["client_id"].unique())
    ids_upstream = set(upstreamed["client_id"].unique())

    # Start from Stock Y (clients at beginning of the year)
    result = stock_y.copy()
    result["year"] = year

    # Classify each client
    result["still_present_next_year"] = result["client_id"].isin(ids_y1).astype(int)
    result["is_upstreamed"] = result["client_id"].isin(ids_upstream).astype(int)

    # Churn flag: absent next year AND not upstreamed
    result["churned"] = (
        (result["still_present_next_year"] == 0) &
        (result["is_upstreamed"] == 0)
    ).astype(int)

    # Summary stats
    n_total = len(result)
    n_retained = (result["churned"] == 0).sum()
    n_churned = (result["churned"] == 1).sum()
    n_upstreamed = (result["is_upstreamed"] == 1).sum()

    # Clients who upstreamed but also appear in Y+1 (edge case)
    n_upstream_and_present = (
        (result["is_upstreamed"] == 1) & (result["still_present_next_year"] == 1)
    ).sum()

    print(f"\n  Year {year} summary:")
    print(f"    Total clients (start of year): {n_total}")
    print(f"    Retained (in Stock {year+1}):    {n_retained - n_upstreamed}")
    print(f"    Upstreamed (VIP):               {n_upstreamed}")
    print(f"    Churned:                        {n_churned}")
    print(f"    Churn rate:                     {n_churned/n_total:.2%}")

    if n_upstream_and_present > 0:
        print(f"    Note: {n_upstream_and_present} upstreamed clients also appear in Stock {year+1}")

    # New clients in Y+1 that weren't in Y (acquisitions)
    new_clients = ids_y1 - ids_y
    print(f"    New clients in {year+1}:          {len(new_clients)}")

    # Drop helper column
    result.drop(columns=["still_present_next_year"], inplace=True)

    return result


def build_churn_dataset(
    base_path: str,
    years: list = None,
    encoding: str = "utf-8",
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    Build the full churn dataset from all CHURN_YYYY folders.

    Parameters
    ----------
    base_path : Directory containing CHURN_2023/, CHURN_2024/, CHURN_2025/ folders
    years : List of years to process (default: auto-detect from folder names)
    encoding : CSV encoding
    output_path : Where to save the merged dataset (optional)

    Returns
    -------
    DataFrame: one row per client per year with churn flag
    """
    base = Path(base_path)

    # Auto-detect years from folder names
    if years is None:
        churn_folders = sorted(base.glob("CHURN_*"))
        years = []
        for f in churn_folders:
            try:
                y = int(f.name.split("_")[1])
                years.append(y)
            except (IndexError, ValueError):
                continue

    if not years:
        raise ValueError(f"No CHURN_YYYY folders found in {base_path}")

    print("=" * 70)
    print("  BUILDING CHURN DATASET FROM STOCK FILES")
    print("=" * 70)
    print(f"  Years: {years}")
    print(f"  Source: {base_path}")

    all_years = []

    for year in years:
        folder = base / f"CHURN_{year}"
        if not folder.exists():
            print(f"\n  Warning: {folder} not found, skipping year {year}")
            continue

        print(f"\nLoading CHURN_{year}/...")
        csvs = load_year_csvs(str(folder), year, encoding=encoding)

        year_df = derive_churn_from_stocks(
            stock_y=csvs["stock_y"],
            stock_y1=csvs["stock_y1"],
            upstreamed=csvs["upstreamed"],
            year=year,
        )
        all_years.append(year_df)

    if not all_years:
        raise ValueError("No data loaded from any year")

    # Merge all years
    merged = pd.concat(all_years, ignore_index=True)

    # Overall summary
    print("\n" + "=" * 70)
    print("  MERGED DATASET SUMMARY")
    print("=" * 70)
    print(f"  Total rows: {len(merged)} (client-years)")
    print(f"  Unique clients: {merged['client_id'].nunique()}")
    print(f"  Years: {sorted(merged['year'].unique())}")
    print(f"  Overall churn rate: {merged['churned'].mean():.2%}")
    print(f"  Total upstreamed: {merged['is_upstreamed'].sum()}")

    # Year-by-year summary table
    summary = merged.groupby("year").agg(
        total_clients=("client_id", "count"),
        churned=("churned", "sum"),
        upstreamed=("is_upstreamed", "sum"),
        churn_rate=("churned", "mean"),
    ).reset_index()
    print(f"\n{summary.to_string(index=False)}")

    if output_path:
        merged.to_csv(output_path, index=False)
        print(f"\n  Saved to {output_path}")

    return merged


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build churn dataset from Stock CSVs")
    parser.add_argument("--base-path", default=".", help="Directory containing CHURN_YYYY folders")
    parser.add_argument("--years", nargs="+", type=int, default=None)
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--output", default="churn_merged.csv")
    args = parser.parse_args()

    build_churn_dataset(
        base_path=args.base_path,
        years=args.years,
        encoding=args.encoding,
        output_path=args.output,
    )
