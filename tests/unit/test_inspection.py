"""Unit tests for chunk-based dataset forensic inspection engine."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from netdefy.data.inspection import DatasetForensicInspector


def _create_sample_forensic_csv(path: Path) -> None:
    """Create a mock flow CSV containing edge cases (infinities, nulls, duplicates)."""
    df = pd.DataFrame(
        {
            " Destination Port": [80, 443, 80, 22, 80],
            "Flow Duration": [100.0, 200.0, 100.0, 50.0, 300.0],
            "Flow Bytes/s": [1000.0, np.inf, 1000.0, -np.inf, np.nan],
            "Timestamp": [
                "2017-07-03 09:00:00",
                "2017-07-03 09:15:00",
                "2017-07-03 09:00:00",  # Duplicate row
                "corrupted_time",
                "2017-07-03 10:00:00",
            ],
            " Label": [
                "BENIGN",
                "BENIGN",
                "BENIGN",
                "SSH-Patator",
                "BENIGN",
            ],
        }
    )
    df.to_csv(path, index=False)


def test_inspect_file_metrics(tmp_path: Path) -> None:
    """Verify single-file chunk inspection calculates all metrics accurately."""
    csv_file = tmp_path / "Tuesday-WorkingHours.csv"
    _create_sample_forensic_csv(csv_file)

    inspector = DatasetForensicInspector(chunk_size=2)  # Force small chunks
    report = inspector.inspect_file(csv_file)

    assert report.filename == "Tuesday-WorkingHours.csv"
    assert report.total_rows == 5
    assert report.total_columns == 5

    # Header whitespace cleaning
    assert " Destination Port" in report.raw_columns
    assert "Destination Port" in report.cleaned_columns
    assert "Label" in report.cleaned_columns

    # Missing & infinite values
    assert report.total_missing_values == 1
    assert report.total_infinite_values == 2
    assert report.infinite_values_per_column["Flow Bytes/s"] == 2

    # Duplicates (row 0 and row 2 are identical)
    assert report.intra_file_duplicate_rows == 1
    assert report.intra_file_duplicate_pct == 20.0

    # Labels
    assert report.benign_count == 4
    assert report.attack_count == 1
    assert report.attack_pct == 20.0
    assert report.label_distribution["BENIGN"] == 4
    assert report.label_distribution["SSH-Patator"] == 1

    # Timestamps
    assert report.timestamp_column_found is True
    assert report.min_timestamp is not None
    assert "2017-07-03" in report.min_timestamp
    assert report.unparseable_timestamps_count == 1


def test_inspect_directory_schema_consistency(tmp_path: Path) -> None:
    """Verify multi-file inspection detects schema matches and mismatches."""
    file1 = tmp_path / "Monday.csv"
    pd.DataFrame({"colA": [1, 2], "colB": [3, 4], "Label": ["BENIGN", "BENIGN"]}).to_csv(
        file1, index=False
    )

    file2 = tmp_path / "Tuesday.csv"
    pd.DataFrame({"colA": [5, 6], "colB": [7, 8], "Label": ["BENIGN", "DoS"]}).to_csv(
        file2, index=False
    )

    file3_mismatched = tmp_path / "Wednesday.csv"
    pd.DataFrame({"colA": [9], "colC_different": [10], "Label": ["DDoS"]}).to_csv(
        file3_mismatched, index=False
    )

    inspector = DatasetForensicInspector(chunk_size=10)

    # 1. Consistent subset
    sub_dir = tmp_path / "consistent"
    sub_dir.mkdir()
    file1.rename(sub_dir / "Monday.csv")
    file2.rename(sub_dir / "Tuesday.csv")

    report_consistent = inspector.inspect_directory(sub_dir)
    assert report_consistent.total_files == 2
    assert report_consistent.total_rows == 4
    assert report_consistent.total_benign == 3
    assert report_consistent.total_attacks == 1
    assert report_consistent.schema_is_consistent is True

    # 2. Add mismatched file
    file3_mismatched.rename(sub_dir / "Wednesday.csv")
    report_mismatched = inspector.inspect_directory(sub_dir)
    assert report_mismatched.total_files == 3
    assert report_mismatched.schema_is_consistent is False
    assert "Wednesday.csv" in report_mismatched.schema_mismatches


def test_inter_file_duplicate_detection(tmp_path: Path) -> None:
    """Verify tracking duplicate rows across multiple files."""
    file1 = tmp_path / "Day1.csv"
    file2 = tmp_path / "Day2.csv"

    # Both files share an identical row
    shared_row = {"Flow ID": 999, "Duration": 10.0, "Label": "BENIGN"}
    df1 = pd.DataFrame([shared_row, {"Flow ID": 101, "Duration": 20.0, "Label": "BENIGN"}])
    df2 = pd.DataFrame([shared_row, {"Flow ID": 202, "Duration": 30.0, "Label": "ATTACK"}])

    df1.to_csv(file1, index=False)
    df2.to_csv(file2, index=False)

    inspector = DatasetForensicInspector()
    report = inspector.inspect_directory(tmp_path)

    assert report.total_files == 2
    assert report.total_rows == 4
    # The shared row in Day2 is an inter-file duplicate
    assert report.total_inter_file_duplicates == 1


def test_report_markdown_and_json_generation(tmp_path: Path) -> None:
    """Verify formatting of all forensic summary markdown and json outputs."""
    csv_file = tmp_path / "Monday.csv"
    pd.DataFrame({"Timestamp": ["2017-07-03 10:00:00"], "Label": ["BENIGN"]}).to_csv(
        csv_file, index=False
    )

    inspector = DatasetForensicInspector()
    report = inspector.inspect_directory(tmp_path)

    summary_md = report.generate_forensic_summary_markdown()
    assert "# NETDEFY Dataset Forensic Inspection" in summary_md
    assert "Monday.csv" in summary_md

    label_md = report.generate_label_distribution_markdown()
    assert "BENIGN" in label_md

    temporal_md = report.generate_temporal_distribution_markdown()
    assert "2017-07-03" in temporal_md

    dup_md = report.generate_duplicate_investigation_markdown()
    assert "Data Leakage Implications" in dup_md

    schema_md = report.generate_feature_schema_markdown()
    assert "Canonical Feature Set" in schema_md

    json_path = tmp_path / "report.json"
    report.save_json(json_path)
    assert json_path.is_file()
