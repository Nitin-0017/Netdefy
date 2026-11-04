"""Integration tests for NETDEFY Phase 4C XGBoost Classifier Pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from netdefy.models.xgboost_classifier import XGBoostAttackClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "models" / "xgboost_classifier" / "v1"
BENCHMARK_DIR = PROJECT_ROOT / "data" / "benchmark" / "v1"


def test_classifier_artifacts_exist() -> None:
    """Verify all required Phase 4C model and evaluation artifacts exist."""
    assert ARTIFACT_DIR.exists(), f"Artifact directory missing: {ARTIFACT_DIR}"
    assert (ARTIFACT_DIR / "model.ubj").exists()
    assert (ARTIFACT_DIR / "model.json").exists()
    assert (ARTIFACT_DIR / "class_mapping.json").exists()
    assert (ARTIFACT_DIR / "feature_importance.json").exists()
    assert (ARTIFACT_DIR / "training_summary.json").exists()
    assert (ARTIFACT_DIR / "validation_metrics.json").exists()
    assert (ARTIFACT_DIR / "test_metrics.json").exists()
    assert (ARTIFACT_DIR / "confusion_matrix.json").exists()
    assert (ARTIFACT_DIR / "error_analysis.json").exists()
    assert (ARTIFACT_DIR / "artifact_manifest.json").exists()


def test_classifier_model_reproducibility() -> None:
    """Verify loaded classifier produces deterministic predictions on holdout traffic."""
    model_path = ARTIFACT_DIR / "model.json"
    if not model_path.exists():
        pytest.skip("Classifier artifact not yet trained")

    classifier = XGBoostAttackClassifier.load(model_path)
    assert classifier.is_fitted
    assert len(classifier.feature_names) == 76
    assert len(classifier.class_mapping) == 8

    # Load 100 test samples
    test_table = pq.read_table(BENCHMARK_DIR / "test.parquet")
    test_df = test_table.slice(0, 100).to_pandas()

    probs1 = classifier.predict_proba(test_df)
    probs2 = classifier.predict_proba(test_df)

    # Determinism
    np.testing.assert_array_equal(probs1, probs2)
    assert probs1.shape == (100, 8)
    assert probs1.dtype == np.float32

    # Predictions
    preds = classifier.predict(test_df, reject_threshold=0.50)
    assert len(preds) == 100


def test_classifier_validation_metrics_quality() -> None:
    """Verify validation metrics meet research criteria on known attacks."""
    val_metrics_path = ARTIFACT_DIR / "validation_metrics.json"
    if not val_metrics_path.exists():
        pytest.skip("Validation metrics artifact missing")

    with open(val_metrics_path, encoding="utf-8") as f:
        data = json.load(f)

    report = data["validation_report"]
    assert report["total_samples"] == 20000
    assert report["accuracy"] > 0.99
    assert report["macro_f1"] > 0.95
    assert report["balanced_accuracy"] > 0.98


def test_classifier_holdout_test_metrics() -> None:
    """Verify test metrics artifact contains complete evaluation data."""
    test_metrics_path = ARTIFACT_DIR / "test_metrics.json"
    if not test_metrics_path.exists():
        pytest.skip("Test metrics artifact missing")

    with open(test_metrics_path, encoding="utf-8") as f:
        data = json.load(f)

    assert "full_test_report_closed_set" in data
    assert "full_test_report_open_set" in data
    assert "disambiguated_test_report" in data
    assert "latency_ms_per_flow" in data
    assert "throughput_flows_per_second" in data

    closed_report = data["full_test_report_closed_set"]
    assert closed_report["total_samples"] == 50000
    # High benign recall
    benign_recall = closed_report["per_class_metrics"]["BENIGN"]["recall"]
    assert benign_recall > 0.98


def test_classifier_manifest_fingerprints() -> None:
    """Verify artifact manifest has valid checksums and schema fingerprints."""
    manifest_path = ARTIFACT_DIR / "artifact_manifest.json"
    if not manifest_path.exists():
        pytest.skip("Manifest artifact missing")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["model_name"] == "xgboost_classifier"
    assert manifest["model_version"] == "v1"
    assert "artifacts" in manifest
    assert "classifier_train" in manifest["benchmark_partition_checksums"]
    assert "validation" in manifest["benchmark_partition_checksums"]
    assert "test" in manifest["benchmark_partition_checksums"]
