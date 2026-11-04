"""NETDEFY — Evaluation Metrics Suite.

Implements comprehensive classification, threshold-independent ranking,
and attack-wise performance metrics for network anomaly detection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass(frozen=True)
class BinaryEvaluationMetrics:
    """Evaluation metrics for a binary anomaly decision threshold."""

    threshold_key: str
    threshold_value: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    benign_fpr: float
    false_alarms_per_1000_benign: float
    total_samples: int
    total_attacks: int
    total_benign: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnomalyEvaluationReport:
    """Comprehensive anomaly evaluation report across multiple thresholds."""

    dataset_name: str
    total_samples: int
    benign_count: int
    attack_count: int
    roc_auc: float
    pr_auc: float
    metrics_by_threshold: dict[str, BinaryEvaluationMetrics]
    attack_wise_recall_by_threshold: dict[str, dict[str, float]]
    attack_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_samples": self.total_samples,
            "benign_count": self.benign_count,
            "attack_count": self.attack_count,
            "roc_auc": round(self.roc_auc, 6),
            "pr_auc": round(self.pr_auc, 6),
            "metrics_by_threshold": {k: v.to_dict() for k, v in self.metrics_by_threshold.items()},
            "attack_wise_recall_by_threshold": self.attack_wise_recall_by_threshold,
            "attack_counts": self.attack_counts,
        }


def compute_binary_metrics(
    y_true_binary: np.ndarray,
    y_pred_binary: np.ndarray,
    threshold_key: str,
    threshold_value: float,
) -> BinaryEvaluationMetrics:
    """Compute binary classification metrics for given predictions.

    Args:
        y_true_binary: 1D array of int (1 = Attack / Anomaly, 0 = Benign).
        y_pred_binary: 1D array of int (1 = Flagged, 0 = Normal).
        threshold_key: Identifier string (e.g. 'p99.0').
        threshold_value: Numeric threshold value.
    """
    tn, fp, fn, tp = confusion_matrix(y_true_binary, y_pred_binary, labels=[0, 1]).ravel()

    total_benign = int(tn + fp)
    total_attacks = int(tp + fn)
    total_samples = int(total_benign + total_attacks)

    prec = float(precision_score(y_true_binary, y_pred_binary, zero_division=0.0))
    rec = float(recall_score(y_true_binary, y_pred_binary, zero_division=0.0))
    f1 = float(f1_score(y_true_binary, y_pred_binary, zero_division=0.0))

    benign_fpr = float(fp / total_benign) if total_benign > 0 else 0.0
    fp_per_1000 = benign_fpr * 1000.0

    return BinaryEvaluationMetrics(
        threshold_key=threshold_key,
        threshold_value=threshold_value,
        true_positives=int(tp),
        false_positives=int(fp),
        true_negatives=int(tn),
        false_negatives=int(fn),
        precision=round(prec, 6),
        recall=round(rec, 6),
        f1=round(f1, 6),
        benign_fpr=round(benign_fpr, 6),
        false_alarms_per_1000_benign=round(fp_per_1000, 4),
        total_samples=total_samples,
        total_attacks=total_attacks,
        total_benign=total_benign,
    )


def compute_attack_wise_recall(
    y_true_labels: pd.Series | np.ndarray,
    y_pred_binary: np.ndarray,
    benign_label: str = "BENIGN",
) -> dict[str, float]:
    """Calculate recall for each distinct attack class."""
    labels = np.asarray(y_true_labels)
    preds = np.asarray(y_pred_binary)

    attack_classes = sorted(set(labels) - {benign_label})
    recalls: dict[str, float] = {}

    for cls_name in attack_classes:
        mask = labels == cls_name
        total_cls = int(np.sum(mask))
        if total_cls == 0:
            recalls[cls_name] = 0.0
        else:
            detected = int(np.sum(preds[mask] == 1))
            recalls[cls_name] = round(float(detected / total_cls), 6)

    return recalls


def evaluate_anomaly_detector(
    y_true_labels: pd.Series | np.ndarray,
    anomaly_scores: np.ndarray,
    thresholds: dict[str, float],
    dataset_name: str = "evaluation",
    benign_label: str = "BENIGN",
) -> AnomalyEvaluationReport:
    """Execute complete anomaly evaluation across all calibrated thresholds.

    Args:
        y_true_labels: Multi-class labels (strings).
        anomaly_scores: Continuous anomaly scores (float32).
        thresholds: Dictionary of threshold name -> threshold value.
        dataset_name: Name of evaluation partition.
        benign_label: Label designating normal flows.
    """
    labels = np.asarray(y_true_labels)
    scores = np.asarray(anomaly_scores, dtype=np.float32)

    # Binary ground truth: 1 for any attack, 0 for BENIGN
    y_true_binary = (labels != benign_label).astype(np.int32)
    benign_count = int(np.sum(y_true_binary == 0))
    attack_count = int(np.sum(y_true_binary == 1))

    # Threshold-independent ranking metrics
    if attack_count > 0 and benign_count > 0:
        roc_auc = float(roc_auc_score(y_true_binary, scores))
        pr_auc = float(average_precision_score(y_true_binary, scores))
    else:
        roc_auc = 0.0
        pr_auc = 0.0

    metrics_by_threshold: dict[str, BinaryEvaluationMetrics] = {}
    attack_wise_by_threshold: dict[str, dict[str, float]] = {}

    for th_key, th_val in thresholds.items():
        y_pred = (scores >= th_val).astype(np.int32)
        metrics_by_threshold[th_key] = compute_binary_metrics(
            y_true_binary=y_true_binary,
            y_pred_binary=y_pred,
            threshold_key=th_key,
            threshold_value=th_val,
        )
        attack_wise_by_threshold[th_key] = compute_attack_wise_recall(
            y_true_labels=labels,
            y_pred_binary=y_pred,
            benign_label=benign_label,
        )

    # Attack counts
    attack_classes = sorted(set(labels) - {benign_label})
    attack_counts = {cls_name: int(np.sum(labels == cls_name)) for cls_name in attack_classes}

    return AnomalyEvaluationReport(
        dataset_name=dataset_name,
        total_samples=len(labels),
        benign_count=benign_count,
        attack_count=attack_count,
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        metrics_by_threshold=metrics_by_threshold,
        attack_wise_recall_by_threshold=attack_wise_by_threshold,
        attack_counts=attack_counts,
    )
