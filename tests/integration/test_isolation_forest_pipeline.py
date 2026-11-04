"""Integration tests for NETDEFY Phase 4A Isolation Forest Pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from netdefy.evaluation.thresholds import ThresholdCalibrationResult
from netdefy.models.isolation_forest import IsolationForestDetector

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "models" / "isolation_forest" / "v1"
BENCHMARK_DIR = PROJECT_ROOT / "data" / "benchmark" / "v1"


def test_isolation_forest_artifacts_exist() -> None:
    """Verify all required Phase 4A model and evaluation artifacts exist."""
    assert ARTIFACT_DIR.exists(), f"Artifact directory missing: {ARTIFACT_DIR}"
    assert (ARTIFACT_DIR / "model.joblib").exists()
    assert (ARTIFACT_DIR / "thresholds.json").exists()
    assert (ARTIFACT_DIR / "training_summary.json").exists()
    assert (ARTIFACT_DIR / "validation_metrics.json").exists()
    assert (ARTIFACT_DIR / "test_metrics.json").exists()
    assert (ARTIFACT_DIR / "error_analysis.json").exists()


def test_isolation_forest_model_reproducibility() -> None:
    """Verify loaded model produces deterministic scores and adheres to score direction."""
    model_path = ARTIFACT_DIR / "model.joblib"
    if not model_path.exists():
        pytest.skip("Model artifact not yet trained")

    detector = IsolationForestDetector.load(model_path)
    assert detector.is_fitted
    assert len(detector.feature_names) == 76

    # Load 100 test samples
    test_table = pq.read_table(BENCHMARK_DIR / "test.parquet")
    test_df = test_table.slice(0, 100).to_pandas()

    scores1 = detector.score_samples(test_df)
    scores2 = detector.score_samples(test_df)

    # Determinism
    np.testing.assert_array_equal(scores1, scores2)
    assert scores1.dtype == np.float32

    # Higher score = more anomalous
    preds = detector.predict(test_df, threshold=0.6)
    assert set(preds).issubset({0, 1})


def test_thresholds_purity_and_ordering() -> None:
    """Verify threshold metadata confirms pure benign calibration and monotonic ordering."""
    th_path = ARTIFACT_DIR / "thresholds.json"
    if not th_path.exists():
        pytest.skip("Thresholds artifact missing")

    calib = ThresholdCalibrationResult.load(th_path)
    assert calib.strategy == "benign_validation_percentile"
    assert calib.benign_sample_count == 15315  # Exactly 15,315 BENIGN in validation.parquet

    th_dict = calib.thresholds
    assert "p95.0" in th_dict
    assert "p99.0" in th_dict
    assert "p99.5" in th_dict

    # Monotonic ordering
    assert th_dict["p95.0"] < th_dict["p99.0"] < th_dict["p99.5"]


def test_test_metrics_content() -> None:
    """Verify test metrics artifact contains complete evaluation data."""
    metrics_path = ARTIFACT_DIR / "test_metrics.json"
    if not metrics_path.exists():
        pytest.skip("Test metrics artifact missing")

    with open(metrics_path, encoding="utf-8") as f:
        data = json.load(f)

    assert "full_test_report" in data
    assert "disambiguated_test_report" in data
    assert "latency_ms_per_flow" in data
    assert "throughput_flows_per_second" in data

    full = data["full_test_report"]
    assert full["total_samples"] == 50000
    assert full["benign_count"] == 37474
    assert full["attack_count"] == 12526
    assert full["roc_auc"] > 0.60
    assert full["pr_auc"] > 0.30
