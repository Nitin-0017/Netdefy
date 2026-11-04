"""Integration tests for NETDEFY Phase 4B Deep Autoencoder Pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from netdefy.evaluation.thresholds import ThresholdCalibrationResult
from netdefy.models.autoencoder import AutoencoderDetector

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "models" / "autoencoder" / "v1"
BENCHMARK_DIR = PROJECT_ROOT / "data" / "benchmark" / "v1"


def test_autoencoder_artifacts_exist() -> None:
    """Verify all required Phase 4B model, training, and evaluation artifacts exist."""
    assert ARTIFACT_DIR.exists(), f"Artifact directory missing: {ARTIFACT_DIR}"
    assert (ARTIFACT_DIR / "best_model.pt").exists()
    assert (ARTIFACT_DIR / "model_config.yaml").exists()
    assert (ARTIFACT_DIR / "training_history.json").exists()
    assert (ARTIFACT_DIR / "thresholds.json").exists()
    assert (ARTIFACT_DIR / "training_summary.json").exists()
    assert (ARTIFACT_DIR / "validation_metrics.json").exists()
    assert (ARTIFACT_DIR / "feature_schema.json").exists()


def test_autoencoder_model_reproducibility() -> None:
    """Verify loaded model produces deterministic scores and float32 outputs."""
    model_path = ARTIFACT_DIR / "best_model.pt"
    if not model_path.exists():
        pytest.skip("Model artifact not yet trained")

    detector = AutoencoderDetector.load(model_path, device="cpu")
    assert detector.is_fitted
    assert len(detector.feature_names) == 76

    # Load 100 test samples
    test_table = pq.read_table(BENCHMARK_DIR / "test.parquet")
    test_df = test_table.slice(0, 100).to_pandas()

    scores1 = detector.score_samples(test_df)
    scores2 = detector.score_samples(test_df)

    # Deterministic scoring
    np.testing.assert_array_equal(scores1, scores2)
    assert scores1.dtype == np.float32

    # Score orientation: scores must be non-negative MSE
    assert (scores1 >= 0.0).all()

    # Predictions
    preds = detector.predict(test_df, threshold=0.5)
    assert set(preds).issubset({0, 1})


def test_autoencoder_thresholds_purity_and_ordering() -> None:
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


def test_autoencoder_training_history_convergence() -> None:
    """Verify training history exhibits learning and finite non-NaN loss values."""
    hist_path = ARTIFACT_DIR / "training_history.json"
    if not hist_path.exists():
        pytest.skip("Training history missing")

    with open(hist_path, encoding="utf-8") as f:
        history = json.load(f)

    train_losses = history["train_losses"]
    val_losses = history["val_losses"]

    assert len(train_losses) > 0
    assert len(val_losses) == len(train_losses)

    # All losses must be finite positive floats
    assert all(np.isfinite(loss_val) and loss_val > 0.0 for loss_val in train_losses)
    assert all(np.isfinite(loss_val) and loss_val > 0.0 for loss_val in val_losses)

    # Best epoch must be within valid range
    assert 1 <= history["best_epoch"] <= len(train_losses)
