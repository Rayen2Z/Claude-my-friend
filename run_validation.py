"""
===============================================================================
  MASTER VALIDATION RUNNER
===============================================================================
  Runs all hypothesis checks (H5, H3, H7) and generates a consolidated report.

  Two modes:
    STOCK MODE (primary):
      python run_validation.py --base-path .
      Reads CHURN_2023/, CHURN_2024/, CHURN_2025/ folders with Stock CSVs

    TRANSACTION MODE (legacy):
      python run_validation.py --mode transactions --transactions data/txns.csv

  Workflow:
    1. Build churn dataset from Stock files (or transactions)
    2. Run H7 data quality checks
    3. Run H5 churn definition quality checks
    4. Run H3 constant hazard assumption checks
    5. Train retention model (if features available)
    6. Generate consolidated report
===============================================================================
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from data_pipeline.load_churn_csvs import build_churn_dataset
from hypothesis_validation.h5_churn_definition_quality import run_all_h5_checks
from hypothesis_validation.h3_constant_hazard_assumption import run_all_h3_checks
from hypothesis_validation.h7_data_quality_checks import run_all_h7_checks
from model.retention_model import train_retention_model, plot_model_diagnostics, score_clients


def main():
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(description="Run full retention model validation")
    parser.add_argument("--mode", choices=["stocks", "transactions"], default="stocks",
                        help="Data source mode (default: stocks)")
    parser.add_argument("--base-path", default=".",
                        help="[stocks] Directory containing CHURN_YYYY folders")
    parser.add_argument("--years", nargs="+", type=int, default=None,
                        help="[stocks] Years to process (auto-detect if omitted)")
    parser.add_argument("--encoding", default="utf-8",
                        help="CSV encoding (try 'latin-1' for SAP exports)")
    parser.add_argument("--transactions", default=None,
                        help="[transactions] Path to transactions CSV")
    parser.add_argument("--clients", default=None, help="Path to clients CSV (optional)")
    parser.add_argument("--output-dir", default="results", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    plots_dir = str(output_dir / "plots")
    Path(plots_dir).mkdir(exist_ok=True)

    # =========================================================================
    # STEP 1: Build churn dataset
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 1: BUILD CHURN DATASET")
    print("=" * 70)

    churn_data_path = str(output_dir / "churn_merged.csv")

    if args.mode == "stocks":
        churn_df = build_churn_dataset(
            base_path=args.base_path,
            years=args.years,
            encoding=args.encoding,
            output_path=churn_data_path,
        )
    else:
        # Transaction-based fallback
        from data_pipeline.churn_data_pipeline import load_data, derive_monthly_churn
        raw_df = load_data(args.transactions)
        monthly_churn = derive_monthly_churn(raw_df)

        # Convert to annual format
        yearly_features = raw_df.copy()
        yearly_features["year"] = yearly_features["transaction_date"].dt.year
        clients_per_year = yearly_features.groupby(["client_id", "year"]).size().reset_index(name="_count")
        clients_per_year.drop(columns=["_count"], inplace=True)

        if not monthly_churn.empty:
            monthly_churn["churn_year"] = monthly_churn["churn_month"].dt.year
            churn_lookup = monthly_churn[["client_id", "churn_year"]].drop_duplicates()
            clients_per_year = clients_per_year.merge(churn_lookup, on="client_id", how="left")
            clients_per_year["churned"] = (
                clients_per_year["churn_year"] == clients_per_year["year"] + 1
            ).astype(int)
            clients_per_year.drop(columns=["churn_year"], inplace=True)
        else:
            clients_per_year["churned"] = 0

        clients_per_year["is_upstreamed"] = 0
        churn_df = clients_per_year
        churn_df.to_csv(churn_data_path, index=False)

    # =========================================================================
    # STEP 2: H7 Data Quality Checks
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 2: H7 — DATA QUALITY CHECKS")
    print("=" * 70)

    h7_results = run_all_h7_checks(
        churn_data_path,
        transactions_path=args.transactions,
        output_dir=plots_dir,
    )

    # =========================================================================
    # STEP 3: H5 Churn Definition Quality
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 3: H5 — CHURN DEFINITION QUALITY")
    print("=" * 70)

    h5_results = run_all_h5_checks(churn_data_path, output_dir=plots_dir)

    # =========================================================================
    # STEP 4: H3 Constant Hazard Assumption
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 4: H3 — CONSTANT HAZARD ASSUMPTION")
    print("=" * 70)

    h3_results = run_all_h3_checks(
        churn_data_path=churn_data_path,
        clients_path=args.clients,
        output_dir=plots_dir,
    )

    # =========================================================================
    # STEP 5: Train Retention Model
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 5: TRAIN RETENTION MODEL")
    print("=" * 70)

    # Check if there are enough numeric features for training
    numeric_features = churn_df.select_dtypes(include=["number"]).columns
    feature_candidates = [c for c in numeric_features
                          if c not in ("churned", "churned_next_year", "is_upstreamed", "year")]

    if len(feature_candidates) < 2:
        print("\n  ⚠ Not enough features to train retention model.")
        print("    Your Stock CSVs currently only have client_id.")
        print("    To train the model, add columns to your Stock CSVs:")
        print("      - NBI (nbi_q1, nbi_q2, nbi_q3, nbi_q4 or nbi_annual)")
        print("      - Transaction counts (n_transactions_q1..q4)")
        print("      - Number of products (n_products_q1..q4)")
        print("      - Age, tenure_months, segment")
        print("    Or use enrich_churn_with_features() with transaction data.")
    else:
        try:
            model_results = train_retention_model(churn_df)
            plot_model_diagnostics(model_results, output_dir=plots_dir)

            scored = score_clients(churn_df, model_results["model"], model_results["feature_names"])
            scores_path = str(output_dir / "client_retention_scores.csv")
            scored[["client_id", "year", "retention_score", "retention_3yr"]].to_csv(
                scores_path, index=False
            )
            print(f"\nRetention scores saved to {scores_path}")
        except ImportError:
            print("\n  ⚠ scikit-learn not installed. Skipping model training.")
            print("    Install with: pip install scikit-learn")
        except Exception as e:
            print(f"\n  ⚠ Model training failed: {e}")
            print("    This may happen if your dataset has too few features or no churn events.")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("  VALIDATION COMPLETE — SUMMARY")
    print("=" * 70)
    print(f"\n  Output directory: {output_dir}/")
    print(f"  Churn dataset: {churn_data_path}")
    print(f"  Plots: {plots_dir}/")
    print(f"\n  Next steps:")
    print(f"    1. Review plots in {plots_dir}/")
    print(f"    2. Discuss H5 business questions with your team")
    print(f"    3. If H3 fails, plan survival model upgrade for V2")
    print(f"    4. Address any H7 data quality issues before production")
    print(f"    5. Add NBI/transaction features to Stock CSVs for model training")


if __name__ == "__main__":
    main()
