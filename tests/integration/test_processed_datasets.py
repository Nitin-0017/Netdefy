"""Integration tests verifying processed Parquet datasets in data/processed."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "preprocessing"


@pytest.mark.skipif(
    not (PROCESSED_DIR / "train" / "train_raw.parquet").exists(),
    reason="Processed parquet datasets have not been generated yet.",
)
def test_processed_parquet_integrity_and_leakage_absence() -> None:
    """Verify row counts, exact 77 columns, float32 dtypes, and zero leakage in actual Parquets."""
    with open(ARTIFACTS_DIR / "feature_schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    retained_76 = schema["retained_features_service_independent"]
    assert len(retained_76) == 76

    expected_counts = {
        ("train", "raw"): 529918,
        ("train", "dedup"): 459112,
        ("train", "audit"): 459112,
        ("validation", "raw"): 1138612,
        ("validation", "dedup"): 963879,
        ("validation", "audit"): 963879,
        ("test", "raw"): 1162213,
        ("test", "dedup"): 845403,
        ("test", "audit"): 845403,
    }

    for (part, view), expected_rows in expected_counts.items():
        pfile = PROCESSED_DIR / part / f"{part}_{view}.parquet"
        assert pfile.exists()
        pf = pq.ParquetFile(pfile)
        assert pf.metadata.num_rows == expected_rows, f"Row count mismatch in {pfile}"

        if view in ("raw", "dedup"):
            assert pf.metadata.num_columns == 77
            assert pf.schema.names[-1] == "Label"
            assert pf.schema.names[:-1] == retained_76

            # Sample first 2000 rows to verify float32 and no NaNs/Infs
            df_sample = pq.read_table(pfile).slice(0, 2000).to_pandas()
            for col in retained_76:
                assert df_sample[col].dtype == np.float32
                assert not df_sample[col].isna().any()
                assert not np.isinf(df_sample[col]).any()

        elif view == "audit":
            assert pf.metadata.num_columns == 3
            assert set(pf.schema.names) == {"Destination Port", "Service_Category", "Label"}
