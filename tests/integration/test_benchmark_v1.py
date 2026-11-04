"""Integration tests for NETDEFY Phase 3.2: 200K Benchmark Dataset (v1)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pyarrow.parquet as pq
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARK_DIR = PROJECT_ROOT / "data" / "benchmark" / "v1"


def compute_file_sha256(file_path: Path) -> str:
    """Compute standard SHA-256 checksum."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture(scope="module")
def benchmark_metadata() -> dict[str, Any]:
    manifest_path = BENCHMARK_DIR / "metadata" / "benchmark_manifest.json"
    if not manifest_path.exists():
        pytest.skip("Benchmark v1 manifest does not exist")
    with open(manifest_path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


@pytest.fixture(scope="module")
def source_provenance() -> dict[str, list[dict[str, Any]]]:
    prov_path = BENCHMARK_DIR / "metadata" / "source_row_manifest.json"
    if not prov_path.exists():
        pytest.skip("Source row manifest does not exist")
    with open(prov_path, encoding="utf-8") as f:
        return cast(dict[str, list[dict[str, Any]]], json.load(f))


@pytest.fixture(scope="module")
def feature_schema() -> list[str]:
    schema_path = BENCHMARK_DIR / "metadata" / "feature_schema.json"
    if not schema_path.exists():
        pytest.skip("Feature schema does not exist")
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    return cast(list[str], schema["retained_features_service_independent"])


def test_benchmark_files_and_checksums(benchmark_metadata: dict[str, Any]) -> None:
    """Verify that all Parquet files exist and match their registered SHA-256."""
    files = benchmark_metadata["files"]
    assert len(files) == 5
    for file_key, meta in files.items():
        fpath = PROJECT_ROOT / meta["path"]
        assert fpath.exists(), f"Missing benchmark file: {meta['path']}"
        actual_sha = compute_file_sha256(fpath)
        assert actual_sha == meta["sha256"], f"Checksum mismatch for {file_key}"


def test_partition_row_counts() -> None:
    """Verify exact sample allocations across all partitions."""
    oc_train = pq.read_table(BENCHMARK_DIR / "oneclass_train.parquet")
    cls_train = pq.read_table(BENCHMARK_DIR / "classifier_train.parquet")
    val = pq.read_table(BENCHMARK_DIR / "validation.parquet")
    test = pq.read_table(BENCHMARK_DIR / "test.parquet")
    rare = pq.read_table(BENCHMARK_DIR / "supplementary" / "rare_class_diagnostic.parquet")

    assert len(oc_train) == 100000
    assert len(cls_train) == 30000
    assert len(val) == 20000
    assert len(test) == 50000
    assert len(rare) == 6193

    total_benchmark = len(oc_train) + len(cls_train) + len(val) + len(test)
    assert total_benchmark == 200000


def test_oneclass_train_pure_benign_monday(
    source_provenance: dict[str, list[dict[str, Any]]],
) -> None:
    """Verify one-class training set is 100% BENIGN and 100% Monday."""
    df = pq.read_table(BENCHMARK_DIR / "oneclass_train.parquet").to_pandas()
    assert (df["Label"] == "BENIGN").all()

    days = {rec["source_day"] for rec in source_provenance["oneclass_train"]}
    assert days == {"Monday"}


def test_classifier_train_and_val_disjoint_provenance(
    source_provenance: dict[str, list[dict[str, Any]]],
) -> None:
    """Verify classifier_train and validation are completely disjoint and Tue/Wed."""
    cls_days = {rec["source_day"] for rec in source_provenance["classifier_train"]}
    val_days = {rec["source_day"] for rec in source_provenance["validation"]}

    assert cls_days.issubset({"Tuesday", "Wednesday"})
    assert val_days.issubset({"Tuesday", "Wednesday"})

    cls_records = {
        (rec["source_file"], rec["file_row_index"]) for rec in source_provenance["classifier_train"]
    }
    val_records = {
        (rec["source_file"], rec["file_row_index"]) for rec in source_provenance["validation"]
    }
    overlap = cls_records & val_records
    assert len(overlap) == 0, f"Found {len(overlap)} overlapping records between cls_train and val!"


def test_test_partition_holdout(source_provenance: dict[str, list[dict[str, Any]]]) -> None:
    """Verify test partition contains only Thursday and Friday traffic."""
    test_days = {rec["source_day"] for rec in source_provenance["test"]}
    assert test_days == {"Thursday", "Friday"}


def test_schema_dtypes_and_cleanliness(feature_schema: list[str]) -> None:
    """Verify 76 float32 features, no NaN/inf, and exclusion of Port and Label."""
    assert len(feature_schema) == 76
    assert "Destination Port" not in feature_schema
    assert "Label" not in feature_schema

    for p_name in ["oneclass_train", "classifier_train", "validation", "test"]:
        df = pq.read_table(BENCHMARK_DIR / f"{p_name}.parquet").to_pandas()
        assert len(df.columns) == 77
        assert sorted(df.columns.tolist()) == sorted(feature_schema + ["Label"])

        # Check dtypes
        for col in feature_schema:
            assert df[col].dtype == np.float32

        # Check clean values
        assert not df[feature_schema].isna().any().any()
        assert not np.isinf(df[feature_schema].to_numpy()).any()


def test_attack_representation_and_rare_split() -> None:
    """Verify all 14 attack classes are represented and Heartbleed is split 7/4."""
    cls_df = pq.read_table(BENCHMARK_DIR / "classifier_train.parquet").to_pandas()
    val_df = pq.read_table(BENCHMARK_DIR / "validation.parquet").to_pandas()
    test_df = pq.read_table(BENCHMARK_DIR / "test.parquet").to_pandas()

    all_labels = set(cls_df["Label"]) | set(val_df["Label"]) | set(test_df["Label"])
    attack_labels = all_labels - {"BENIGN"}
    assert len(attack_labels) == 14

    # Heartbleed split
    assert (cls_df["Label"] == "Heartbleed").sum() == 7
    assert (val_df["Label"] == "Heartbleed").sum() == 4

    # Rare classes present in test
    test_counts = test_df["Label"].value_counts()
    for rare_cls in [
        "Bot",
        "Web Attack \ufffd Brute Force",
        "Web Attack \ufffd XSS",
        "Infiltration",
        "Web Attack \ufffd Sql Injection",
    ]:
        assert test_counts.get(rare_cls, 0) >= 1


def test_rare_class_diagnostic_exact_composition() -> None:
    """Verify supplementary rare_class_diagnostic has all instances of rare attacks."""
    df = pq.read_table(
        BENCHMARK_DIR / "supplementary" / "rare_class_diagnostic.parquet"
    ).to_pandas()
    counts = df["Label"].value_counts().to_dict()

    expected = {
        "BENIGN": 2000,
        "Bot": 1966,
        "Web Attack \ufffd Brute Force": 1507,
        "Web Attack \ufffd XSS": 652,
        "Infiltration": 36,
        "Web Attack \ufffd Sql Injection": 21,
        "Heartbleed": 11,
    }
    assert counts == expected
    assert len(df) == 6193


def test_ambiguity_tracking() -> None:
    """Verify ambiguity manifest captures ambiguous rows in test partition."""
    ambig_path = BENCHMARK_DIR / "metadata" / "ambiguity_manifest.json"
    assert ambig_path.exists()
    with open(ambig_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["conflicting_vector_count_in_cicids2017"] == 130
    summary = data["ambiguity_summary_in_50k_test"]
    assert summary["conflicting_vectors_in_benchmark_test"] > 0
    assert summary["ambiguous_rows_in_benchmark_test"] > 0
    assert "PortScan" in summary["ambiguous_rows_by_class"]
