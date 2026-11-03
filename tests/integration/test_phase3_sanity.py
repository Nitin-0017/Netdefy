"""Integration tests verifying end-to-end Phase 3 temporal preprocessing pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from netdefy.preprocessing.pipeline import TemporalPreprocessingPipeline


def _write_mock_csv(file_path: Path, rows: int, label: str, add_inf: bool = False) -> None:
    """Generate synthetic flow records matching the CICIDS2017 schema with duplicate headers."""
    header = (
        " Destination Port, Flow Duration, Total Fwd Packets, Total Backward Packets, "
        "Fwd Header Length, Bwd Header Length, Fwd Header Length, Flow Bytes/s, Flow Packets/s, Label\n"
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(header)
        for i in range(rows):
            bytes_val = "Infinity" if (add_inf and i == 0) else f"{1000.0 + i}"
            f.write(
                f"{80 + i},{100.0 + i},{2 + i},{1 + i},20,20,20,{bytes_val},{50.0 + i},{label}\n"
            )


def test_phase3_temporal_preprocessing_end_to_end(tmp_path: Path) -> None:
    """Verify complete Phase 3 pipeline execution on mock partitioned CSVs."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    processed_dir = tmp_path / "processed"
    artifacts_dir = tmp_path / "artifacts"
    reports_dir = tmp_path / "reports"

    # Create mock CSVs for all 8 canonical files
    # 1. Monday (Train)
    _write_mock_csv(raw_dir / "Monday-WorkingHours.pcap_ISCX.csv", 6, "BENIGN", add_inf=True)

    # 2. Tuesday & Wednesday (Validation)
    _write_mock_csv(raw_dir / "Tuesday-WorkingHours.pcap_ISCX.csv", 4, "SSH-Patator")
    _write_mock_csv(raw_dir / "Wednesday-workingHours.pcap_ISCX.csv", 4, "DoS-Hulk")

    # 3. Thursday & Friday (Test)
    _write_mock_csv(
        raw_dir / "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
        2,
        "Web-Attack",
    )
    _write_mock_csv(
        raw_dir / "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
        2,
        "Infiltration",
    )
    _write_mock_csv(raw_dir / "Friday-WorkingHours-Morning.pcap_ISCX.csv", 2, "Bot")
    _write_mock_csv(
        raw_dir / "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
        2,
        "PortScan",
    )
    _write_mock_csv(raw_dir / "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv", 2, "DDoS")

    pipeline = TemporalPreprocessingPipeline(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        artifacts_dir=artifacts_dir,
        reports_dir=reports_dir,
        chunk_size=2,  # Force fine-grained streaming
        scaler_type="standard",
    )

    metadata = pipeline.run()

    # 1. Verify Parquet Datasets
    train_raw = pd.read_parquet(processed_dir / "train" / "train_raw.parquet")
    train_dedup = pd.read_parquet(processed_dir / "train" / "train_dedup.parquet")
    assert len(train_raw) == 6
    assert len(train_dedup) == 6
    assert "Label" in train_raw.columns
    assert "Fwd Header Length.1" not in train_raw.columns

    val_raw = pd.read_parquet(processed_dir / "validation" / "validation_raw.parquet")
    assert len(val_raw) == 8  # 4 from Tuesday + 4 from Wednesday

    test_raw = pd.read_parquet(processed_dir / "test" / "test_raw.parquet")
    assert len(test_raw) == 10  # 2 * 5 files

    # 2. Verify Artifacts
    assert (artifacts_dir / "feature_schema.json").is_file()
    assert (artifacts_dir / "imputer.joblib").is_file()
    assert (artifacts_dir / "standard_scaler.joblib").is_file()
    assert (artifacts_dir / "robust_scaler.joblib").is_file()
    assert (artifacts_dir / "preprocessing_metadata.json").is_file()

    # 3. Verify Reports
    assert (reports_dir / "feature_selection_report.md").is_file()
    assert (reports_dir / "duplicate_overlap_report.md").is_file()
    assert (reports_dir / "missing_value_report.md").is_file()
    assert (reports_dir / "temporal_partition_report.md").is_file()
    assert (reports_dir / "preprocessing_report.md").is_file()

    # 4. Verify Metadata
    assert metadata.train_raw_rows == 6
    assert metadata.val_raw_rows == 8
    assert metadata.test_raw_rows == 10
    assert metadata.retained_feature_count == 7  # 7 service-independent features
