#!/usr/bin/env python3
"""NETDEFY — Phase 3.2: 200K Benchmark Validation Suite.

Executes comprehensive programmatic verification of all 20 requirements for
the Phase 3.2 benchmark dataset (data/benchmark/v1).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.validate_benchmark")


def compute_file_sha256(file_path: Path) -> str:
    """Compute standard SHA-256 checksum of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class BenchmarkValidator:
    """Validates all 20 structural, numerical, and leakage-safe invariants of the benchmark."""

    def __init__(self, benchmark_dir: Path) -> None:
        self.benchmark_dir = benchmark_dir.resolve()
        self.metadata_dir = self.benchmark_dir / "metadata"
        self.supplementary_dir = self.benchmark_dir / "supplementary"
        self.results: list[dict[str, Any]] = []

    def log_check(self, req_id: int, name: str, passed: bool, details: str) -> None:
        status_str = "PASS" if passed else "FAIL"
        self.results.append(
            {
                "id": req_id,
                "name": name,
                "status": status_str,
                "details": details,
            }
        )
        if passed:
            logger.info("[REQ-%02d: PASS] %s — %s", req_id, name, details)
        else:
            logger.error("[REQ-%02d: FAIL] %s — %s", req_id, name, details)

    def validate_all(self) -> bool:
        logger.info("Starting Benchmark Validation on: %s", self.benchmark_dir)

        # Load metadata
        schema_path = self.metadata_dir / "feature_schema.json"
        manifest_path = self.metadata_dir / "benchmark_manifest.json"
        provenance_path = self.metadata_dir / "source_row_manifest.json"
        ambiguity_path = self.metadata_dir / "ambiguity_manifest.json"
        config_path = self.metadata_dir / "sampling_config.yaml"
        audit_path = self.metadata_dir / "sampling_audit.json"

        with open(schema_path, encoding="utf-8") as f:
            schema_data = json.load(f)
        feature_cols: list[str] = schema_data["retained_features_service_independent"]

        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)

        with open(provenance_path, encoding="utf-8") as f:
            provenance_data = json.load(f)

        with open(config_path, encoding="utf-8") as f:
            _ = yaml.safe_load(f)

        with open(audit_path, encoding="utf-8") as f:
            _ = json.load(f)

        # Load Parquet datasets
        oc_train_path = self.benchmark_dir / "oneclass_train.parquet"
        cls_train_path = self.benchmark_dir / "classifier_train.parquet"
        val_path = self.benchmark_dir / "validation.parquet"
        test_path = self.benchmark_dir / "test.parquet"
        rare_path = self.supplementary_dir / "rare_class_diagnostic.parquet"

        oc_train_df = pq.read_table(oc_train_path).to_pandas()
        cls_train_df = pq.read_table(cls_train_path).to_pandas()
        val_df = pq.read_table(val_path).to_pandas()
        test_df = pq.read_table(test_path).to_pandas()
        rare_df = pq.read_table(rare_path).to_pandas()

        datasets = {
            "oneclass_train": oc_train_df,
            "classifier_train": cls_train_df,
            "validation": val_df,
            "test": test_df,
        }

        # REQ-01: oneclass_train.parquet exists and has exactly 100,000 rows
        n_oc = len(oc_train_df)
        self.log_check(
            1,
            "oneclass_train row count",
            n_oc == 100000,
            f"Found {n_oc:,} rows (expected 100,000)",
        )

        # REQ-02: oneclass_train contains exclusively BENIGN labels (0 attack records)
        oc_attacks = (oc_train_df["Label"] != "BENIGN").sum()
        self.log_check(
            2,
            "oneclass_train pure BENIGN",
            oc_attacks == 0,
            f"Non-BENIGN rows: {oc_attacks}",
        )

        # REQ-03: oneclass_train contains only records sourced from Monday
        oc_days = {rec["source_day"] for rec in provenance_data["oneclass_train"]}
        self.log_check(
            3,
            "oneclass_train Monday source",
            oc_days == {"Monday"},
            f"Source days: {sorted(oc_days)}",
        )

        # REQ-04: classifier_train.parquet exists and has exactly 30,000 rows
        n_cls = len(cls_train_df)
        self.log_check(
            4,
            "classifier_train row count",
            n_cls == 30000,
            f"Found {n_cls:,} rows (expected 30,000)",
        )

        # REQ-05: classifier_train contains only records sourced from Tuesday and Wednesday
        cls_days = {rec["source_day"] for rec in provenance_data["classifier_train"]}
        self.log_check(
            5,
            "classifier_train Tue/Wed source",
            cls_days.issubset({"Tuesday", "Wednesday"}),
            f"Source days: {sorted(cls_days)}",
        )

        # REQ-06: validation.parquet exists and has exactly 20,000 rows
        n_val = len(val_df)
        self.log_check(
            6,
            "validation row count",
            n_val == 20000,
            f"Found {n_val:,} rows (expected 20,000)",
        )

        # REQ-07: validation contains only records sourced from Tuesday and Wednesday
        val_days = {rec["source_day"] for rec in provenance_data["validation"]}
        self.log_check(
            7,
            "validation Tue/Wed source",
            val_days.issubset({"Tuesday", "Wednesday"}),
            f"Source days: {sorted(val_days)}",
        )

        # REQ-08: classifier_train and validation have zero overlapping source records (disjoint row indices)
        cls_raw_indices = {
            (rec["source_file"], rec["file_row_index"])
            for rec in provenance_data["classifier_train"]
        }
        val_raw_indices = {
            (rec["source_file"], rec["file_row_index"]) for rec in provenance_data["validation"]
        }
        val_cls_overlap = len(cls_raw_indices & val_raw_indices)
        self.log_check(
            8,
            "classifier_train and validation disjointness",
            val_cls_overlap == 0,
            f"Overlapping source records: {val_cls_overlap}",
        )

        # REQ-09: test.parquet exists and has exactly 50,000 rows
        n_test = len(test_df)
        self.log_check(
            9,
            "test row count",
            n_test == 50000,
            f"Found {n_test:,} rows (expected 50,000)",
        )

        # REQ-10: test contains only records sourced from Thursday and Friday
        test_days = {rec["source_day"] for rec in provenance_data["test"]}
        self.log_check(
            10,
            "test Thu/Fri chronological holdout",
            test_days.issubset({"Thursday", "Friday"}),
            f"Source days: {sorted(test_days)}",
        )

        # REQ-11: Total benchmark records across the four partitions equals exactly 200,000
        total_benchmark = n_oc + n_cls + n_val + n_test
        self.log_check(
            11,
            "Total benchmark size 200,000",
            total_benchmark == 200000,
            f"Total records: {total_benchmark:,} (100k+30k+20k+50k)",
        )

        # REQ-12: All four primary partition files contain identical feature columns (76 continuous features + 1 Label column = 77 columns)
        expected_cols = sorted(feature_cols + ["Label"])
        cols_match = all(sorted(df.columns.tolist()) == expected_cols for df in datasets.values())
        self.log_check(
            12,
            "Identical feature schema across partitions",
            cols_match,
            f"76 continuous features + Label = 77 columns per partition (match: {cols_match})",
        )

        # REQ-13: No feature columns contain NaN, inf, -inf, or null values across all four partitions
        has_invalid = False
        invalid_details: list[str] = []
        for name, df in datasets.items():
            num_nans = df[feature_cols].isna().sum().sum()
            num_infs = np.isinf(df[feature_cols].to_numpy()).sum()
            if num_nans > 0 or num_infs > 0:
                has_invalid = True
                invalid_details.append(f"{name}: {num_nans} NaNs, {num_infs} Infs")
        self.log_check(
            13,
            "Clean numerical values (zero NaN/inf/null)",
            not has_invalid,
            "All partitions 100% clean" if not has_invalid else "; ".join(invalid_details),
        )

        # REQ-14: All 76 continuous features are stored with float32 precision
        dtypes_ok = all(
            all(df[col].dtype == np.float32 for col in feature_cols) for df in datasets.values()
        )
        self.log_check(
            14,
            "float32 precision enforcement",
            dtypes_ok,
            f"All 76 continuous features float32: {dtypes_ok}",
        )

        # REQ-15: Destination Port and Label are excluded from the continuous feature matrix
        port_in_features = "Destination Port" in feature_cols
        label_in_features = "Label" in feature_cols
        self.log_check(
            15,
            "Port and Label exclusion from feature matrix",
            (not port_in_features) and (not label_in_features),
            f"Destination Port excluded: {not port_in_features}, Label excluded from features: {not label_in_features}",
        )

        # REQ-16: All 14 CICIDS2017 attack categories present in source data are represented in the benchmark
        all_benchmark_labels = (
            set(cls_train_df["Label"]) | set(val_df["Label"]) | set(test_df["Label"])
        )
        all_attacks = all_benchmark_labels - {"BENIGN"}
        expected_14_attacks = {
            "FTP-Patator",
            "SSH-Patator",
            "DoS slowloris",
            "DoS Slowhttptest",
            "DoS Hulk",
            "DoS GoldenEye",
            "Heartbleed",
            "Web Attack \ufffd Brute Force",
            "Web Attack \ufffd XSS",
            "Web Attack \ufffd Sql Injection",
            "Infiltration",
            "Bot",
            "PortScan",
            "DDoS",
        }
        attacks_represented = expected_14_attacks.issubset(all_attacks)
        self.log_check(
            16,
            "All 14 attack categories represented",
            attacks_represented,
            f"Found {len(all_attacks)} attack classes across benchmark partitions (expected 14)",
        )

        # REQ-17: Rare attack classes preserved (>= 1 in test, Heartbleed split 7/4)
        test_labels_counts = test_df["Label"].value_counts().to_dict()
        rare_test_present = all(
            test_labels_counts.get(cls, 0) >= 1
            for cls in [
                "Bot",
                "Web Attack \ufffd Brute Force",
                "Web Attack \ufffd XSS",
                "Infiltration",
                "Web Attack \ufffd Sql Injection",
            ]
        )
        cls_hb = (cls_train_df["Label"] == "Heartbleed").sum()
        val_hb = (val_df["Label"] == "Heartbleed").sum()
        hb_split_ok = (cls_hb == 7) and (val_hb == 4)
        self.log_check(
            17,
            "Rare attack preservation and Heartbleed 7/4 split",
            rare_test_present and hb_split_ok,
            f"Rare classes in test: {rare_test_present}, Heartbleed cls/val: {cls_hb}/{val_hb}",
        )

        # REQ-18: rare_class_diagnostic.parquet exists and contains 100% of rare instances (6,193 records)
        n_rare = len(rare_df)
        rare_counts = rare_df["Label"].value_counts().to_dict()
        expected_rare_counts = {
            "BENIGN": 2000,
            "Bot": 1966,
            "Web Attack \ufffd Brute Force": 1507,
            "Web Attack \ufffd XSS": 652,
            "Infiltration": 36,
            "Web Attack \ufffd Sql Injection": 21,
            "Heartbleed": 11,
        }
        rare_counts_match = rare_counts == expected_rare_counts
        self.log_check(
            18,
            "Supplementary rare_class_diagnostic integrity",
            (n_rare == 6193) and rare_counts_match,
            f"Total rows: {n_rare:,} (expected 6,193), class breakdown match: {rare_counts_match}",
        )

        # REQ-19: Ambiguous records documented and quantified in test partition
        with open(ambiguity_path, encoding="utf-8") as f:
            ambig_data = json.load(f)
        n_ambig_test = ambig_data["ambiguity_summary_in_50k_test"][
            "ambiguous_rows_in_benchmark_test"
        ]
        n_ambig_classes = len(
            ambig_data["ambiguity_summary_in_50k_test"]["ambiguous_rows_by_class"]
        )
        self.log_check(
            19,
            "Ambiguity manifest documentation",
            n_ambig_test > 0 and n_ambig_classes > 0,
            f"Documented {n_ambig_test:,} ambiguous rows across {n_ambig_classes} classes in test",
        )

        # REQ-20: All metadata files exist, valid JSON/YAML, matching SHA-256 checksums
        checksums_valid = True
        checksum_details: list[str] = []
        for file_key, meta in manifest_data["files"].items():
            fpath = PROJECT_ROOT / meta["path"]
            actual_sha = compute_file_sha256(fpath)
            if actual_sha != meta["sha256"]:
                checksums_valid = False
                checksum_details.append(
                    f"{file_key}: expected {meta['sha256'][:10]} got {actual_sha[:10]}"
                )

        all_meta_exist = (
            schema_path.exists()
            and manifest_path.exists()
            and provenance_path.exists()
            and ambiguity_path.exists()
            and config_path.exists()
            and audit_path.exists()
        )
        self.log_check(
            20,
            "Metadata validity and file checksum integrity",
            all_meta_exist and checksums_valid,
            f"All 6 metadata files exist: {all_meta_exist}, SHA-256 match: {checksums_valid}",
        )

        all_passed = all(r["status"] == "PASS" for r in self.results)
        return all_passed

    def print_summary_table(self) -> None:
        print("\n" + "=" * 90)
        print("          NETDEFY — PHASE 3.2 BENCHMARK VALIDATION AUDIT SUMMARY          ")
        print("=" * 90)
        print(f"{'Req ID':<8}{'Requirement Name':<45}{'Status':<10}{'Details'}")
        print("-" * 90)
        for r in self.results:
            print(f"REQ-{r['id']:02d}   {r['name']:<45}{r['status']:<10}{r['details']}")
        print("=" * 90)
        passed_count = sum(1 for r in self.results if r["status"] == "PASS")
        print(f"TOTAL: {passed_count}/{len(self.results)} REQUIREMENTS PASSED.")
        print("=" * 90 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NETDEFY 200K Benchmark.")
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmark" / "v1",
        help="Path to benchmark directory",
    )
    args = parser.parse_args()

    validator = BenchmarkValidator(args.benchmark_dir)
    success = validator.validate_all()
    validator.print_summary_table()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
