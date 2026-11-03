#!/usr/bin/env python3
"""Forensic dataset inspection CLI for NETDEFY."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Add src to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from netdefy.config import load_config
from netdefy.data.inspection import DatasetForensicInspector
from netdefy.data.manifest import create_manifest_from_directory
from netdefy.utils.logging import setup_logging


def main() -> int:
    """Run chunk-based forensic inspection across raw dataset CSV files."""
    parser = argparse.ArgumentParser(description="Forensic inspection of CICIDS2017 network flows.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=project_root / "data" / "raw",
        help="Path to raw dataset directory (default: data/raw)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=project_root / "reports",
        help="Destination directory for reports (default: reports/)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50000,
        help="Row chunk size for streaming processing (default: 50,000)",
    )
    args = parser.parse_args()

    config = load_config(project_root / "configs" / "config.yaml")
    setup_logging(level=config.logging.level)

    print("=" * 80)
    print("       NETDEFY — CHUNK-BASED DATASET FORENSIC INSPECTION               ")
    print("=" * 80)

    raw_dir = args.raw_dir
    reports_dir = args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    inspector = DatasetForensicInspector(
        chunk_size=args.chunk_size,
        label_column_hint=config.data.label_column,
    )

    print(f"\nScanning directory: {raw_dir.resolve()}")
    print(f"Streaming chunk size: {args.chunk_size:,} rows\n")

    report = inspector.inspect_directory(raw_dir, dataset_name=config.data.dataset_name)

    if report.total_files == 0:
        print("[WARNING] No CSV files found in target directory.")
        print("Please acquire or extract the dataset archive first:")
        print("  python scripts/acquire_dataset.py\n")
        return 1

    # 1. Save Master JSON Report
    json_path = reports_dir / "dataset_forensic_summary.json"
    report.save_json(json_path)
    print(f"  • Forensic JSON saved:     {json_path}")

    # 2. Save Markdown Summary Report
    summary_md_path = reports_dir / "dataset_forensic_summary.md"
    summary_md_path.write_text(report.generate_forensic_summary_markdown(), encoding="utf-8")
    print(f"  • Summary Markdown saved:  {summary_md_path}")

    # 3. Save Label Distribution Reports (CSV & Markdown)
    label_md_path = reports_dir / "label_distribution.md"
    label_md_path.write_text(report.generate_label_distribution_markdown(), encoding="utf-8")
    print(f"  • Label Markdown saved:    {label_md_path}")

    label_rows = [
        {"Label": k, "Count": v, "Percentage": (v / report.total_rows) * 100.0}
        for k, v in report.global_label_distribution.items()
    ]
    label_csv_path = reports_dir / "label_distribution.csv"
    pd.DataFrame(label_rows).to_csv(label_csv_path, index=False)
    print(f"  • Label CSV saved:         {label_csv_path}")

    # 4. Save Temporal Distribution Reports (CSV & Markdown)
    temporal_md_path = reports_dir / "temporal_distribution.md"
    temporal_md_path.write_text(report.generate_temporal_distribution_markdown(), encoding="utf-8")
    print(f"  • Temporal Markdown saved: {temporal_md_path}")

    temporal_rows = [
        {
            "Filename": r.filename,
            "Min_Timestamp": r.min_timestamp,
            "Max_Timestamp": r.max_timestamp,
            "Unparseable_Count": r.unparseable_timestamps_count,
        }
        for r in report.file_reports
    ]
    temporal_csv_path = reports_dir / "temporal_distribution.csv"
    pd.DataFrame(temporal_rows).to_csv(temporal_csv_path, index=False)
    print(f"  • Temporal CSV saved:      {temporal_csv_path}")

    # 5. Save Duplicate Investigation Report
    dup_md_path = reports_dir / "duplicate_investigation.md"
    dup_md_path.write_text(report.generate_duplicate_investigation_markdown(), encoding="utf-8")
    print(f"  • Duplicate Report saved:  {dup_md_path}")

    # 6. Save Feature Schema Report
    schema_md_path = reports_dir / "feature_schema.md"
    schema_md_path.write_text(report.generate_feature_schema_markdown(), encoding="utf-8")
    print(f"  • Schema Report saved:     {schema_md_path}")

    # 7. Update Manifest with exact inspected counts
    manifest = create_manifest_from_directory(raw_dir, dataset_name=config.data.dataset_name)
    manifest.total_rows = report.total_rows
    # Map row and column counts
    file_map = {r.filename: r for r in report.file_reports}
    for f_entry in manifest.files:
        if f_entry.filename in file_map:
            f_entry.row_count = file_map[f_entry.filename].total_rows
            f_entry.column_count = file_map[f_entry.filename].total_columns
            f_entry.status = "inspected"

    manifest_path = raw_dir / "manifest.json"
    manifest.save(manifest_path)
    reports_manifest = reports_dir / "dataset_manifest.json"
    manifest.save(reports_manifest)
    print(f"  • Master Manifest saved:   {manifest_path}")

    # Print high-level CLI summary
    print("\n" + "=" * 80)
    print("                     FORENSIC INSPECTION SUMMARY                        ")
    print("=" * 80)
    print(f"  • Total Files:             {report.total_files}")
    print(f"  • Total Records:           {report.total_rows:,}")
    print(
        f"  • Benign Flows:            {report.total_benign:,} ({(report.total_benign / report.total_rows) * 100:.2f}%)"
    )
    print(
        f"  • Attack Flows:            {report.total_attacks:,} ({(report.total_attacks / report.total_rows) * 100:.2f}%)"
    )
    print(
        f"  • Intra-File Duplicates:   {report.total_intra_file_duplicates:,} ({(report.total_intra_file_duplicates / report.total_rows) * 100:.2f}%)"
    )
    print(f"  • Inter-File Duplicates:   {report.total_inter_file_duplicates:,}")
    print(f"  • Schema Consistent:       {report.schema_is_consistent}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
