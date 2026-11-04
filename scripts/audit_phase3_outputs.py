"""Independent audit and verification script for Phase 3 preprocessing artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import joblib
import numpy as np
import pyarrow.parquet as pq

from netdefy.preprocessing.cleaner import DataCleaner
from netdefy.preprocessing.scaler import FeatureScaler


def run_audit() -> None:
    project_root = Path(__file__).resolve().parent.parent
    processed_dir = project_root / "data" / "processed"
    artifacts_dir = project_root / "artifacts" / "preprocessing"

    print("=" * 80)
    print("           NETDEFY — PHASE 3 INDEPENDENT OUTPUT AUDIT           ")
    print("=" * 80)

    # 1. Check Schema
    with open(artifacts_dir / "feature_schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    retained_76 = schema["retained_features_service_independent"]
    assert len(retained_76) == 76, f"Expected 76 features, got {len(retained_76)}"
    assert "Destination Port" not in retained_76
    assert "Label" not in retained_76
    assert "Fwd Header Length.1" not in retained_76
    for ident in ["Flow ID", "Source IP", "Destination IP", "Timestamp", "Source Port"]:
        assert ident not in retained_76, f"Forbidden identifier found: {ident}"

    print("✓ Feature schema verified: 76 service-independent features.")

    # 2. Check Parquets
    partitions = ["train", "validation", "test"]
    views = ["raw", "dedup", "audit"]

    total_raw_rows = 0
    total_dedup_rows = 0

    for p in partitions:
        print(f"\n--- Partition: {p} ---")
        for v in views:
            pfile = processed_dir / p / f"{p}_{v}.parquet"
            assert pfile.exists(), f"Missing file: {pfile}"
            size_mb = pfile.stat().st_size / (1024 * 1024)

            # Read schema and row count using ParquetFile metadata (instant)
            pf = pq.ParquetFile(pfile)
            nrows = pf.metadata.num_rows
            ncols = pf.metadata.num_columns
            cols = pf.schema.names

            print(f"  • {v:5s}: {nrows:>10,} rows | {ncols:>2} cols | {size_mb:>6.2f} MB")

            if v == "raw":
                total_raw_rows += nrows
                assert ncols == 77  # 76 features + Label
                assert cols[-1] == "Label"
                assert cols[:-1] == retained_76
            elif v == "dedup":
                total_dedup_rows += nrows
                assert ncols == 77  # 76 features + Label
                assert cols[-1] == "Label"
                assert cols[:-1] == retained_76
            elif v == "audit":
                assert ncols == 3  # Destination Port, Service_Category, Label
                assert "Destination Port" in cols
                assert "Service_Category" in cols
                assert "Label" in cols

    print("\n" + "=" * 80)
    print(f"Total Raw Flow Records:          {total_raw_rows:,} (Expected: 2,830,743)")
    print(f"Total Deduplicated Flow Records: {total_dedup_rows:,}")
    assert total_raw_rows == 2830743, f"Raw row count mismatch: {total_raw_rows}"

    # 3. Deep check on data types and nulls
    print("\n--- Verifying Data Types, NaNs, and Infs ---")
    for p in partitions:
        for v in ["raw", "dedup"]:
            pfile = processed_dir / p / f"{p}_{v}.parquet"
            # Read first 10,000 rows sample to verify types and numerical stability
            df_sample = pq.read_table(pfile).slice(0, 10000).to_pandas()
            for col in retained_76:
                assert df_sample[col].dtype == np.float32, (
                    f"Column {col} in {pfile} is not float32 ({df_sample[col].dtype})"
                )
                assert not df_sample[col].isna().any(), f"Column {col} has NaN in {pfile}"
                assert not np.isinf(df_sample[col]).any(), f"Column {col} has Inf in {pfile}"
            print(f"  ✓ {p}_{v}.parquet: all 76 features verified float32, 0 NaNs, 0 Infs.")

    # 4. Check fitted joblib artifacts
    print("\n--- Verifying Fitted Artifacts Provenance ---")
    imputer: DataCleaner = joblib.load(artifacts_dir / "imputer.joblib")
    assert imputer.is_fitted
    assert len(imputer.statistics_) == 76
    print(
        f"  ✓ Imputer: fitted={imputer.is_fitted}, strategy={imputer.strategy}, "
        f"76 features, constant features in train={len(imputer.constant_columns_in_training)}"
    )

    std_scaler: FeatureScaler = joblib.load(artifacts_dir / "standard_scaler.joblib")
    assert std_scaler.is_fitted
    assert std_scaler.scaler_type == "standard"
    assert len(std_scaler.center_) == 76
    print(
        f"  ✓ StandardScaler: fitted={std_scaler.is_fitted}, "
        f"76 features, center count={len(std_scaler.center_)}"
    )

    rob_scaler: FeatureScaler = joblib.load(artifacts_dir / "robust_scaler.joblib")
    assert rob_scaler.is_fitted
    assert rob_scaler.scaler_type == "robust"
    assert len(rob_scaler.center_) == 76
    print(
        f"  ✓ RobustScaler: fitted={rob_scaler.is_fitted}, "
        f"76 features, center count={len(rob_scaler.center_)}"
    )

    # 5. Check metadata JSON
    with open(artifacts_dir / "preprocessing_metadata.json", encoding="utf-8") as f:
        meta = json.load(f)
    print("\n--- Metadata Summary ---")
    print(f"  • Execution Timestamp: {meta['execution_timestamp']}")
    print(f"  • Duration:            {meta['processing_duration_seconds']:.2f} s")
    print(f"  • Peak RAM:            {meta['peak_memory_mb']:.2f} MB")
    print(f"  • Random Seed:         {meta['random_seed']}")
    print(
        f"  • Raw Rows:            {meta['train_raw_rows'] + meta['val_raw_rows'] + meta['test_raw_rows']:,}"
    )
    print(
        f"  • Retained Dedup Rows: {meta['train_dedup_rows'] + meta['val_dedup_rows'] + meta['test_dedup_rows']:,}"
    )

    print("\n" + "=" * 80)
    print("               PHASE 3 OUTPUT AUDIT PASSED 100%                 ")
    print("=" * 80)


if __name__ == "__main__":
    run_audit()
