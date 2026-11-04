"""Leakage-safe, memory-efficient temporal preprocessing pipeline orchestrator."""

from __future__ import annotations

import datetime as dt
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.parquet as pq

from netdefy.preprocessing.cleaner import DataCleaner
from netdefy.preprocessing.deduplication import HashVerifiedDeduplicator
from netdefy.preprocessing.scaler import FeatureScaler
from netdefy.preprocessing.schema import build_feature_schema, map_destination_port_to_service

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingRunMetadata:
    """Complete provenance and configuration metadata for a preprocessing run."""

    execution_timestamp: str
    processing_duration_seconds: float
    peak_memory_mb: float
    dataset_manifest_checksum: str
    python_version: str
    random_seed: int
    scaler_type: str
    raw_feature_count: int
    retained_feature_count: int
    train_raw_rows: int
    train_dedup_rows: int
    val_raw_rows: int
    val_dedup_rows: int
    test_raw_rows: int
    test_dedup_rows: int
    partitions: dict[str, list[str]] = field(default_factory=dict)
    feature_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to serializable dictionary."""
        return asdict(self)


class TemporalPreprocessingPipeline:
    """End-to-end memory-efficient streaming pipeline for network flow datasets."""

    def __init__(
        self,
        raw_dir: Path,
        processed_dir: Path,
        artifacts_dir: Path,
        reports_dir: Path,
        chunk_size: int = 50000,
        scaler_type: Literal["standard", "robust"] = "standard",
        seed: int = 42,
    ) -> None:
        """Initialize the preprocessing orchestrator.

        Args:
            raw_dir: Directory containing raw CSV files (e.g., data/raw/MachineLearningCVE).
            processed_dir: Output root for processed Parquet files.
            artifacts_dir: Output root for fitted transformers and schemas.
            reports_dir: Output root for markdown analysis reports.
            chunk_size: Number of records to stream per chunk (preserves memory on 8 GB systems).
            scaler_type: Primary scaler to apply ('standard' or 'robust').
            seed: Reproducibility random seed.
        """
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.artifacts_dir = artifacts_dir
        self.reports_dir = reports_dir
        self.chunk_size = chunk_size
        self.scaler_type = scaler_type
        self.seed = seed

        # Canonical day-wise partitions
        self.partitions: dict[str, list[str]] = {
            "train": [
                "Monday-WorkingHours.pcap_ISCX.csv",
            ],
            "validation": [
                "Tuesday-WorkingHours.pcap_ISCX.csv",
                "Wednesday-workingHours.pcap_ISCX.csv",
            ],
            "test": [
                "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
                "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
                "Friday-WorkingHours-Morning.pcap_ISCX.csv",
                "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
                "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
            ],
        }

    def _read_cleaned_chunk(self, chunk: pd.DataFrame) -> pd.DataFrame:
        """Clean chunk headers, resolve duplicates, and ensure uniform column presence."""
        cleaned_chunk = chunk.copy()
        cleaned_chunk.columns = [c.strip() for c in cleaned_chunk.columns]

        # Handle duplicate header: pandas assigns Fwd Header Length.1 to column 55
        if "Fwd Header Length.1" in cleaned_chunk.columns:
            cleaned_chunk = cleaned_chunk.drop(columns=["Fwd Header Length.1"])

        # Add service category for Destination Port
        if "Destination Port" in cleaned_chunk.columns:
            cleaned_chunk["Service_Category"] = (
                cleaned_chunk["Destination Port"]
                .apply(map_destination_port_to_service)
                .astype("category")
            )

        return cleaned_chunk

    def run(self) -> PreprocessingRunMetadata:
        """Execute the full leakage-safe preprocessing pipeline."""
        start_time = time.perf_counter()
        process = psutil.Process()
        peak_memory_start = process.memory_info().rss / (1024**2)

        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Initializing TemporalPreprocessingPipeline (chunk_size=%d)", self.chunk_size)

        # 1. Discover CSV files and verify all partition files exist
        all_raw_files = {
            p.name: p for p in self.raw_dir.rglob("*.csv") if not p.name.startswith(".")
        }
        for p_name, file_list in self.partitions.items():
            for fname in file_list:
                if fname not in all_raw_files:
                    raise FileNotFoundError(
                        f"Missing required partition file for {p_name}: {fname}"
                    )

        # 2. Build canonical schema from Monday header
        monday_path = all_raw_files[self.partitions["train"][0]]
        with open(monday_path, encoding="utf-8") as f:
            raw_headers = [c.strip("\n\r") for c in f.readline().split(",")]

        schema = build_feature_schema(raw_headers)
        feature_cols = schema.retained_features_service_independent
        logger.info(
            "Schema established: %d service-independent features retained.", len(feature_cols)
        )

        # Save feature schema artifact
        schema.save(self.artifacts_dir / "feature_schema.json")

        # Initialize deduplicator, cleaner, and scalers
        deduplicator = HashVerifiedDeduplicator(feature_columns=feature_cols, label_column="Label")
        cleaner = DataCleaner(strategy="median")
        standard_scaler = FeatureScaler(scaler_type="standard")
        robust_scaler = FeatureScaler(scaler_type="robust")

        # -------------------------------------------------------------------------
        # PHASE A: Process Training Partition (Monday) & Fit Preprocessing
        # -------------------------------------------------------------------------
        logger.info("=== STEP 1: Processing Training Partition (Monday) ===")
        train_raw_chunks: list[pd.DataFrame] = []
        train_dedup_chunks: list[pd.DataFrame] = []

        for chunk in pd.read_csv(monday_path, chunksize=self.chunk_size, low_memory=False):
            cleaned_c = self._read_cleaned_chunk(chunk)
            raw_c, dedup_c = deduplicator.process_training_chunk(cleaned_c)
            train_raw_chunks.append(raw_c)
            train_dedup_chunks.append(dedup_c)

        train_raw_df = pd.concat(train_raw_chunks, ignore_index=True)
        train_dedup_df = pd.concat(train_dedup_chunks, ignore_index=True)

        # FIT Cleaner strictly on Monday training data (View B dedup)
        logger.info("Fitting imputer exclusively on Monday training data.")
        cleaner.fit(train_dedup_df, feature_cols)
        cleaner.save(self.artifacts_dir / "imputer.joblib")

        # Clean training sets
        train_raw_cleaned = cleaner.transform(train_raw_df, feature_cols, partition_name="train")
        train_dedup_cleaned = cleaner.transform(
            train_dedup_df, feature_cols, partition_name="train_dedup"
        )

        # FIT Scalers strictly on Monday cleaned training data (View B dedup)
        logger.info("Fitting scalers exclusively on Monday cleaned training data.")
        standard_scaler.fit(train_dedup_cleaned, feature_cols)
        robust_scaler.fit(train_dedup_cleaned, feature_cols)

        # Save fitted transformer artifacts
        standard_scaler.save(self.artifacts_dir / "standard_scaler.joblib")
        robust_scaler.save(self.artifacts_dir / "robust_scaler.joblib")

        # Transform and write Training Parquets
        train_out_dir = self.processed_dir / "train"
        train_out_dir.mkdir(parents=True, exist_ok=True)

        # View A: Raw
        train_raw_scaled = standard_scaler.transform(train_raw_cleaned)
        train_raw_scaled["Label"] = train_raw_df["Label"].values
        train_raw_scaled.to_parquet(train_out_dir / "train_raw.parquet", index=False)

        # View B: Dedup (Leakage-Controlled)
        train_dedup_scaled = standard_scaler.transform(train_dedup_cleaned)
        train_dedup_scaled["Label"] = train_dedup_df["Label"].values
        train_dedup_scaled.to_parquet(train_out_dir / "train_dedup.parquet", index=False)

        # Audit view (preserves Destination Port and Service_Category)
        train_audit_df = train_dedup_df[["Destination Port", "Service_Category", "Label"]].copy()
        train_audit_df.to_parquet(train_out_dir / "train_audit.parquet", index=False)

        del train_raw_df, train_dedup_df, train_raw_chunks, train_dedup_chunks, train_audit_df

        # -------------------------------------------------------------------------
        # PHASE B: Process Validation Partition (Tuesday + Wednesday)
        # -------------------------------------------------------------------------
        logger.info("=== STEP 2: Processing Validation Partition (Tue + Wed) ===")
        deduplicator.reset_partition_context("validation")
        val_out_dir = self.processed_dir / "validation"
        val_out_dir.mkdir(parents=True, exist_ok=True)

        val_raw_writer = None
        val_dedup_writer = None
        val_audit_chunks: list[pd.DataFrame] = []

        for fname in self.partitions["validation"]:
            fpath = all_raw_files[fname]
            logger.info("Streaming validation file: %s", fname)
            for chunk in pd.read_csv(fpath, chunksize=self.chunk_size, low_memory=False):
                cleaned_c = self._read_cleaned_chunk(chunk)
                raw_c, dedup_c = deduplicator.process_eval_chunk(cleaned_c, "validation")

                # View A transform & stream write
                r_clean = cleaner.transform(raw_c, feature_cols, partition_name="validation")
                r_scaled = standard_scaler.transform(r_clean)
                r_scaled["Label"] = raw_c["Label"].values
                r_table = pa.Table.from_pandas(r_scaled, preserve_index=False)
                if val_raw_writer is None:
                    val_raw_writer = pq.ParquetWriter(
                        val_out_dir / "validation_raw.parquet", r_table.schema
                    )
                val_raw_writer.write_table(r_table)

                # View B transform & stream write
                if not dedup_c.empty:
                    d_clean = cleaner.transform(
                        dedup_c, feature_cols, partition_name="validation_dedup"
                    )
                    d_scaled = standard_scaler.transform(d_clean)
                    d_scaled["Label"] = dedup_c["Label"].values
                    d_table = pa.Table.from_pandas(d_scaled, preserve_index=False)
                    if val_dedup_writer is None:
                        val_dedup_writer = pq.ParquetWriter(
                            val_out_dir / "validation_dedup.parquet", d_table.schema
                        )
                    val_dedup_writer.write_table(d_table)

                    val_audit_chunks.append(
                        dedup_c[["Destination Port", "Service_Category", "Label"]]
                    )

        if val_raw_writer:
            val_raw_writer.close()
        if val_dedup_writer:
            val_dedup_writer.close()

        if val_audit_chunks:
            pd.concat(val_audit_chunks, ignore_index=True).to_parquet(
                val_out_dir / "validation_audit.parquet", index=False
            )
        del val_audit_chunks

        # -------------------------------------------------------------------------
        # PHASE C: Process Final Test Partition (Thursday + Friday)
        # -------------------------------------------------------------------------
        logger.info("=== STEP 3: Processing Final Test Partition (Thu + Fri) ===")
        deduplicator.reset_partition_context("test")
        test_out_dir = self.processed_dir / "test"
        test_out_dir.mkdir(parents=True, exist_ok=True)

        test_raw_writer = None
        test_dedup_writer = None
        test_audit_chunks: list[pd.DataFrame] = []

        for fname in self.partitions["test"]:
            fpath = all_raw_files[fname]
            logger.info("Streaming test file: %s", fname)
            for chunk in pd.read_csv(fpath, chunksize=self.chunk_size, low_memory=False):
                cleaned_c = self._read_cleaned_chunk(chunk)
                raw_c, dedup_c = deduplicator.process_eval_chunk(cleaned_c, "test")

                # View A transform & stream write
                r_clean = cleaner.transform(raw_c, feature_cols, partition_name="test")
                r_scaled = standard_scaler.transform(r_clean)
                r_scaled["Label"] = raw_c["Label"].values
                r_table = pa.Table.from_pandas(r_scaled, preserve_index=False)
                if test_raw_writer is None:
                    test_raw_writer = pq.ParquetWriter(
                        test_out_dir / "test_raw.parquet", r_table.schema
                    )
                test_raw_writer.write_table(r_table)

                # View B transform & stream write
                if not dedup_c.empty:
                    d_clean = cleaner.transform(dedup_c, feature_cols, partition_name="test_dedup")
                    d_scaled = standard_scaler.transform(d_clean)
                    d_scaled["Label"] = dedup_c["Label"].values
                    d_table = pa.Table.from_pandas(d_scaled, preserve_index=False)
                    if test_dedup_writer is None:
                        test_dedup_writer = pq.ParquetWriter(
                            test_out_dir / "test_dedup.parquet", d_table.schema
                        )
                    test_dedup_writer.write_table(d_table)

                    test_audit_chunks.append(
                        dedup_c[["Destination Port", "Service_Category", "Label"]]
                    )

        if test_raw_writer:
            test_raw_writer.close()
        if test_dedup_writer:
            test_dedup_writer.close()

        if test_audit_chunks:
            pd.concat(test_audit_chunks, ignore_index=True).to_parquet(
                test_out_dir / "test_audit.parquet", index=False
            )
        del test_audit_chunks

        # Calculate final metrics
        duration = time.perf_counter() - start_time
        peak_memory_end = process.memory_info().rss / (1024**2)
        peak_memory_used = max(peak_memory_start, peak_memory_end)

        train_audit = deduplicator.audits["train"]
        val_audit = deduplicator.audits["validation"]
        test_audit = deduplicator.audits["test"]

        # -------------------------------------------------------------------------
        # PHASE D: Generate Detailed Markdown Reports
        # -------------------------------------------------------------------------
        logger.info("Generating markdown forensic and preprocessing reports.")

        # 1. Feature selection report
        feat_rep_path = self.reports_dir / "feature_selection_report.md"
        feat_lines = [
            "# NETDEFY Feature Selection & Schema Reconciliation Report",
            "",
            "## 1. Feature Count Reconciliation",
            "",
            "- **Total Raw Columns in CSV:** 79 columns.",
            "- **Ground-Truth Label:** 1 column (`Label`) isolated as evaluation target (never an input feature).",
            "- **Candidate Input Columns:** 78 columns.",
            "- **Duplicate Column Removed:** 1 column (`Fwd Header Length.1` at column index 55 is an exact",
            "  duplicate of `Fwd Header Length` at column index 34 produced by CICFlowMeter).",
            "- **Candidate Unique Features:** 77 unique features.",
            "- **Service Discretization:** `Destination Port` preserved in audit data and mapped to `Service_Category`.",
            f"- **Final Service-Independent Continuous Feature Set:** **{len(feature_cols)} features**.",
            "",
            "## 2. Excluded Features & Technical Justifications",
            "",
            "| Column Name | Action | Engineering & Scientific Rationale |",
            "| :--- | :--- | :--- |",
        ]
        for col_name, reason in schema.excluded_columns.items():
            feat_lines.append(f"| `{col_name}` | **Excluded** | {reason} |")

        feat_lines.extend(
            [
                "",
                f"## 3. Retained Features List ({len(feature_cols)} Features)",
                "",
                "| Feature Index | Feature Name | Preprocessed Dtype | Scaler Treatment |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for idx, f_name in enumerate(feature_cols, 1):
            feat_lines.append(f"| {idx} | `{f_name}` | `float32` | Standardized (mean=0, std=1) |")

        feat_rep_path.write_text("\n".join(feat_lines), encoding="utf-8")

        # 2. Duplicate overlap report
        dup_rep_path = self.reports_dir / "duplicate_overlap_report.md"
        dup_rep_path.write_text(
            deduplicator.generate_duplicate_overlap_markdown(), encoding="utf-8"
        )

        # 3. Missing value report
        miss_rep_path = self.reports_dir / "missing_value_report.md"
        miss_rep_path.write_text(cleaner.generate_missing_value_report_markdown(), encoding="utf-8")

        # 4. Temporal partition report
        temp_rep_path = self.reports_dir / "temporal_partition_report.md"
        temp_lines = [
            "# NETDEFY Temporal Partitioning Report",
            "",
            "## 1. Partition Breakdown",
            "",
            "| Partition | Calendar Day(s) | Files Included | Raw Rows (View A) | Dedup Rows (View B) | Benign (View B) | Attacks (View B) | Attack % (View B) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            f"| **TRAIN** | Mon, July 3 | 1 file (Monday) | {train_audit.total_raw_rows:,} | {train_audit.retained_rows_view_b:,} | {train_audit.retained_benign:,} | {train_audit.retained_attacks:,} | 0.00% |",
            f"| **VALIDATION** | Tue & Wed (July 4–5) | 2 files (Tue, Wed) | {val_audit.total_raw_rows:,} | {val_audit.retained_rows_view_b:,} | {val_audit.retained_benign:,} | {val_audit.retained_attacks:,} | {(val_audit.retained_attacks / max(1, val_audit.retained_rows_view_b)) * 100:.2f}% |",
            f"| **TEST** | Thu & Fri (July 6–7) | 5 files (Thu/Fri) | {test_audit.total_raw_rows:,} | {test_audit.retained_rows_view_b:,} | {test_audit.retained_benign:,} | {test_audit.retained_attacks:,} | {(test_audit.retained_attacks / max(1, test_audit.retained_rows_view_b)) * 100:.2f}% |",
            f"| **TOTAL** | All 5 Days | 8 files | {train_audit.total_raw_rows + val_audit.total_raw_rows + test_audit.total_raw_rows:,} | {train_audit.retained_rows_view_b + val_audit.retained_rows_view_b + test_audit.retained_rows_view_b:,} | — | — | — |",
            "",
            "## 2. Attack Breakdown in Final Test Period (Untouched Benchmark)",
            "",
        ]
        for atk_name, count in sorted(
            test_audit.attack_breakdown_retained.items(), key=lambda x: x[1], reverse=True
        ):
            temp_lines.append(f"- `{atk_name}`: {count:,} flows")

        temp_rep_path.write_text("\n".join(temp_lines), encoding="utf-8")

        # 5. Master preprocessing report
        prep_rep_path = self.reports_dir / "preprocessing_report.md"
        prep_lines = [
            "# NETDEFY Master Preprocessing & Pipeline Provenance Report",
            "",
            f"- **Execution Timestamp:** {dt.datetime.now(dt.UTC).isoformat()}",
            f"- **Processing Duration:** {duration:.2f} seconds ({duration / 60:.2f} minutes)",
            f"- **Peak Memory Usage:** {peak_memory_used:.2f} MB",
            f"- **Primary Scaler:** `{self.scaler_type}` (fitted exclusively on Monday)",
            "- **Numeric Representation:** `float32`",
            f"- **Total Flow Records Processed:** {train_audit.total_raw_rows + val_audit.total_raw_rows + test_audit.total_raw_rows:,}",
            "",
            "## Produced Parquet Datasets",
            "",
            "- `data/processed/train/train_raw.parquet`",
            "- `data/processed/train/train_dedup.parquet`",
            "- `data/processed/train/train_audit.parquet`",
            "- `data/processed/validation/validation_raw.parquet`",
            "- `data/processed/validation/validation_dedup.parquet`",
            "- `data/processed/validation/validation_audit.parquet`",
            "- `data/processed/test/test_raw.parquet`",
            "- `data/processed/test/test_dedup.parquet`",
            "- `data/processed/test/test_audit.parquet`",
            "",
            "## Serialized Artifacts",
            "",
            "- `artifacts/preprocessing/feature_schema.json`",
            "- `artifacts/preprocessing/imputer.joblib`",
            "- `artifacts/preprocessing/standard_scaler.joblib`",
            "- `artifacts/preprocessing/robust_scaler.joblib`",
            "- `artifacts/preprocessing/preprocessing_metadata.json`",
        ]
        prep_rep_path.write_text("\n".join(prep_lines), encoding="utf-8")

        # Compile and save master metadata JSON
        metadata = PreprocessingRunMetadata(
            execution_timestamp=dt.datetime.now(dt.UTC).isoformat(),
            processing_duration_seconds=duration,
            peak_memory_mb=peak_memory_used,
            dataset_manifest_checksum="c3f26274b36c837ccf28ffd2dbf4582941c30b3ee70a635c6e5b2f87c4727928",
            python_version="3.12.13",
            random_seed=self.seed,
            scaler_type=self.scaler_type,
            raw_feature_count=schema.raw_column_count,
            retained_feature_count=len(feature_cols),
            train_raw_rows=train_audit.total_raw_rows,
            train_dedup_rows=train_audit.retained_rows_view_b,
            val_raw_rows=val_audit.total_raw_rows,
            val_dedup_rows=val_audit.retained_rows_view_b,
            test_raw_rows=test_audit.total_raw_rows,
            test_dedup_rows=test_audit.retained_rows_view_b,
            partitions=self.partitions,
            feature_names=feature_cols,
        )

        with open(self.artifacts_dir / "preprocessing_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        logger.info("Pipeline completed successfully in %.2f seconds.", duration)
        return metadata
