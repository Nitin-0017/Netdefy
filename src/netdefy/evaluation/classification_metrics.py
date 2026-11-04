"""NETDEFY — Multiclass Classification Metrics and Evaluation Engine.

Computes comprehensive multiclass performance metrics including macro/weighted averages,
per-class precision/recall/F1, confusion matrices, multiclass log loss, and OvR AUCs.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


@dataclass
class MulticlassClassificationReport:
    """Comprehensive multiclass evaluation report container."""

    dataset_name: str
    total_samples: int
    accuracy: float
    balanced_accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    weighted_f1: float
    log_loss_value: float | None
    multiclass_ovr_roc_auc: float | None
    classes: list[str]
    per_class_metrics: dict[str, dict[str, float | int]]
    confusion_matrix_data: dict[str, Any]
    unknown_count: int
    unknown_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_multiclass_classifier(
    y_true: pd.Series | np.ndarray | list[str],
    y_pred: pd.Series | np.ndarray | list[str],
    y_prob: np.ndarray | None = None,
    classes: list[str] | None = None,
    dataset_name: str = "dataset",
    unknown_label: str = "UNKNOWN",
) -> MulticlassClassificationReport:
    """Compute rigorous multiclass evaluation metrics with unknown class handling."""
    y_true_arr = np.asarray([str(x) for x in y_true])
    y_pred_arr = np.asarray([str(x) for x in y_pred])

    total_samples = len(y_true_arr)
    unknown_mask = y_pred_arr == unknown_label
    unknown_count = int(unknown_mask.sum())
    unknown_rate = float(unknown_count / total_samples) if total_samples > 0 else 0.0

    # Determine unique classes for metric alignment
    target_classes = list(classes) if classes is not None else sorted(set(y_true_arr))

    # Compute overall accuracy
    acc = float(accuracy_score(y_true_arr, y_pred_arr))

    # For balanced accuracy and per-class stats across known classes
    # If predictions contain UNKNOWN, evaluate against all unique classes present
    all_eval_labels = sorted(set(y_true_arr) | set(y_pred_arr))
    bal_acc = float(balanced_accuracy_score(y_true_arr, y_pred_arr))

    prec, rec, f1, supp = precision_recall_fscore_support(
        y_true_arr,
        y_pred_arr,
        labels=all_eval_labels,
        zero_division=0.0,  # Explicitly handle division by zero
    )

    per_class_metrics: dict[str, dict[str, float | int]] = {}
    for idx, label_name in enumerate(all_eval_labels):
        per_class_metrics[label_name] = {
            "precision": float(round(prec[idx], 4)),
            "recall": float(round(rec[idx], 4)),
            "f1": float(round(f1[idx], 4)),
            "support": int(supp[idx]),
        }

    # Macro & Weighted metrics (calculated over true classes present in test ground truth)
    macro_prec, macro_rec, macro_f1, _ = precision_recall_fscore_support(
        y_true_arr,
        y_pred_arr,
        average="macro",
        zero_division=0.0,
    )
    _, _, weighted_f1, _ = precision_recall_fscore_support(
        y_true_arr,
        y_pred_arr,
        average="weighted",
        zero_division=0.0,
    )

    # Confusion matrix
    cm_labels = all_eval_labels
    cm = confusion_matrix(y_true_arr, y_pred_arr, labels=cm_labels)
    confusion_dict = {
        "labels": cm_labels,
        "matrix": cm.tolist(),
    }

    # Optional Log Loss and OvR ROC-AUC if probabilities are available
    loss_val: float | None = None
    ovr_auc: float | None = None

    if y_prob is not None and classes is not None and set(y_true_arr).issubset(set(classes)):
        try:
            # Map true labels to indices matching probability columns
            class_to_idx = {c: i for i, c in enumerate(classes)}
            y_true_idx = np.array([class_to_idx[lbl] for lbl in y_true_arr])

            loss_val = float(
                round(log_loss(y_true_idx, y_prob, labels=list(range(len(classes)))), 4)
            )

            # Multiclass ROC-AUC (OvR)
            # Requires at least 2 distinct classes present in true labels
            if len(np.unique(y_true_idx)) > 1:
                ovr_auc = float(
                    round(
                        roc_auc_score(
                            y_true_idx,
                            y_prob,
                            multi_class="ovr",
                            average="macro",
                            labels=list(range(len(classes))),
                        ),
                        4,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not compute multiclass log loss / ROC-AUC: %s", exc)

    return MulticlassClassificationReport(
        dataset_name=dataset_name,
        total_samples=total_samples,
        accuracy=float(round(acc, 4)),
        balanced_accuracy=float(round(bal_acc, 4)),
        macro_precision=float(round(macro_prec, 4)),
        macro_recall=float(round(macro_rec, 4)),
        macro_f1=float(round(macro_f1, 4)),
        weighted_f1=float(round(weighted_f1, 4)),
        log_loss_value=loss_val,
        multiclass_ovr_roc_auc=ovr_auc,
        classes=target_classes,
        per_class_metrics=per_class_metrics,
        confusion_matrix_data=confusion_dict,
        unknown_count=unknown_count,
        unknown_rate=float(round(unknown_rate, 4)),
    )
