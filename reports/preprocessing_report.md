# NETDEFY Master Preprocessing & Pipeline Provenance Report

- **Execution Timestamp:** 2026-11-04T03:24:52.442470+00:00
- **Processing Duration:** 75.95 seconds (1.27 minutes)
- **Peak Memory Usage:** 752.62 MB
- **Primary Scaler:** `standard` (fitted exclusively on Monday)
- **Numeric Representation:** `float32`
- **Total Flow Records Processed:** 2,830,743

## Produced Parquet Datasets

- `data/processed/train/train_raw.parquet`
- `data/processed/train/train_dedup.parquet`
- `data/processed/train/train_audit.parquet`
- `data/processed/validation/validation_raw.parquet`
- `data/processed/validation/validation_dedup.parquet`
- `data/processed/validation/validation_audit.parquet`
- `data/processed/test/test_raw.parquet`
- `data/processed/test/test_dedup.parquet`
- `data/processed/test/test_audit.parquet`

## Serialized Artifacts

- `artifacts/preprocessing/feature_schema.json`
- `artifacts/preprocessing/imputer.joblib`
- `artifacts/preprocessing/standard_scaler.joblib`
- `artifacts/preprocessing/robust_scaler.joblib`
- `artifacts/preprocessing/preprocessing_metadata.json`