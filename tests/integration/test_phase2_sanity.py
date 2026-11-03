"""Integration test verifying end-to-end Phase 2 dataset acquisition, manifest, and inspection pipeline."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from netdefy.data.acquisition import compute_sha256, safe_extract_zip
from netdefy.data.inspection import DatasetForensicInspector
from netdefy.data.manifest import create_manifest_from_directory


def test_phase2_acquisition_and_inspection_pipeline(tmp_path: Path) -> None:
    """Verify complete Phase 2 flow: ZIP -> extraction -> manifest -> chunk inspection -> reports."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    # 1. Prepare synthetic dataset CSVs mimicking CICIDS2017 structure
    monday_df = pd.DataFrame(
        {
            " Destination Port": [80, 443, 80],
            "Flow Duration": [100.0, 500.0, 250.0],
            "Flow Bytes/s": [1200.0, 4500.0, 800.0],
            "Timestamp": [
                "2017-07-03 09:00:00",
                "2017-07-03 10:00:00",
                "2017-07-03 11:00:00",
            ],
            " Label": ["BENIGN", "BENIGN", "BENIGN"],
        }
    )

    tuesday_df = pd.DataFrame(
        {
            " Destination Port": [22, 80, 22],
            "Flow Duration": [50.0, 300.0, 50.0],
            "Flow Bytes/s": [300.0, 1500.0, 300.0],
            "Timestamp": [
                "2017-07-04 09:30:00",
                "2017-07-04 10:00:00",
                "2017-07-04 09:30:00",  # Duplicate row
            ],
            " Label": ["SSH-Patator", "BENIGN", "SSH-Patator"],
        }
    )

    # 2. Package into mock MachineLearningCSV.zip
    zip_path = raw_dir / "MachineLearningCSV.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Monday-WorkingHours.csv", monday_df.to_csv(index=False))
        zf.writestr("Tuesday-WorkingHours.csv", tuesday_df.to_csv(index=False))

    # 3. Safe Extraction
    archive_sha = compute_sha256(zip_path)
    assert len(archive_sha) == 64
    extracted_files = safe_extract_zip(zip_path, raw_dir, expected_sha256=archive_sha)
    assert len(extracted_files) == 2

    # 4. Manifest Generation
    manifest = create_manifest_from_directory(raw_dir)
    assert manifest.total_files == 2
    manifest_file = raw_dir / "manifest.json"
    manifest.save(manifest_file)
    assert manifest_file.is_file()

    # 5. Chunk-based Forensic Inspection
    inspector = DatasetForensicInspector(chunk_size=2)
    report = inspector.inspect_directory(raw_dir)

    assert report.total_files == 2
    assert report.total_rows == 6
    assert report.total_benign == 4
    assert report.total_attacks == 2
    assert report.total_intra_file_duplicates == 1  # 1 duplicate in Tuesday
    assert report.schema_is_consistent is True

    # 6. Verify Reports Generation
    summary_md = report.generate_forensic_summary_markdown()
    assert "Monday-WorkingHours.csv" in summary_md
    assert "Tuesday-WorkingHours.csv" in summary_md

    label_md = report.generate_label_distribution_markdown()
    assert "SSH-Patator" in label_md
    assert "BENIGN" in label_md

    temporal_md = report.generate_temporal_distribution_markdown()
    assert "2017-07-03" in temporal_md
    assert "2017-07-04" in temporal_md

    dup_md = report.generate_duplicate_investigation_markdown()
    assert "Root Cause Analysis" in dup_md

    # 7. Update manifest with inspected counts
    manifest.total_rows = report.total_rows
    manifest.save(reports_dir / "dataset_manifest.json")
    loaded_manifest = manifest.load(reports_dir / "dataset_manifest.json")
    assert loaded_manifest.total_rows == 6
