#!/usr/bin/env python3
"""Execute leakage-safe temporal preprocessing on CICIDS2017 flow data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from netdefy.config import load_config
from netdefy.preprocessing.pipeline import TemporalPreprocessingPipeline
from netdefy.utils.logging import setup_logging


def main() -> int:
    """Run full temporal preprocessing pipeline and artifact export."""
    parser = argparse.ArgumentParser(description="Preprocess CICIDS2017 network flow partitions.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=project_root / "data" / "raw" / "MachineLearningCVE",
        help="Path to directory containing extracted raw CSVs",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=project_root / "data" / "processed",
        help="Destination directory for processed Parquet datasets",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=project_root / "artifacts" / "preprocessing",
        help="Destination directory for fitted preprocessor artifacts",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=project_root / "reports",
        help="Destination directory for markdown analysis reports",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50000,
        help="Row streaming chunk size (default: 50,000 for Apple Silicon 8 GB)",
    )
    parser.add_argument(
        "--scaler",
        type=str,
        choices=["standard", "robust"],
        default="standard",
        help="Primary feature scaler to apply (default: standard)",
    )
    args = parser.parse_args()

    config = load_config(project_root / "configs" / "config.yaml")
    setup_logging(level=config.logging.level)

    print("=" * 80)
    print("       NETDEFY — LEAKAGE-SAFE TEMPORAL PREPROCESSING PIPELINE          ")
    print("=" * 80)
    print(f"Raw Input Directory:       {args.raw_dir.resolve()}")
    print(f"Processed Output Dir:      {args.processed_dir.resolve()}")
    print(f"Artifacts Destination:     {args.artifacts_dir.resolve()}")
    print(f"Reports Destination:       {args.reports_dir.resolve()}")
    print(f"Streaming Chunk Size:      {args.chunk_size:,} rows")
    print(f"Primary Scaler Type:       {args.scaler}")
    print("=" * 80)

    pipeline = TemporalPreprocessingPipeline(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        artifacts_dir=args.artifacts_dir,
        reports_dir=args.reports_dir,
        chunk_size=args.chunk_size,
        scaler_type=args.scaler,
        seed=config.system.seed,
    )

    metadata = pipeline.run()

    print("\n" + "=" * 80)
    print("                  PREPROCESSING EXECUTION COMPLETE                     ")
    print("=" * 80)
    print(
        f"  • Processing Duration:     {metadata.processing_duration_seconds:.2f} seconds ({metadata.processing_duration_seconds / 60:.2f} min)"
    )
    print(f"  • Peak Memory Usage:       {metadata.peak_memory_mb:.2f} MB")
    print(f"  • Raw Feature Count:       {metadata.raw_feature_count}")
    print(f"  • Retained Feature Count:  {metadata.retained_feature_count}")
    print(f"  • Training Rows (View A):  {metadata.train_raw_rows:,}")
    print(f"  • Training Rows (View B):  {metadata.train_dedup_rows:,}")
    print(f"  • Val Rows (View A):       {metadata.val_raw_rows:,}")
    print(f"  • Val Rows (View B):       {metadata.val_dedup_rows:,}")
    print(f"  • Test Rows (View A):      {metadata.test_raw_rows:,}")
    print(f"  • Test Rows (View B):      {metadata.test_dedup_rows:,}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
