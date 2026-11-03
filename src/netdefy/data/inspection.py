"""Chunk-based forensic dataset inspection engine for network flow data."""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FileForensicReport:
    """Forensic report for a single network traffic CSV file."""

    filename: str
    file_size_bytes: int
    total_rows: int
    total_columns: int
    raw_columns: list[str]
    cleaned_columns: list[str]
    column_dtypes: dict[str, str]
    numeric_columns_count: int
    categorical_columns_count: int
    duplicate_headers: list[str]
    missing_values_per_column: dict[str, int]
    total_missing_values: int
    infinite_values_per_column: dict[str, int]
    total_infinite_values: int
    intra_file_duplicate_rows: int
    intra_file_duplicate_pct: float
    inter_file_duplicate_rows: int
    label_distribution: dict[str, int]
    benign_count: int
    attack_count: int
    attack_pct: float
    timestamp_column_found: bool
    timestamp_col_name: str | None
    min_timestamp: str | None
    max_timestamp: str | None
    unparseable_timestamps_count: int
    malformed_rows_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return asdict(self)


@dataclass
class DatasetForensicReport:
    """Comprehensive forensic report aggregating across all dataset files."""

    dataset_name: str
    inspected_at: str
    total_files: int
    total_size_bytes: int
    total_rows: int
    global_label_distribution: dict[str, int]
    total_benign: int
    total_attacks: int
    total_intra_file_duplicates: int
    total_inter_file_duplicates: int
    schema_is_consistent: bool
    schema_mismatches: dict[str, Any]
    file_reports: list[FileForensicReport]
    recommended_temporal_splits: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert aggregated report to dictionary."""
        return {
            "dataset_name": self.dataset_name,
            "inspected_at": self.inspected_at,
            "total_files": self.total_files,
            "total_size_bytes": self.total_size_bytes,
            "total_rows": self.total_rows,
            "global_label_distribution": self.global_label_distribution,
            "total_benign": self.total_benign,
            "total_attacks": self.total_attacks,
            "total_intra_file_duplicates": self.total_intra_file_duplicates,
            "total_inter_file_duplicates": self.total_inter_file_duplicates,
            "schema_is_consistent": self.schema_is_consistent,
            "schema_mismatches": self.schema_mismatches,
            "file_reports": [r.to_dict() for r in self.file_reports],
            "recommended_temporal_splits": self.recommended_temporal_splits,
        }

    def save_json(self, destination: Path) -> None:
        """Save report to JSON file."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Saved forensic report JSON to %s", destination)

    def generate_forensic_summary_markdown(self) -> str:
        """Generate high-level markdown summary."""
        lines = [
            f"# NETDEFY Dataset Forensic Inspection: {self.dataset_name}",
            "",
            f"- **Inspection Timestamp:** {self.inspected_at}",
            f"- **Total Files Analyzed:** {self.total_files}",
            f"- **Total Raw Volume:** {self.total_size_bytes / (1024**2):.2f} MB ({self.total_size_bytes:,} bytes)",
            f"- **Total Flow Records:** {self.total_rows:,}",
            f"- **Benign Flows:** {self.total_benign:,} ({(self.total_benign / max(1, self.total_rows)) * 100:.2f}%)",
            f"- **Attack Flows:** {self.total_attacks:,} ({(self.total_attacks / max(1, self.total_rows)) * 100:.2f}%)",
            f"- **Intra-File Duplicate Rows:** {self.total_intra_file_duplicates:,} ({(self.total_intra_file_duplicates / max(1, self.total_rows)) * 100:.2f}%)",
            f"- **Inter-File Duplicate Rows:** {self.total_inter_file_duplicates:,}",
            f"- **Schema Consistency:** {'CONSISTENT' if self.schema_is_consistent else 'INCONSISTENT'}",
            "",
            "## File-by-File Forensic Overview",
            "",
            "| Filename | Size (MB) | Rows | Cols | Missing | Infs | Dups | Attacks (%) | Time Window |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for r in self.file_reports:
            size_mb = r.file_size_bytes / (1024**2)
            time_win = (
                f"{r.min_timestamp[:10]} to {r.max_timestamp[:10]}"
                if r.min_timestamp and r.max_timestamp
                else "N/A"
            )
            lines.append(
                f"| `{r.filename}` | {size_mb:.2f} | {r.total_rows:,} | {r.total_columns} | "
                f"{r.total_missing_values:,} | {r.total_infinite_values:,} | "
                f"{r.intra_file_duplicate_rows:,} | {r.attack_pct:.2f}% | {time_win} |"
            )

        return "\n".join(lines)

    def generate_label_distribution_markdown(self) -> str:
        """Generate markdown breakdown of attack vs benign labels."""
        lines = [
            "# NETDEFY Label Distribution & Attack Profile",
            "",
            "| Label / Traffic Category | Flow Count | Percentage (%) | Class Type |",
            "| :--- | :--- | :--- | :--- |",
        ]
        sorted_labels = sorted(
            self.global_label_distribution.items(), key=lambda x: x[1], reverse=True
        )
        for label, count in sorted_labels:
            pct = (count / max(1, self.total_rows)) * 100.0
            ctype = "Benign Baseline" if "benign" in label.lower() else "Attack / Anomaly"
            lines.append(f"| `{label}` | {count:,} | {pct:.4f}% | {ctype} |")

        lines.extend(
            [
                "",
                "## Per-File Label Breakdown",
                "",
            ]
        )
        for r in self.file_reports:
            lines.append(f"### `{r.filename}`")
            lines.append(
                f"- **Total Rows:** {r.total_rows:,} | **Benign:** {r.benign_count:,} | **Attacks:** {r.attack_count:,} ({r.attack_pct:.2f}%)"
            )
            for lab, cnt in sorted(r.label_distribution.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  - `{lab}`: {cnt:,}")
            lines.append("")

        return "\n".join(lines)

    def generate_temporal_distribution_markdown(self) -> str:
        """Generate markdown analysis of timestamps and chronological spans."""
        lines = [
            "# NETDEFY Temporal Distribution & Chronological Sequencing",
            "",
            "This report documents the chronological boundaries of each file to design",
            "the strict, leakage-free temporal evaluation protocol.",
            "",
            "| File | First Observed Timestamp | Last Observed Timestamp | Unparseable Timestamps |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for r in self.file_reports:
            min_t = r.min_timestamp or "Not Found"
            max_t = r.max_timestamp or "Not Found"
            lines.append(
                f"| `{r.filename}` | `{min_t}` | `{max_t}` | {r.unparseable_timestamps_count:,} |"
            )

        lines.extend(
            [
                "",
                "## Temporal Partitioning Strategy Recommendations",
                "",
                "- **Training Partition (Day 1 - Monday & Day 2 - Tuesday Morning):**",
                "  Must consist exclusively of benign network behavior to establish normal communication baselines.",
                "- **Validation / Calibration Partition (Day 2 Afternoon & Day 3 - Wednesday):**",
                "  Used for threshold calibration (99th/99.5th percentile) and hyperparameter selection.",
                "- **Final Test Partition (Day 4 - Thursday & Day 5 - Friday):**",
                "  Strictly held out until final model evaluation to evaluate temporal decay on novel attacks.",
            ]
        )
        return "\n".join(lines)

    def generate_duplicate_investigation_markdown(self) -> str:
        """Generate forensic duplicate investigation report."""
        lines = [
            "# NETDEFY Duplicate Record & Data Leakage Forensic Investigation",
            "",
            "## 1. Executive Summary",
            "",
            f"- **Total Records Inspected:** {self.total_rows:,}",
            f"- **Exact Intra-File Duplicates:** {self.total_intra_file_duplicates:,} ({(self.total_intra_file_duplicates / max(1, self.total_rows)) * 100:.2f}%)",
            f"- **Exact Inter-File Duplicates:** {self.total_inter_file_duplicates:,}",
            "",
            "## 2. Root Cause Analysis in Network Telemetry",
            "",
            "Duplicate network flows occur primarily due to:",
            "1. **Packet Capture Tap Placement:** Dual-homed monitoring taps and switched port analyzers (SPAN)",
            "   duplicate bidirectional flow headers when packets cross multiple network interfaces.",
            "2. **TCP Retransmission & Keep-Alives:** Long-lived connection sessions generate identical flow",
            "   feature summaries across window timeouts.",
            "3. **FlowMeter Timeout Chunking:** Fixed active/idle timeout boundaries artificially shard",
            "   continuous network flows into identical statistical representations.",
            "",
            "## 3. Data Leakage Implications",
            "",
            "- **Train/Test Contamination:** If duplicate flows exist across partitions, random splitting",
            "   artificially inflates evaluation metrics because the model memorizes exact flow vectors.",
            "- **Temporal Splitting Remedy:** Chronological partitioning combined with deduplication",
            "   eliminates cross-partition identical flow memorization.",
            "- **Preservation Policy:** Raw files remain completely untouched in `data/raw/`; deduplication",
            "   will be executed strictly downstream in `src/netdefy/preprocessing/` for Phase 3.",
        ]
        return "\n".join(lines)

    def generate_feature_schema_markdown(self) -> str:
        """Generate comprehensive feature schema and data types markdown."""
        lines = [
            "# NETDEFY Network Flow Feature Schema & Type Distribution",
            "",
            f"**Schema Consistency Across Partitions:** {'CONSISTENT' if self.schema_is_consistent else 'MISMATCH DETECTED'}",
            "",
        ]

        if not self.schema_is_consistent and self.schema_mismatches:
            lines.extend(
                [
                    "### Schema Mismatches Detected",
                    "```json",
                    json.dumps(self.schema_mismatches, indent=2),
                    "```",
                    "",
                ]
            )

        if self.file_reports:
            sample_report = self.file_reports[0]
            lines.extend(
                [
                    f"### Canonical Feature Set ({sample_report.total_columns} Features)",
                    "",
                    f"- **Numeric Features:** {sample_report.numeric_columns_count}",
                    f"- **Categorical / String Features:** {sample_report.categorical_columns_count}",
                    "",
                    "| Canonical Feature Name | Inferred Dtype | Missing Count | Infinite Count |",
                    "| :--- | :--- | :--- | :--- |",
                ]
            )
            for col in sample_report.cleaned_columns:
                dtype = sample_report.column_dtypes.get(col, "unknown")
                missing = sample_report.missing_values_per_column.get(col, 0)
                infs = sample_report.infinite_values_per_column.get(col, 0)
                lines.append(f"| `{col}` | `{dtype}` | {missing:,} | {infs:,} |")

        return "\n".join(lines)


class DatasetForensicInspector:
    """Chunk-based dataset inspection engine designed for resource-constrained environments."""

    def __init__(
        self,
        chunk_size: int = 50000,
        label_column_hint: str = "Label",
        timestamp_column_hint: str = "Timestamp",
    ) -> None:
        """Initialize the forensic inspector.

        Args:
            chunk_size: Number of rows per processing chunk (default 50,000 for Apple M3 8GB).
            label_column_hint: Substring or name used to identify the label column.
            timestamp_column_hint: Substring or name used to identify the timestamp column.
        """
        self.chunk_size = chunk_size
        self.label_column_hint = label_column_hint.lower()
        self.timestamp_column_hint = timestamp_column_hint.lower()

    def inspect_file(
        self,
        file_path: Path,
        global_row_hashes: set[int] | None = None,
    ) -> FileForensicReport:
        """Inspect a single CSV file in chunks and compute forensic statistics.

        Args:
            file_path: Path to CSV file.
            global_row_hashes: Optional set of 64-bit integer hashes seen across previous files.

        Returns:
            FileForensicReport detailing file structure, health, and distributions.
        """
        file_size = file_path.stat().st_size
        logger.info(
            "Forensic inspection starting for %s (%.1f MB)", file_path.name, file_size / (1024**2)
        )

        # 1. Read header to inspect column names & detect duplicate headers
        with open(file_path, encoding="utf-8", errors="replace") as f:
            header_line = f.readline()
        raw_columns = [col.strip("\n\r") for col in header_line.split(",")]
        cleaned_columns = [col.strip() for col in raw_columns]

        seen_headers: set[str] = set()
        duplicate_headers: list[str] = []
        for col in cleaned_columns:
            if col in seen_headers and col not in duplicate_headers:
                duplicate_headers.append(col)
            seen_headers.add(col)

        # Identify label and timestamp columns
        label_col: str | None = None
        timestamp_col: str | None = None
        for col in cleaned_columns:
            col_l = col.lower()
            if self.label_column_hint in col_l:
                label_col = col
            if self.timestamp_column_hint in col_l:
                timestamp_col = col

        # Initialize accumulators
        total_rows = 0
        missing_counts: collections.Counter[str] = collections.Counter()
        infinite_counts: collections.Counter[str] = collections.Counter()
        label_counts: collections.Counter[str] = collections.Counter()
        column_dtypes: dict[str, str] = {}
        intra_duplicates = 0
        inter_duplicates = 0
        local_row_hashes: set[int] = set()

        min_dt: dt.datetime | None = None
        max_dt: dt.datetime | None = None
        unparseable_timestamps = 0
        malformed_rows = 0

        # Read CSV chunk-by-chunk to stay strictly within 8 GB memory boundaries
        csv_iterator = pd.read_csv(
            file_path,
            chunksize=self.chunk_size,
            low_memory=False,
            encoding="utf-8",
            on_bad_lines="warn",
        )

        for chunk_idx, chunk in enumerate(csv_iterator):
            # Clean chunk column names of leading/trailing spaces
            chunk.columns = [c.strip() for c in chunk.columns]
            chunk_rows = len(chunk)
            total_rows += chunk_rows

            if chunk_idx == 0:
                for col in chunk.columns:
                    column_dtypes[str(col)] = str(chunk[col].dtype)

            # Missing values per column
            chunk_nulls = chunk.isna().sum()
            for col_name, n_missing in chunk_nulls.items():
                if n_missing > 0:
                    missing_counts[str(col_name)] += int(n_missing)

            # Infinite values on numeric columns
            numeric_cols = chunk.select_dtypes(include=[np.number]).columns
            for num_col in numeric_cols:
                series = chunk[num_col]
                n_infs = int(np.isinf(series).sum())
                if n_infs > 0:
                    infinite_counts[str(num_col)] += n_infs

            # Label distribution
            if label_col and label_col in chunk.columns:
                val_counts = chunk[label_col].value_counts(dropna=False)
                for label_val, count in val_counts.items():
                    label_counts[str(label_val).strip()] += int(count)

            # Timestamp parsing
            if timestamp_col and timestamp_col in chunk.columns:
                parsed_ts = pd.to_datetime(
                    chunk[timestamp_col],
                    errors="coerce",
                    format="mixed",
                )
                invalid_ts = int(parsed_ts.isna().sum()) - int(chunk[timestamp_col].isna().sum())
                if invalid_ts > 0:
                    unparseable_timestamps += invalid_ts

                valid_dates = parsed_ts.dropna()
                if not valid_dates.empty:
                    chunk_min = valid_dates.min().to_pydatetime()
                    chunk_max = valid_dates.max().to_pydatetime()
                    min_dt = chunk_min if min_dt is None else min(min_dt, chunk_min)
                    max_dt = chunk_max if max_dt is None else max(max_dt, chunk_max)

            # Duplicate detection via 64-bit row hashing
            # Convert row values to fast string representation and hash
            for row_vals in chunk.itertuples(index=False, name=None):
                row_repr = str(row_vals).encode("utf-8")
                # 64-bit integer hash from MD5 prefix (minimal memory overhead)
                row_hash = int.from_bytes(hashlib.md5(row_repr).digest()[:8], "little")

                is_intra_dup = row_hash in local_row_hashes
                if is_intra_dup:
                    intra_duplicates += 1
                else:
                    local_row_hashes.add(row_hash)

                if global_row_hashes is not None:
                    if row_hash in global_row_hashes:
                        if not is_intra_dup:
                            inter_duplicates += 1
                    else:
                        global_row_hashes.add(row_hash)

        # Categorize benign vs attack
        benign_count = 0
        attack_count = 0
        for label, count in label_counts.items():
            if "benign" in label.lower():
                benign_count += count
            else:
                attack_count += count

        attack_pct = (attack_count / max(1, total_rows)) * 100.0
        intra_dup_pct = (intra_duplicates / max(1, total_rows)) * 100.0

        numeric_count = sum(
            1 for dt_str in column_dtypes.values() if "int" in dt_str or "float" in dt_str
        )
        categorical_count = len(column_dtypes) - numeric_count

        return FileForensicReport(
            filename=file_path.name,
            file_size_bytes=file_size,
            total_rows=total_rows,
            total_columns=len(cleaned_columns),
            raw_columns=raw_columns,
            cleaned_columns=cleaned_columns,
            column_dtypes=column_dtypes,
            numeric_columns_count=numeric_count,
            categorical_columns_count=categorical_count,
            duplicate_headers=duplicate_headers,
            missing_values_per_column=dict(missing_counts),
            total_missing_values=sum(missing_counts.values()),
            infinite_values_per_column=dict(infinite_counts),
            total_infinite_values=sum(infinite_counts.values()),
            intra_file_duplicate_rows=intra_duplicates,
            intra_file_duplicate_pct=intra_dup_pct,
            inter_file_duplicate_rows=inter_duplicates,
            label_distribution=dict(label_counts),
            benign_count=benign_count,
            attack_count=attack_count,
            attack_pct=attack_pct,
            timestamp_column_found=timestamp_col is not None,
            timestamp_col_name=timestamp_col,
            min_timestamp=min_dt.isoformat() if min_dt else None,
            max_timestamp=max_dt.isoformat() if max_dt else None,
            unparseable_timestamps_count=unparseable_timestamps,
            malformed_rows_count=malformed_rows,
        )

    def inspect_directory(
        self,
        raw_dir: Path,
        dataset_name: str = "CICIDS2017",
    ) -> DatasetForensicReport:
        """Inspect all CSV files within a directory in a memory-bounded streaming fashion.

        Args:
            raw_dir: Directory containing raw CSV files.
            dataset_name: Dataset identification label.

        Returns:
            DatasetForensicReport aggregating metrics across all files.
        """
        csv_files = sorted(
            [p for p in raw_dir.rglob("*.csv") if not p.name.startswith(".")],
            key=lambda p: p.name,
        )
        if not csv_files:
            return DatasetForensicReport(
                dataset_name=dataset_name,
                inspected_at=dt.datetime.now(dt.UTC).isoformat(),
                total_files=0,
                total_size_bytes=0,
                total_rows=0,
                global_label_distribution={},
                total_benign=0,
                total_attacks=0,
                total_intra_file_duplicates=0,
                total_inter_file_duplicates=0,
                schema_is_consistent=True,
                schema_mismatches={},
                file_reports=[],
                recommended_temporal_splits={},
            )

        file_reports: list[FileForensicReport] = []
        global_label_dist: collections.Counter[str] = collections.Counter()
        global_row_hashes: set[int] = set()

        total_size = 0
        total_rows = 0
        total_benign = 0
        total_attacks = 0
        total_intra_dups = 0
        total_inter_dups = 0

        # Process each file sequentially
        for file_path in csv_files:
            report = self.inspect_file(file_path, global_row_hashes=global_row_hashes)
            file_reports.append(report)

            total_size += report.file_size_bytes
            total_rows += report.total_rows
            total_benign += report.benign_count
            total_attacks += report.attack_count
            total_intra_dups += report.intra_file_duplicate_rows
            total_inter_dups += report.inter_file_duplicate_rows

            for lab, cnt in report.label_distribution.items():
                global_label_dist[lab] += cnt

        # Verify schema consistency across files
        schema_consistent = True
        schema_mismatches: dict[str, Any] = {}
        reference_cols = file_reports[0].cleaned_columns

        for rep in file_reports[1:]:
            if rep.cleaned_columns != reference_cols:
                schema_consistent = False
                missing = list(set(reference_cols) - set(rep.cleaned_columns))
                extra = list(set(rep.cleaned_columns) - set(reference_cols))
                schema_mismatches[rep.filename] = {
                    "missing_columns": missing,
                    "extra_columns": extra,
                }

        # Temporal split recommendations
        temporal_splits = {
            "strategy": "Chronological Day-Wise Partitioning",
            "principle": "Train on early benign baselines; validate on subsequent traffic; test on final days.",
            "leakage_guardrails": [
                "Drop all operational identifiers: Flow ID, Source IP, Destination IP, Timestamp, Source Port.",
                "Deduplicate exact flow matches across partitions prior to evaluation.",
                "Freeze anomaly detection thresholds strictly on validation data.",
            ],
        }

        return DatasetForensicReport(
            dataset_name=dataset_name,
            inspected_at=dt.datetime.now(dt.UTC).isoformat(),
            total_files=len(file_reports),
            total_size_bytes=total_size,
            total_rows=total_rows,
            global_label_distribution=dict(global_label_dist),
            total_benign=total_benign,
            total_attacks=total_attacks,
            total_intra_file_duplicates=total_intra_dups,
            total_inter_file_duplicates=total_inter_dups,
            schema_is_consistent=schema_consistent,
            schema_mismatches=schema_mismatches,
            file_reports=file_reports,
            recommended_temporal_splits=temporal_splits,
        )
