"""Unit tests for BenignThresholdCalibrator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from netdefy.evaluation.thresholds import BenignThresholdCalibrator, ThresholdCalibrationResult


def test_threshold_calibrator_invalid_percentiles() -> None:
    with pytest.raises(ValueError, match="must be in"):
        BenignThresholdCalibrator(target_percentiles=[95.0, 105.0])

    with pytest.raises(ValueError, match="must be in"):
        BenignThresholdCalibrator(target_percentiles=[-1.0, 99.0])


def test_threshold_calibrator_pure_benign() -> None:
    calibrator = BenignThresholdCalibrator(target_percentiles=[95.0, 99.0, 99.5])
    rng = np.random.default_rng(42)
    scores = rng.normal(loc=0.4, scale=0.05, size=10000).astype(np.float32)

    res = calibrator.calibrate(scores)
    assert res.benign_sample_count == 10000
    assert "p95.0" in res.thresholds
    assert "p99.0" in res.thresholds
    assert "p99.5" in res.thresholds

    assert res.thresholds["p95.0"] < res.thresholds["p99.0"] < res.thresholds["p99.5"]
    assert res.score_statistics["mean"] == pytest.approx(0.4, abs=0.02)


def test_threshold_calibrator_from_validation() -> None:
    calibrator = BenignThresholdCalibrator(target_percentiles=[95.0, 99.0])
    df = pd.DataFrame(
        {
            "Label": ["BENIGN"] * 800 + ["DoS Hulk"] * 200,
            "feature1": range(1000),
        }
    )
    scores = np.linspace(0.1, 1.0, 1000, dtype=np.float32)

    res = calibrator.calibrate_from_validation(
        val_df=df,
        anomaly_scores=scores,
        label_column="Label",
        benign_label="BENIGN",
    )
    assert res.benign_sample_count == 800


def test_threshold_calibrator_empty_or_nan_raises() -> None:
    calibrator = BenignThresholdCalibrator()
    with pytest.raises(ValueError, match="empty"):
        calibrator.calibrate(np.array([], dtype=np.float32))

    with pytest.raises(ValueError, match="NaN or Inf"):
        calibrator.calibrate(np.array([0.5, np.nan], dtype=np.float32))


def test_threshold_calibration_save_and_load(tmp_path: Path) -> None:
    calibrator = BenignThresholdCalibrator(target_percentiles=[95.0, 99.0])
    scores = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], dtype=np.float32)
    res = calibrator.calibrate(scores)

    json_file = tmp_path / "thresholds.json"
    res.save(json_file)
    assert json_file.exists()

    loaded = ThresholdCalibrationResult.load(json_file)
    assert loaded.benign_sample_count == res.benign_sample_count
    assert loaded.thresholds == res.thresholds
