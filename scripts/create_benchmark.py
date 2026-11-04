#!/usr/bin/env python3
"""NETDEFY — Phase 3.2: 200K Hybrid Benchmark Construction Script.

Constructs four mutually exclusive partitions:
1. oneclass_train.parquet (100,000 rows, Monday BENIGN only)
2. classifier_train.parquet (30,000 rows, Tuesday + Wednesday)
3. validation.parquet (20,000 rows, Tuesday + Wednesday, disjoint from classifier_train)
4. test.parquet (50,000 rows, Thursday + Friday, chronological holdout)
Plus supplementary/rare_class_diagnostic.parquet.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import logging
import struct
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

# Add src to python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.benchmark")


def compute_canonical_hash(row_values: list[float]) -> str:
    """Compute a canonical 64-bit hex hash from float32 values.

    Normalizes negative zero to positive zero and uses IEEE-754 binary packing.
    """
    clean_vals = [0.0 if abs(v) < 1e-12 else float(v) for v in row_values]
    packed = struct.pack(f"<{len(clean_vals)}f", *clean_vals)
    return hashlib.sha256(packed).hexdigest()[:16]


def compute_file_sha256(file_path: Path) -> str:
    """Compute standard SHA-256 checksum of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_source_provenance(partition_type: str, raw_idx: int) -> tuple[str, str, int]:
    """Map partition-local raw row index back to canonical CSV filename and line number."""
    if partition_type == "train":
        return "Monday-WorkingHours.pcap_ISCX.csv", "Monday", raw_idx

    elif partition_type in ("validation", "classifier_train"):
        if raw_idx < 445909:
            return "Tuesday-WorkingHours.pcap_ISCX.csv", "Tuesday", raw_idx
        else:
            return "Wednesday-workingHours.pcap_ISCX.csv", "Wednesday", raw_idx - 445909

    elif partition_type == "test":
        if raw_idx < 170366:
            return (
                "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
                "Thursday",
                raw_idx,
            )
        elif raw_idx < 458968:
            return (
                "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
                "Thursday",
                raw_idx - 170366,
            )
        elif raw_idx < 650001:
            return "Friday-WorkingHours-Morning.pcap_ISCX.csv", "Friday", raw_idx - 458968
        elif raw_idx < 936468:
            return (
                "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
                "Friday",
                raw_idx - 650001,
            )
        else:
            return "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv", "Friday", raw_idx - 936468

    raise ValueError(f"Unknown partition type: {partition_type}")


