"""
Data Processing — Load Stock CSVs, derive churn, build unified DataFrame.

Expected folder structure (each CHURN_YYYY folder contains 3 CSVs):
    CHURN_2023/
        Stock 2023.csv        ← clients at start of 2023
        Stock 2024.csv        ← clients at start of 2024
        Upstreaming.csv       ← clients who moved to VIP during 2023
    CHURN_2024/ ...
    CHURN_2025/ ...

Each CSV must have a 'client_id' column (other columns are kept as-is).

Churn logic per year:
    In Stock Y but NOT in Stock Y+1 and NOT in Upstreaming  →  churned = 1
    In Upstreaming                                           →  churned = 0, is_upstreamed = 1
    In both Stock Y and Stock Y+1                            →  churned = 0
"""

import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_csv(folder: Path, candidates: list[str]) -> Path | None:
    """Return the first existing file from a list of candidate names."""
    for name in candidates:
        path = folder / name
        if path.exists():
            return path
    # Fallback: grab the first CSV in the folder
    csvs = sorted(folder.glob("*.csv")) + sorted(folder.glob("*.CSV"))
    return csvs[0] if csvs else None


def _read_csv(path: Path, encoding: str = "utf-8") -> pd.DataFrame:
    """Read a CSV with automatic delimiter detection and encoding fallback."""
    try:
        return pd.read_csv(path, encoding=encoding, sep=None, engine="python")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", sep=None, engine="python")


def _clean_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise client_id: find column, cast to str, strip, dedupe."""
    df = df.copy()

    # Find the client_id column (case-insensitive)
    id_col = None
    for col in df.columns:
        if col.strip().lower().replace(" ", "_").replace("-", "_") in (
            "client_id", "clientid", "id_client", "customer_id", "cust_id",
            "id", "no_client", "num_client",
        ):
            id_col = col
            break
    if id_col is None:
        id_col = df.columns[0]  # last resort

    df = df.rename(columns={id_col: "client_id"})
    df["client_id"] = df["client_id"].astype(str).str.strip()
    df = df[df["client_id"].notna() & (df["client_id"] != "") & (df["client_id"] != "nan")]
    df = df.drop_duplicates(subset=["client_id"])
    return df


# ---------------------------------------------------------------------------
# Core: load one year
# ---------------------------------------------------------------------------

def load_year(folder: str | Path, year: int, encoding: str = "utf-8") -> pd.DataFrame:
    """
    Load the 3 CSVs for a single year and return one DataFrame with columns:
        client_id, year, churned, is_upstreamed  (+ any extra Stock columns)
    """
    folder = Path(folder)

    stock_y = _read_csv(
        _find_csv(folder, [f"Stock {year}.csv", f"Stock_{year}.csv", f"stock {year}.csv"]),
        encoding,
    )
    stock_y1 = _read_csv(
        _find_csv(folder, [f"Stock {year+1}.csv", f"Stock_{year+1}.csv", f"stock {year+1}.csv"]),
        encoding,
    )
    upstream = _read_csv(
        _find_csv(folder, ["Upstreaming.csv", "upstreaming.csv"]),
        encoding,
    )

    stock_y = _clean_ids(stock_y)
    stock_y1 = _clean_ids(stock_y1)
    upstream = _clean_ids(upstream)

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


# ---------------------------------------------------------------------------
# Core: build full dataset
# ---------------------------------------------------------------------------

def build_dataset(
    base_path: str | Path = ".",
    years: list[int] | None = None,
    encoding: str = "utf-8",
    output_path: str | None = None,
) -> pd.DataFrame:
    """
    Load all CHURN_YYYY folders, derive churn per year, stack into one DataFrame.

    Parameters
    ----------
    base_path : directory containing the CHURN_YYYY folders
    years     : explicit list of years; auto-detected from folder names if None
    encoding  : CSV encoding ('utf-8' or 'latin-1' for SAP exports)
    output_path : save merged CSV here (optional)

    Returns
    -------
    DataFrame with one row per client per year.
    """
    base = Path(base_path)

    if years is None:
        years = sorted(
            int(f.name.split("_")[1])
            for f in base.glob("CHURN_*")
            if f.is_dir() and f.name.split("_")[1].isdigit()
        )

    if not years:
        raise FileNotFoundError(f"No CHURN_YYYY folders found in {base_path}")

    print(f"Building churn dataset — years: {years}\n")

    frames = [load_year(base / f"CHURN_{y}", y, encoding) for y in years]
    merged = pd.concat(frames, ignore_index=True)

    # Summary
    print(f"\n{'='*50}")
    print(f"  Total rows : {len(merged)} (client-years)")
    print(f"  Unique IDs : {merged['client_id'].nunique()}")
    print(f"  Churn rate : {merged['churned'].mean():.2%}")
    print(f"  Upstreamed : {merged['is_upstreamed'].sum()}")
    print(f"{'='*50}")

    if output_path:
        merged.to_csv(output_path, index=False)
        print(f"  Saved → {output_path}")

    return merged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Build churn dataset from Stock CSVs")
    p.add_argument("--base-path", default=".", help="Dir with CHURN_YYYY folders")
    p.add_argument("--years", nargs="+", type=int, default=None)
    p.add_argument("--encoding", default="utf-8")
    p.add_argument("--output", default="churn_dataset.csv")
    args = p.parse_args()

    build_dataset(args.base_path, args.years, args.encoding, args.output)
