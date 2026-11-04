"""Unit tests for Netdefy IsolationForestDetector."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from netdefy.models.isolation_forest import IsolationForestConfig, IsolationForestDetector


def test_isolation_forest_config_defaults() -> None:
    config = IsolationForestConfig()
    assert config.n_estimators == 100
    assert config.max_samples == "auto"
    assert config.contamination == "auto"
    assert config.max_features == 1.0
    assert config.bootstrap is False
    assert config.n_jobs == -1
    assert config.random_state == 42


def test_isolation_forest_fit_and_score_direction() -> None:
    """Verify that anomalous outliers receive HIGHER anomaly scores than inliers."""
    rng = np.random.default_rng(42)
    # Generate tight cluster of normal inliers
    normal_data = rng.normal(loc=0.0, scale=0.5, size=(500, 4)).astype(np.float32)

    detector = IsolationForestDetector(
        config=IsolationForestConfig(n_estimators=50, random_state=42)
    )
    detector.fit(normal_data, feature_names=["f1", "f2", "f3", "f4"])
    assert detector.is_fitted
    assert detector.train_sample_count == 500

    # Inliers should have low anomaly scores
    inlier_scores = detector.score_samples(normal_data[:50])

    # Extreme outliers should have high anomaly scores
    outlier_data = np.full((10, 4), 100.0, dtype=np.float32)
    outlier_scores = detector.score_samples(outlier_data)

    # In NETDEFY: Higher score = more anomalous!
    assert np.mean(outlier_scores) > np.mean(inlier_scores)
    assert np.min(outlier_scores) > np.percentile(inlier_scores, 95.0)


def test_isolation_forest_predict_threshold() -> None:
    rng = np.random.default_rng(42)
    normal_data = rng.normal(loc=0.0, scale=1.0, size=(200, 2)).astype(np.float32)

    detector = IsolationForestDetector()
    detector.fit(normal_data)

    scores = detector.score_samples(normal_data)
    threshold = float(np.percentile(scores, 90.0))

    preds = detector.predict(normal_data, threshold=threshold)
    assert preds.shape == (200,)
    assert set(preds).issubset({0, 1})
    # Approximately 10% should be flagged
    assert 15 <= np.sum(preds == 1) <= 25


def test_isolation_forest_nan_inf_rejection() -> None:
    detector = IsolationForestDetector()
    bad_data_nan = np.array([[1.0, np.nan], [2.0, 3.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="NaN or Inf"):
        detector.fit(bad_data_nan)

    good_data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    detector.fit(good_data)

    bad_data_inf = np.array([[1.0, np.inf]], dtype=np.float32)
    with pytest.raises(ValueError, match="NaN or Inf"):
        detector.score_samples(bad_data_inf)


def test_isolation_forest_unfitted_raises() -> None:
    detector = IsolationForestDetector()
    with pytest.raises(RuntimeError, match="not fitted"):
        detector.score_samples(np.array([[1.0, 2.0]], dtype=np.float32))


def test_isolation_forest_save_and_load(tmp_path: Path) -> None:
    rng = np.random.default_rng(42)
    data = rng.normal(loc=0.0, scale=1.0, size=(100, 3)).astype(np.float32)

    detector = IsolationForestDetector(
        config=IsolationForestConfig(n_estimators=30, random_state=42)
    )
    detector.fit(data, feature_names=["col_a", "col_b", "col_c"])

    orig_scores = detector.score_samples(data)

    save_file = tmp_path / "model.joblib"
    sha = detector.save(save_file)
    assert save_file.exists()
    assert len(sha) == 64

    loaded_detector = IsolationForestDetector.load(save_file)
    assert loaded_detector.is_fitted
    assert loaded_detector.feature_names == ["col_a", "col_b", "col_c"]

    loaded_scores = loaded_detector.score_samples(data)
    np.testing.assert_allclose(orig_scores, loaded_scores, rtol=1e-5)
