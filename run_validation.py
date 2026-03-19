"""
===============================================================================
  MASTER VALIDATION RUNNER
===============================================================================
  Runs all hypothesis checks (H5, H3, H7) and generates a consolidated report.

  Usage:
    python run_validation.py --transactions data/transactions.csv \
                             --clients data/clients.csv \
                             --output-dir results

  Workflow:
    1. Run data pipeline → build retention dataset
    2. Run H7 data quality checks
    3. Run H5 churn definition quality checks
    4. Run H3 constant hazard assumption checks
    5. Train retention model
    6. Generate consolidated report
===============================================================================
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from data_pipeline.churn_data_pipeline import run_pipeline, derive_monthly_churn, load_data
from hypothesis_validation.h5_churn_definition_quality import run_all_h5_checks
from hypothesis_validation.h3_constant_hazard_assumption import run_all_h3_checks
from hypothesis_validation.h7_data_quality_checks import run_all_h7_checks
from model.retention_model import train_retention_model, plot_model_diagnostics, score_clients


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run full retention model validation")
    parser.add_argument("--transactions", required=True, help="Path to transactions CSV")
    parser.add_argument("--clients", default=None, help="Path to clients CSV (optional)")
    parser.add_argument("--upstreamed", default=None,
                        help="Path to CSV of clients who moved to VIP portfolio")
    parser.add_argument("--output-dir", default="results", help="Output directory")
    parser.add_argument("--absence-threshold", type=int, default=3,
                        help="Months absent to confirm churn (default: 3)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    plots_dir = str(output_dir / "plots")
    Path(plots_dir).mkdir(exist_ok=True)

    # =========================================================================
    # STEP 1: Build retention dataset
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 1: BUILD RETENTION DATASET")
    print("=" * 70)

    # Load upstreamed clients if provided
    import pandas as pd
    upstreamed = None
    if args.upstreamed:
        upstreamed = pd.read_csv(args.upstreamed)

    retention_data_path = str(output_dir / "retention_model_data.csv")
    features_df = run_pipeline(
        transactions_path=args.transactions,
        clients_path=args.clients,
        upstreamed_path=args.upstreamed,
        output_path=retention_data_path,
        absence_threshold=args.absence_threshold,
    )

    # Also save churn events for H3
    print("\nExporting churn events for H3 validation...")
    raw_df = load_data(args.transactions)
    churn_df = derive_monthly_churn(
        raw_df,
        absence_threshold=args.absence_threshold,
        upstreamed_clients=upstreamed,
    )
    churn_events_path = str(output_dir / "churn_events.csv")
    churn_df.to_csv(churn_events_path, index=False)

    # =========================================================================
    # STEP 2: H7 Data Quality Checks
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 2: H7 — DATA QUALITY CHECKS")
    print("=" * 70)

    h7_results = run_all_h7_checks(
        retention_data_path,
        transactions_path=args.transactions,
        output_dir=plots_dir,
    )

    # =========================================================================
    # STEP 3: H5 Churn Definition Quality
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 3: H5 — CHURN DEFINITION QUALITY")
    print("=" * 70)

    h5_results = run_all_h5_checks(retention_data_path, output_dir=plots_dir)

    # =========================================================================
    # STEP 4: H3 Constant Hazard Assumption
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 4: H3 — CONSTANT HAZARD ASSUMPTION")
    print("=" * 70)

    h3_results = run_all_h3_checks(
        transactions_path=args.transactions,
        churn_path=churn_events_path,
        clients_path=args.clients,
        output_dir=plots_dir,
    )

    # =========================================================================
    # STEP 5: Train Retention Model
    # =========================================================================
    print("\n" + "=" * 70)
    print("  STEP 5: TRAIN RETENTION MODEL")
    print("=" * 70)

    try:
        model_results = train_retention_model(features_df)
        plot_model_diagnostics(model_results, output_dir=plots_dir)

        # Score all clients
        scored = score_clients(features_df, model_results["model"], model_results["feature_names"])
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
        print("    This is expected if your dataset is too small or has no churn events.")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("  VALIDATION COMPLETE — SUMMARY")
    print("=" * 70)
    print(f"\n  Output directory: {output_dir}/")
    print(f"  Retention dataset: {retention_data_path}")
    print(f"  Churn events: {churn_events_path}")
    print(f"  Plots: {plots_dir}/")
    print(f"\n  Next steps:")
    print(f"    1. Review plots in {plots_dir}/")
    print(f"    2. Discuss H5 business questions with your team")
    print(f"    3. If H3 fails, plan survival model upgrade for V2")
    print(f"    4. Address any H7 data quality issues before production")


if __name__ == "__main__":
    main()
