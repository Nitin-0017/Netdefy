"""Unit tests for Netdefy XGBoostAttackClassifier."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from netdefy.models.xgboost_classifier import (
    XGBoostAttackClassifier,
    XGBoostClassifierConfig,
)


def test_classifier_config_defaults() -> None:
    config = XGBoostClassifierConfig()
    assert config.n_estimators == 150
    assert config.max_depth == 6
    assert config.learning_rate == 0.05
    assert config.subsample == 0.8
    assert config.colsample_bytree == 0.8
    assert config.min_child_weight == 1.0
    assert config.gamma == 0.1
    assert config.reg_alpha == 0.01
    assert config.reg_lambda == 1.0
    assert config.objective == "multi:softprob"
    assert config.eval_metric == "mlogloss"
    assert config.tree_method == "hist"
    assert config.random_state == 42
    assert config.confidence_threshold == 0.50


def test_classifier_fit_predict_proba() -> None:
    """Verify multiclass probability prediction and shape alignment."""
    rng = np.random.default_rng(42)
    X = rng.normal(loc=0.0, scale=1.0, size=(120, 6)).astype(np.float32)
    # 3 classes: A, B, C
    y = np.array(["A", "B", "C"] * 40)

    clf = XGBoostAttackClassifier(
        config=XGBoostClassifierConfig(n_estimators=15, max_depth=3, n_jobs=2)
    )
    clf.fit(X, y, feature_names=[f"col_{i}" for i in range(6)])
    assert clf.is_fitted
    assert clf.train_sample_count == 120
    assert len(clf.class_mapping) == 3

    probs = clf.predict_proba(X[:10])
    assert probs.shape == (10, 3)
    assert probs.dtype == np.float32
    # Probabilities must sum to 1 per sample
    np.testing.assert_allclose(probs.sum(axis=1), np.ones(10, dtype=np.float32), atol=1e-5)


def test_classifier_confidence_rejection() -> None:
    """Verify that predictions below confidence threshold are flagged as UNKNOWN."""
    rng = np.random.default_rng(42)
    X = rng.normal(loc=0.0, scale=1.0, size=(90, 4)).astype(np.float32)
    y = np.array(["Alpha", "Beta", "Gamma"] * 30)

    clf = XGBoostAttackClassifier(
        config=XGBoostClassifierConfig(n_estimators=10, max_depth=2, n_jobs=2)
    )
    clf.fit(X, y)

    # With threshold 0.0, no flows rejected
    preds_no_reject = clf.predict(X, reject_threshold=0.0)
    assert "UNKNOWN" not in preds_no_reject

    # With very high threshold (0.999), almost all flows rejected
    preds_strict = clf.predict(X, reject_threshold=0.999, unknown_label="UNKNOWN")
    assert "UNKNOWN" in preds_strict
    assert np.sum(preds_strict == "UNKNOWN") > 0


def test_classifier_nan_inf_rejection() -> None:
    clf = XGBoostAttackClassifier()
    bad_data_nan = np.array([[1.0, np.nan], [2.0, 3.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="NaN or Inf"):
        clf.fit(bad_data_nan, np.array(["A", "B"]))

    good_data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    clf.fit(good_data, np.array(["A", "B"]))

    bad_data_inf = np.array([[1.0, np.inf]], dtype=np.float32)
    with pytest.raises(ValueError, match="NaN or Inf"):
        clf.predict_proba(bad_data_inf)


def test_classifier_unfitted_raises() -> None:
    clf = XGBoostAttackClassifier()
    with pytest.raises(RuntimeError, match="not fitted"):
        clf.predict_proba(np.array([[1.0, 2.0]], dtype=np.float32))


def test_classifier_save_and_load(tmp_path: Path) -> None:
    rng = np.random.default_rng(42)
    X = rng.normal(loc=0.0, scale=1.0, size=(100, 4)).astype(np.float32)
    y = np.array(["CatA", "CatB"] * 50)

    clf = XGBoostAttackClassifier(
        config=XGBoostClassifierConfig(n_estimators=20, max_depth=3, n_jobs=2)
    )
    clf.fit(X, y, feature_names=["f1", "f2", "f3", "f4"])

    orig_probs = clf.predict_proba(X)

    save_json = tmp_path / "model.json"
    sha = clf.save(save_json)
    assert save_json.exists()
    assert (tmp_path / "model.ubj").exists()
    assert len(sha) == 64

    loaded_clf = XGBoostAttackClassifier.load(save_json)
    assert loaded_clf.is_fitted
    assert loaded_clf.feature_names == ["f1", "f2", "f3", "f4"]
    assert loaded_clf.class_mapping == clf.class_mapping

    loaded_probs = loaded_clf.predict_proba(X)
    np.testing.assert_allclose(orig_probs, loaded_probs, atol=1e-5)


def test_classifier_feature_importances() -> None:
    rng = np.random.default_rng(42)
    X = rng.normal(loc=0.0, scale=1.0, size=(150, 4)).astype(np.float32)
    # Informative feature 0
    y = np.where(X[:, 0] > 0.0, "Class_Positive", "Class_Negative")

    clf = XGBoostAttackClassifier(
        config=XGBoostClassifierConfig(n_estimators=15, max_depth=3, n_jobs=2)
    )
    clf.fit(X, y, feature_names=["important_f", "f2", "f3", "f4"])

    importances = clf.get_feature_importances(importance_type="gain")
    assert len(importances) == 4
    # Highest gain should be important_f
    top_feature = list(importances.keys())[0]
    assert top_feature == "important_f"
