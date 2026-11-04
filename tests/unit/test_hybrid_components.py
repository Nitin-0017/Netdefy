"""NETDEFY — Unit Tests for Hybrid Components.

Tests score calibration, score fusion, classifier rejection, decision policy,
explanation generation, and schema serialization using synthetic fixtures.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from netdefy.hybrid.classifier_rejection import (
    ClassifierRejectionConfig,
    ClassifierRejectionEngine,
)
from netdefy.hybrid.decision_engine import DecisionEngine, DecisionPolicyConfig
from netdefy.hybrid.explanation import ExplanationGenerator
from netdefy.hybrid.schemas import (
    AnomalyEvidence,
    ClassifierEvidence,
    DecisionCategory,
)
from netdefy.hybrid.score_calibration import (
    PercentileCalibrator,
    RobustScalerCalibrator,
)
from netdefy.hybrid.score_fusion import ScoreFusionConfig, ScoreFusionEngine


def test_percentile_calibrator_fitting_and_monotonicity(tmp_path: Path) -> None:
    """Test percentile calibration monotonicity, boundary behavior, and serialization."""
    reference_scores = np.linspace(0.1, 0.9, 500)
    calibrator = PercentileCalibrator(num_quantiles=101).fit(reference_scores)

    # Test monotonic order
    test_scores = np.array([0.05, 0.1, 0.5, 0.9, 0.95], dtype=np.float32)
    calibrated = calibrator.transform(test_scores)

    assert calibrated[0] == 0.0  # below minimum
    assert calibrated[-1] == 1.0  # above maximum
    assert np.all(np.diff(calibrated) >= 0)  # monotonically non-decreasing
    assert calibrated.dtype == np.float32

    # Test serialization round-trip
    save_path = tmp_path / "percentile_cal.json"
    checksum = calibrator.save(save_path)
    assert len(checksum) == 64

    loaded = PercentileCalibrator.load(save_path)
    assert loaded.is_fitted
    np.testing.assert_allclose(loaded.transform(test_scores), calibrated)


def test_robust_scaler_calibrator(tmp_path: Path) -> None:
    """Test robust sigmoid calibration resilience, bounds in (0, 1), and serialization."""
    reference_scores = np.random.default_rng(42).normal(loc=10.0, scale=2.0, size=1000)
    calibrator = RobustScalerCalibrator().fit(reference_scores)

    test_scores = np.array([2.0, 10.0, 18.0], dtype=np.float32)
    calibrated = calibrator.transform(test_scores)

    # Median score should map close to 0.5
    assert abs(calibrated[1] - 0.5) < 0.05
    assert 0.0 < calibrated[0] < calibrated[1] < calibrated[2] < 1.0

    save_path = tmp_path / "robust_cal.json"
    calibrator.save(save_path)
    loaded = RobustScalerCalibrator.load(save_path)
    np.testing.assert_allclose(loaded.transform(test_scores), calibrated)


def test_score_fusion_strategies() -> None:
    """Test various score fusion strategies and mathematical properties."""
    c_if = np.array([0.2, 0.8, 0.5], dtype=np.float32)
    c_ae = np.array([0.4, 0.6, 0.9], dtype=np.float32)

    # Strategy: max
    max_engine = ScoreFusionEngine(ScoreFusionConfig(strategy="max"))
    fused_max = max_engine.fuse(c_if, c_ae)
    np.testing.assert_allclose(fused_max, [0.4, 0.8, 0.9])

    # Strategy: mean
    mean_engine = ScoreFusionEngine(ScoreFusionConfig(strategy="mean"))
    fused_mean = mean_engine.fuse(c_if, c_ae)
    np.testing.assert_allclose(fused_mean, [0.3, 0.7, 0.7])

    # Strategy: weighted
    weighted_engine = ScoreFusionEngine(
        ScoreFusionConfig(strategy="weighted", weight_if=0.3, weight_ae=0.7)
    )
    fused_weighted = weighted_engine.fuse(c_if, c_ae)
    expected = 0.3 * c_if + 0.7 * c_ae
    np.testing.assert_allclose(fused_weighted, expected)

    # Strategy: isolation_forest_only
    if_engine = ScoreFusionEngine(ScoreFusionConfig(strategy="isolation_forest_only"))
    np.testing.assert_allclose(if_engine.fuse(c_if, c_ae), c_if)

    # Strategy: autoencoder_only
    ae_engine = ScoreFusionEngine(ScoreFusionConfig(strategy="autoencoder_only"))
    np.testing.assert_allclose(ae_engine.fuse(c_if, c_ae), c_ae)


def test_score_fusion_validation_errors() -> None:
    """Test error handling in score fusion on shape mismatch and invalid weights."""
    engine = ScoreFusionEngine(ScoreFusionConfig(strategy="mean"))
    with pytest.raises(ValueError, match="Shape mismatch"):
        engine.fuse(np.array([0.1, 0.2]), np.array([0.1]))

    with pytest.raises(ValueError, match="Weights must sum to 1.0"):
        ScoreFusionEngine(ScoreFusionConfig(strategy="weighted", weight_if=0.5, weight_ae=0.8))


def test_classifier_rejection_logic() -> None:
    """Test confidence, margin, and entropy rejection rules."""
    class_mapping = {0: "BENIGN", 1: "DoS Hulk", 2: "PortScan"}
    rejection_engine = ClassifierRejectionEngine(
        ClassifierRejectionConfig(min_confidence=0.50, min_margin=0.10, max_entropy=1.50)
    )

    # Sample 1: High confidence DoS Hulk (pass)
    # Sample 2: Low confidence (reject)
    # Sample 3: Small margin tie (reject)
    probs = np.array(
        [
            [0.05, 0.90, 0.05],  # high confidence
            [0.35, 0.35, 0.30],  # low confidence & high entropy
            [0.48, 0.47, 0.05],  # low margin (0.01 < 0.10)
        ],
        dtype=np.float32,
    )

    evidence = rejection_engine.evaluate_batch(probs, class_mapping)
    assert len(evidence) == 3

    assert not evidence[0].rejected
    assert evidence[0].predicted_class == "DoS Hulk"

    assert evidence[1].rejected
    assert "Confidence" in (evidence[1].rejection_reason or "")

    assert evidence[2].rejected
    assert "Margin" in (evidence[2].rejection_reason or "")


def test_decision_engine_rules() -> None:
    """Test all four decision engine branches and conflict resolution rules."""
    engine = DecisionEngine(
        DecisionPolicyConfig(
            anomaly_threshold=0.990,
            threshold_tier="p99.0",
            detector_disagreement_threshold=0.50,
            high_classifier_conflict_confidence=0.85,
            benign_label="BENIGN",
        )
    )

    # 1. Normal flow: low anomaly score, benign classifier
    anom_norm = AnomalyEvidence(
        isolation_forest_raw_score=0.35,
        isolation_forest_calibrated_score=0.40,
        autoencoder_raw_error=0.001,
        autoencoder_calibrated_score=0.30,
        fused_score=0.35,
        threshold=0.990,
        is_anomaly=False,
    )
    clf_norm = ClassifierEvidence(
        predicted_class="BENIGN",
        top_probability=0.95,
        second_probability=0.03,
        probability_margin=0.92,
        entropy=0.2,
        rejected=False,
        rejection_reason=None,
    )
    dec, _ = engine.evaluate_flow(anom_norm, clf_norm)
    assert dec == DecisionCategory.NORMAL

    # 2. Review Required: Anomaly detector says normal, but classifier insists known attack with high confidence
    clf_conflict = ClassifierEvidence(
        predicted_class="DoS Hulk",
        top_probability=0.92,
        second_probability=0.05,
        probability_margin=0.87,
        entropy=0.3,
        rejected=False,
        rejection_reason=None,
    )
    dec, reason = engine.evaluate_flow(anom_norm, clf_conflict)
    assert dec == DecisionCategory.REVIEW_REQUIRED
    assert "Model conflict" in reason

    # 3. Suspicious Known: Anomaly score high, classifier predicts known attack with high confidence
    anom_high = AnomalyEvidence(
        isolation_forest_raw_score=0.68,
        isolation_forest_calibrated_score=0.992,
        autoencoder_raw_error=1.5,
        autoencoder_calibrated_score=0.994,
        fused_score=0.993,
        threshold=0.990,
        is_anomaly=True,
    )
    dec, _ = engine.evaluate_flow(anom_high, clf_conflict)
    assert dec == DecisionCategory.SUSPICIOUS_KNOWN

    # 4. Suspicious Unknown (Open-Set): Anomaly score high, but classifier predicts BENIGN (e.g. unseen PortScan)
    dec, reason = engine.evaluate_flow(anom_high, clf_norm)
    assert dec == DecisionCategory.SUSPICIOUS_UNKNOWN
    assert "classifier assigned benign label" in reason

    # 5. Suspicious Unknown (Rejected Attribution): Anomaly score high, classifier rejected
    clf_rejected = ClassifierEvidence(
        predicted_class="DoS Hulk",
        top_probability=0.35,
        second_probability=0.30,
        probability_margin=0.05,
        entropy=2.2,
        rejected=True,
        rejection_reason="Low confidence",
    )
    dec, _ = engine.evaluate_flow(anom_high, clf_rejected)
    assert dec == DecisionCategory.SUSPICIOUS_UNKNOWN


def test_explanation_generation() -> None:
    """Test structured explanation generator and feature-level attribution."""
    gen = ExplanationGenerator(top_k_features=3)

    anom_ev = AnomalyEvidence(
        isolation_forest_raw_score=0.70,
        isolation_forest_calibrated_score=0.995,
        autoencoder_raw_error=2.0,
        autoencoder_calibrated_score=0.996,
        fused_score=0.9955,
        threshold=0.990,
        is_anomaly=True,
    )
    clf_ev = ClassifierEvidence(
        predicted_class="BENIGN",
        top_probability=0.98,
        second_probability=0.01,
        probability_margin=0.97,
        entropy=0.1,
        rejected=False,
        rejection_reason=None,
    )

    feature_names = ["feat_0", "feat_1", "feat_2", "feat_3"]
    x_in = np.array([1.0, 5.0, 0.0, 2.0], dtype=np.float32)
    x_rec = np.array([1.1, 1.0, 0.0, 2.0], dtype=np.float32)  # feat_1 error = (5 - 1)^2 = 16.0

    exp = gen.explain(
        decision=DecisionCategory.SUSPICIOUS_UNKNOWN,
        decision_reason="Anomalous flow verified",
        anomaly_evidence=anom_ev,
        classifier_evidence=clf_ev,
        feature_names=feature_names,
        x_raw_or_scaled=x_in,
        x_reconstructed=x_rec,
    )

    assert exp.decision == DecisionCategory.SUSPICIOUS_UNKNOWN
    assert len(exp.top_contributing_features) == 3
    assert exp.top_contributing_features[0].feature_name == "feat_1"
    assert abs(exp.top_contributing_features[0].reconstruction_error - 16.0) < 1e-4
    assert len(exp.evidence_summary) > 0
