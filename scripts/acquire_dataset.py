#!/usr/bin/env python3
"""Dataset acquisition and integrity verification CLI for NETDEFY."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from netdefy.config import load_config
from netdefy.data.acquisition import (
    inspect_raw_data_directory,
    safe_extract_zip,
)
from netdefy.data.manifest import create_manifest_from_directory
from netdefy.utils.logging import setup_logging


def main() -> int:
    """Execute raw dataset acquisition inspection and extraction."""
    parser = argparse.ArgumentParser(description="Acquire and verify CICIDS2017 raw dataset.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=project_root / "data" / "raw",
        help="Path to raw data directory (default: data/raw)",
    )
    parser.add_argument(
        "--auto-extract",
        action="store_true",
        default=True,
        help="Automatically extract archive if found",
    )
    args = parser.parse_args()

    config = load_config(project_root / "configs" / "config.yaml")
    setup_logging(level=config.logging.level)

    print("=" * 80)
    print("       NETDEFY — RAW DATASET ACQUISITION & INTEGRITY VERIFICATION       ")
    print("=" * 80)

    raw_dir = args.raw_dir
    status = inspect_raw_data_directory(raw_dir)

    print(f"\nTarget Raw Directory: {raw_dir.resolve()}")
    print(f"Acquisition Status:   {status.summary()}")

    if status.is_ready_for_inspection:
        print(f"\n[SUCCESS] {len(status.csv_files)} CSV files detected in raw directory:")
        for idx, f in enumerate(status.csv_files, 1):
            size_mb = f.stat().st_size / (1024**2)
            print(f"  {idx}. {f.name:<45} ({size_mb:>7.2f} MB)")

        # Generate or update manifest
        manifest = create_manifest_from_directory(raw_dir, dataset_name=config.data.dataset_name)
        manifest_path = raw_dir / "manifest.json"
        manifest.save(manifest_path)

        # Mirror manifest to reports/
        reports_manifest = project_root / "reports" / "dataset_manifest.json"
        manifest.save(reports_manifest)
        print(f"\nManifest successfully updated at: {manifest_path}")
        return 0

    if status.archive_found and status.archive_path is not None:
        print(f"\n[FOUND] Archive detected: {status.archive_path.name}")
        print(f"  • Size:    {status.archive_size_bytes / (1024**2):.2f} MB")
        if status.archive_sha256:
            print(f"  • SHA-256: {status.archive_sha256}")

        if args.auto_extract:
            print("\nExtracting archive safely...")
            extracted = safe_extract_zip(status.archive_path, raw_dir)
            print(f"[SUCCESS] Extracted {len(extracted)} files.")

            manifest = create_manifest_from_directory(
                raw_dir, dataset_name=config.data.dataset_name
            )
            manifest_path = raw_dir / "manifest.json"
            manifest.save(manifest_path)
            reports_manifest = project_root / "reports" / "dataset_manifest.json"
            manifest.save(reports_manifest)
            print(f"Manifest written to: {manifest_path}")
            return 0
        else:
            print("Auto-extraction disabled. Run with --auto-extract to extract archive.")
            return 0

    # Archive not found -> Display manual download instructions
    print(f"\n{status.instructions}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
