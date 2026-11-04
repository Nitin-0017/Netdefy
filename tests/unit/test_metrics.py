"""Unit tests for Netdefy evaluation metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from netdefy.evaluation.metrics import (
    compute_attack_wise_recall,
    compute_binary_metrics,
    evaluate_anomaly_detector,
)


def test_compute_binary_metrics_known_values() -> None:
    # 8 benign (0), 2 attack (1)
    y_true = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1], dtype=int)
    # 1 FP at index 0, 1 TP at index 8, 1 FN at index 9, 7 TN
    y_pred = np.array([1, 0, 0, 0, 0, 0, 0, 0, 1, 0], dtype=int)

    metrics = compute_binary_metrics(
        y_true_binary=y_true,
        y_pred_binary=y_pred,
        threshold_key="test_th",
        threshold_value=0.5,
    )

    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.true_negatives == 7
    assert metrics.false_negatives == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5
    assert metrics.benign_fpr == 1 / 8
    assert metrics.false_alarms_per_1000_benign == 125.0


def test_compute_binary_metrics_zero_predictions() -> None:
    # Edge case: No positive predictions
    y_true = np.array([0, 0, 1, 1], dtype=int)
    y_pred = np.array([0, 0, 0, 0], dtype=int)

    metrics = compute_binary_metrics(
        y_true_binary=y_true,
        y_pred_binary=y_pred,
        threshold_key="high_th",
        threshold_value=0.9,
    )

    assert metrics.true_positives == 0
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.benign_fpr == 0.0


def test_compute_attack_wise_recall() -> None:
    labels = pd.Series(["BENIGN", "BENIGN", "PortScan", "PortScan", "DDoS", "DDoS"])
    preds = np.array([0, 0, 1, 0, 1, 1])

    recalls = compute_attack_wise_recall(
        y_true_labels=labels,
        y_pred_binary=preds,
        benign_label="BENIGN",
    )

    assert recalls["PortScan"] == 0.5
    assert recalls["DDoS"] == 1.0


def test_evaluate_anomaly_detector() -> None:
    labels = np.array(["BENIGN"] * 50 + ["PortScan"] * 50)
    scores = np.concatenate(
        [
            np.linspace(0.1, 0.4, 50, dtype=np.float32),
            np.linspace(0.5, 0.9, 50, dtype=np.float32),
        ]
    )
    thresholds = {"p95.0": 0.38, "p99.0": 0.45}

    report = evaluate_anomaly_detector(
        y_true_labels=labels,
        anomaly_scores=scores,
        thresholds=thresholds,
        dataset_name="mock_test",
        benign_label="BENIGN",
    )

    assert report.total_samples == 100
    assert report.benign_count == 50
    assert report.attack_count == 50
    assert report.roc_auc > 0.99
    assert report.pr_auc > 0.99
    assert "p95.0" in report.metrics_by_threshold
    assert "p99.0" in report.metrics_by_threshold
    assert report.attack_wise_recall_by_threshold["p99.0"]["PortScan"] == 1.0