def build_benchmark(
    processed_dir: Path,
    output_dir: Path,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute the full 200K benchmark construction pipeline."""
    start_time = time.perf_counter()
    process = psutil.Process()
    start_mem = process.memory_info().rss / (1024**2)

    processed_dir = processed_dir.resolve()
    output_dir = output_dir.resolve()

    logger.info(
        "Initializing 200K Benchmark Construction (seed=%d, initial RAM=%.2f MB)",
        seed,
        start_mem,
    )
    rng = np.random.default_rng(seed)

    # Prepare directories
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    supp_dir = output_dir / "supplementary"
    supp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load feature schema
    artifacts_dir = PROJECT_ROOT / "artifacts" / "preprocessing"
    with open(artifacts_dir / "feature_schema.json", encoding="utf-8") as f:
        schema_dict = json.load(f)
    feature_cols = schema_dict["retained_features_service_independent"]
    logger.info("Loaded feature schema: %d continuous features.", len(feature_cols))

    # Copy feature schema into benchmark metadata
    with open(metadata_dir / "feature_schema.json", "w", encoding="utf-8") as f:
        json.dump(schema_dict, f, indent=2)

    # -------------------------------------------------------------------------
    # PART 1: One-Class Training Partition (Monday BENIGN, 100,000 rows)
    # -------------------------------------------------------------------------
    logger.info("=== STEP 1: Constructing oneclass_train.parquet (100,000 rows) ===")
    train_raw_table = pq.read_table(processed_dir / "train" / "train_raw.parquet")
    train_raw_df = train_raw_table.to_pandas()
    assert (train_raw_df["Label"] == "BENIGN").all(), (
        "Fatal: Monday training contains non-BENIGN rows!"
    )

    # Sample 100,000 rows without replacement
    train_pool_size = len(train_raw_df)
    oneclass_train_indices = rng.choice(train_pool_size, size=100000, replace=False)
    oneclass_train_indices.sort()

    oneclass_train_df = train_raw_df.iloc[oneclass_train_indices].copy()
    logger.info("Sampled oneclass_train: %d rows (100%% BENIGN)", len(oneclass_train_df))

    # -------------------------------------------------------------------------
    # PART 2: Classifier Training & Validation (Tuesday + Wednesday, 30k + 20k)
    # -------------------------------------------------------------------------
    logger.info("=== STEP 2: Constructing classifier_train (30k) and validation (20k) ===")
    val_raw_table = pq.read_table(processed_dir / "validation" / "validation_raw.parquet")
    val_raw_df = val_raw_table.to_pandas()
    val_labels = val_raw_df["Label"]

    # Special allocation for rare Heartbleed (11 total rows)
    hb_indices = val_labels[val_labels == "Heartbleed"].index.to_numpy().copy()
    rng.shuffle(hb_indices)
    hb_train_idx = hb_indices[:7]
    hb_val_idx = hb_indices[7:]
    logger.info(
        "Allocated Heartbleed: %d to classifier_train, %d to validation",
        len(hb_train_idx),
        len(hb_val_idx),
    )

    # Proportional stratified sampling on remaining Tue/Wed pool
    non_hb_indices = val_labels[val_labels != "Heartbleed"].index.to_numpy().copy()
    target_cls_train = 30000 - len(hb_train_idx)
    target_val = 20000 - len(hb_val_idx)

    strat_labels = val_labels.loc[non_hb_indices]
    class_proportions = strat_labels.value_counts() / len(strat_labels)

    cls_train_sampled: list[int] = list(hb_train_idx)
    val_sampled: list[int] = list(hb_val_idx)

    # Define exact quotas to hit precisely 30,000 and 20,000
    for cls_name, prop in class_proportions.items():
        cls_pool = strat_labels[strat_labels == cls_name].index.to_numpy().copy()
        rng.shuffle(cls_pool)

        n_train = int(round(prop * target_cls_train))
        n_val = int(round(prop * target_val))

        # Adjust for rounding to hit exact target on BENIGN
        if cls_name == "BENIGN":
            n_train = target_cls_train - sum(
                int(round(p * target_cls_train))
                for c, p in class_proportions.items()
                if c != "BENIGN"
            )
            n_val = target_val - sum(
                int(round(p * target_val)) for c, p in class_proportions.items() if c != "BENIGN"
            )

        cls_train_sampled.extend(cls_pool[:n_train])
        val_sampled.extend(cls_pool[n_train : n_train + n_val])

    assert len(cls_train_sampled) == 30000, f"Expected 30,000, got {len(cls_train_sampled)}"
    assert len(val_sampled) == 20000, f"Expected 20,000, got {len(val_sampled)}"
    assert len(set(cls_train_sampled) & set(val_sampled)) == 0, "Fatal: Disjointness failed!"

    cls_train_sampled.sort()
    val_sampled.sort()

    classifier_train_df = val_raw_df.iloc[cls_train_sampled].copy()
    validation_df = val_raw_df.iloc[val_sampled].copy()

    logger.info("Sampled classifier_train: %d rows", len(classifier_train_df))
    logger.info("Sampled validation: %d rows", len(validation_df))

    # -------------------------------------------------------------------------
    # PART 3: Final Test Partition (Thursday + Friday, 50,000 rows)
    # -------------------------------------------------------------------------
    logger.info("=== STEP 3: Constructing test.parquet (50,000 rows) ===")
    test_raw_table = pq.read_table(processed_dir / "test" / "test_raw.parquet")
    test_raw_df = test_raw_table.to_pandas()
    test_labels = test_raw_df["Label"]

    # Proportional stratified sampling across Thu/Fri classes
    # Exact quotas ensuring every rare class has at least 1 exemplar
    exact_test_quotas = {
        "BENIGN": 37474,
        "PortScan": 6837,
        "DDoS": 5508,
        "Bot": 85,
        "Web Attack \ufffd Brute Force": 65,
        "Web Attack \ufffd XSS": 28,
        "Infiltration": 2,
        "Web Attack \ufffd Sql Injection": 1,
    }
    assert sum(exact_test_quotas.values()) == 50000, (
        f"Test quotas sum to {sum(exact_test_quotas.values())}"
    )

    test_sampled_indices: list[int] = []
    for cls_name, quota in exact_test_quotas.items():
        pool = test_labels[test_labels == cls_name].index.to_numpy().copy()
        rng.shuffle(pool)
        test_sampled_indices.extend(pool[:quota])

    assert len(test_sampled_indices) == 50000, (
        f"Expected 50,000 test rows, got {len(test_sampled_indices)}"
    )
    test_sampled_indices.sort()
    test_df = test_raw_df.iloc[test_sampled_indices].copy()
    logger.info("Sampled test: %d rows across %d classes", len(test_df), len(exact_test_quotas))

    # -------------------------------------------------------------------------
    # PART 4: Supplementary Rare-Class Diagnostic Dataset
    # -------------------------------------------------------------------------
    logger.info("=== STEP 4: Constructing rare_class_diagnostic.parquet ===")
    # Collect all rare attack instances from across the entire dataset:
    # 1. Heartbleed (all 11 from Wed)
    # 2. Infiltration (all 36 from Thu)
    # 3. Web Attack - Sql Injection (all 21 from Thu)
    # 4. Web Attack - XSS (all 652 from Thu)
    # 5. Web Attack - Brute Force (all 1,507 from Thu)
    # 6. Bot (all 1,966 from Fri)
    # 7. Matched sample of 2,000 BENIGN flows from Thursday/Friday
    diag_rows: list[pd.DataFrame] = []

    # Wed Heartbleed
    hb_all = val_raw_df[val_raw_df["Label"] == "Heartbleed"].copy()
    diag_rows.append(hb_all)

    # Thu/Fri rare attacks
    for rare_cls in [
        "Infiltration",
        "Web Attack \ufffd Sql Injection",
        "Web Attack \ufffd XSS",
        "Web Attack \ufffd Brute Force",
        "Bot",
    ]:
        rare_df = test_raw_df[test_raw_df["Label"] == rare_cls].copy()
        diag_rows.append(rare_df)

    # Matched benign baseline (2,000 rows from test)
    test_benign_pool = test_labels[test_labels == "BENIGN"].index.to_numpy().copy()
    rng.shuffle(test_benign_pool)
    benign_matched = test_raw_df.iloc[test_benign_pool[:2000]].copy()
    diag_rows.append(benign_matched)

    diagnostic_df = pd.concat(diag_rows, ignore_index=True)
    logger.info("Constructed rare_class_diagnostic: %d rows total", len(diagnostic_df))

    # -------------------------------------------------------------------------
    # PART 5: Save Parquet Datasets & Compute Checksums
    # -------------------------------------------------------------------------
    logger.info("=== STEP 5: Serializing Parquets with float32 precision ===")
    output_files = {
        "oneclass_train": output_dir / "oneclass_train.parquet",
        "classifier_train": output_dir / "classifier_train.parquet",
        "validation": output_dir / "validation.parquet",
        "test": output_dir / "test.parquet",
        "rare_class_diagnostic": supp_dir / "rare_class_diagnostic.parquet",
    }

    datasets = {
        "oneclass_train": oneclass_train_df,
        "classifier_train": classifier_train_df,
        "validation": validation_df,
        "test": test_df,
        "rare_class_diagnostic": diagnostic_df,
    }

    checksums: dict[str, str] = {}
    for name, path in output_files.items():
        df = datasets[name]
        # Guarantee float32 dtype on features and preserve index=False
        for col in feature_cols:
            df[col] = df[col].astype(np.float32)

        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, path)
        checksums[name] = compute_file_sha256(path)
        logger.info(
            "Saved %s: %d rows, %d cols, SHA-256=%s",
            path.name,
            len(df),
            len(df.columns),
            checksums[name][:12],
        )

    # -------------------------------------------------------------------------
    # PART 6: Generate Metadata & Source Row Manifest
    # -------------------------------------------------------------------------
    logger.info("=== STEP 6: Generating Provenance Manifests ===")
    source_row_records: dict[str, list[dict[str, Any]]] = {
        "oneclass_train": [],
        "classifier_train": [],
        "validation": [],
        "test": [],
    }

    partition_indices: dict[str, tuple[str, list[int], pd.DataFrame]] = {
        "oneclass_train": ("train", list(oneclass_train_indices), oneclass_train_df),
        "classifier_train": (
            "classifier_train",
            cls_train_sampled,
            classifier_train_df,
        ),
        "validation": ("validation", val_sampled, validation_df),
        "test": ("test", test_sampled_indices, test_df),
    }

    # Identify the 130 conflicting feature vectors in test_raw
    test_dups = test_raw_df[test_raw_df.duplicated(subset=feature_cols, keep=False)]
    test_conflict_groups = test_dups.groupby(feature_cols)["Label"].nunique()
    ambiguous_tuples = set(test_conflict_groups[test_conflict_groups > 1].index)
    logger.info("Identified %d ambiguous vectors in raw test pool.", len(ambiguous_tuples))

    ambiguous_vectors_present = set()
    ambiguity_audit: dict[str, Any] = {
        "conflicting_vectors_in_cicids2017": len(ambiguous_tuples),
        "conflicting_vectors_in_benchmark_test": 0,
        "ambiguous_rows_in_benchmark_test": 0,
        "ambiguous_rows_by_class": collections.defaultdict(int),
    }

    for part_name, (part_type, row_indices, df) in partition_indices.items():
        logger.info("Building source row provenance for %s...", part_name)
        feature_vals = df[feature_cols].values.tolist()
        labels_list = df["Label"].tolist()

        for b_idx, (r_idx, f_vals, lbl) in enumerate(
            zip(row_indices, feature_vals, labels_list, strict=True)
        ):
            f_hash = compute_canonical_hash(f_vals)
            src_file, src_day, f_row = get_source_provenance(part_type, int(r_idx))

            tup = tuple(f_vals)
            is_ambiguous = (part_name == "test") and (tup in ambiguous_tuples)
            if is_ambiguous:
                ambiguous_vectors_present.add(tup)
                ambiguity_audit["ambiguous_rows_in_benchmark_test"] += 1
                ambiguity_audit["ambiguous_rows_by_class"][lbl] += 1

            source_row_records[part_name].append(
                {
                    "benchmark_index": b_idx,
                    "partition": part_name,
                    "source_file": src_file,
                    "source_day": src_day,
                    "file_row_index": f_row,
                    "raw_partition_index": int(r_idx),
                    "canonical_hash": f_hash,
                    "label": lbl,
                    "is_ambiguous_flow": is_ambiguous,
                }
            )

    ambiguity_audit["conflicting_vectors_in_benchmark_test"] = len(ambiguous_vectors_present)
    ambiguity_audit["ambiguous_rows_by_class"] = dict(ambiguity_audit["ambiguous_rows_by_class"])

    # Write source row manifest
    with open(metadata_dir / "source_row_manifest.json", "w", encoding="utf-8") as f:
        json.dump(source_row_records, f, indent=2)

    # Write ambiguity manifest
    with open(metadata_dir / "ambiguity_manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "conflicting_vector_count_in_cicids2017": len(ambiguous_tuples),
                "ambiguity_summary_in_50k_test": ambiguity_audit,
            },
            f,
            indent=2,
        )

    # Write sampling config
    sampling_config = {
        "random_seed": seed,
        "target_sizes": {
            "oneclass_train": 100000,
            "classifier_train": 30000,
            "validation": 20000,
            "test": 50000,
            "total_benchmark": 200000,
        },
        "allocation_strategy": "Hybrid natural-stratified with rare-class preservation",
        "source_mapping": {
            "oneclass_train": "Monday-WorkingHours.pcap_ISCX.csv (100% BENIGN)",
            "classifier_train": "Tuesday + Wednesday (Multiclass labelled)",
            "validation": "Tuesday + Wednesday (Disjoint from classifier_train)",
            "test": "Thursday + Friday (Chronological final holdout)",
        },
    }
    with open(metadata_dir / "sampling_config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(sampling_config, f, sort_keys=False)

    # Write sampling audit
    sampling_audit = {
        "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "random_seed": seed,
        "class_distributions": {
            "oneclass_train": oneclass_train_df["Label"].value_counts().to_dict(),
            "classifier_train": classifier_train_df["Label"].value_counts().to_dict(),
            "validation": validation_df["Label"].value_counts().to_dict(),
            "test": test_df["Label"].value_counts().to_dict(),
            "rare_class_diagnostic": diagnostic_df["Label"].value_counts().to_dict(),
        },
        "source_day_distributions": {
            part: pd.Series([rec["source_day"] for rec in source_row_records[part]])
            .value_counts()
            .to_dict()
            for part in partition_indices
        },
        "uniqueness_summary": {
            "oneclass_train": {
                "total_rows": len(oneclass_train_df),
                "unique_feature_vectors": len(
                    set(oneclass_train_df[feature_cols].itertuples(index=False, name=None))
                ),
            },
            "classifier_train": {
                "total_rows": len(classifier_train_df),
                "unique_feature_vectors": len(
                    set(classifier_train_df[feature_cols].itertuples(index=False, name=None))
                ),
            },
            "validation": {
                "total_rows": len(validation_df),
                "unique_feature_vectors": len(
                    set(validation_df[feature_cols].itertuples(index=False, name=None))
                ),
            },
            "test": {
                "total_rows": len(test_df),
                "unique_feature_vectors": len(
                    set(test_df[feature_cols].itertuples(index=False, name=None))
                ),
            },
        },
    }
    with open(metadata_dir / "sampling_audit.json", "w", encoding="utf-8") as f:
        json.dump(sampling_audit, f, indent=2)

    # Write benchmark manifest
    duration = time.perf_counter() - start_time
    peak_mem = process.memory_info().rss / (1024**2)
    benchmark_manifest = {
        "benchmark_version": "v1",
        "creation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(duration, 2),
        "peak_memory_mb": round(peak_mem, 2),
        "total_benchmark_records": 200000,
        "files": {
            name: {
                "path": str(p.resolve().relative_to(PROJECT_ROOT.resolve())),
                "records": len(datasets[name]),
                "sha256": checksums[name],
                "size_mb": round(p.stat().st_size / (1024**2), 2),
            }
            for name, p in output_files.items()
        },
    }
    with open(metadata_dir / "benchmark_manifest.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_manifest, f, indent=2)

    logger.info(
        "Benchmark constructed successfully in %.2f s (Peak RAM: %.2f MB)", duration, peak_mem
    )
    return benchmark_manifest


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Construct NETDEFY 200K Benchmark.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed",
        help="Path to preprocessed parquet files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmark" / "v1",
        help="Path to output benchmark directory",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    args = parser.parse_args()

    build_benchmark(
        processed_dir=args.processed_dir,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
