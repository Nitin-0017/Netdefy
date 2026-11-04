"""NETDEFY — Supervised Classification Error Analysis and Ambiguity Forensics.

Analyzes misclassification matrices, most confused class pairs, confidence threshold
rejection trade-offs, and ambiguity impacts on supervised prediction.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def analyze_confused_classes(
    y_true: pd.Series | np.ndarray | list[str],
    y_pred: pd.Series | np.ndarray | list[str],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Identify the top most frequently confused class pairs (true_label != predicted_label)."""
    y_true_s = pd.Series([str(x) for x in y_true])
    y_pred_s = pd.Series([str(x) for x in y_pred])

    errors_df = pd.DataFrame({"true_label": y_true_s, "predicted_label": y_pred_s})
    misclassified = errors_df[errors_df["true_label"] != errors_df["predicted_label"]]

    if misclassified.empty:
        return []

    confusion_counts = (
        misclassified.groupby(["true_label", "predicted_label"])
        .size()
        .reset_index(name="count")
        .sort_values(by="count", ascending=False)
        .head(top_k)
    )

    total_errors = len(misclassified)
    results: list[dict[str, Any]] = []
    for _, row in confusion_counts.iterrows():
        results.append(
            {
                "true_label": str(row["true_label"]),
                "predicted_label": str(row["predicted_label"]),
                "error_count": int(row["count"]),
                "fraction_of_total_errors": round(float(row["count"] / total_errors), 4),
            }
        )
    return results


def analyze_confidence_rejection_curve(
    y_true: pd.Series | np.ndarray | list[str],
    y_prob: np.ndarray,
    classes: list[str],
    thresholds: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Analyze the effect of probability rejection thresholds on acceptance rate and accuracy.

    Flows with max class probability < tau are classified as UNKNOWN (rejected).
    """
    if thresholds is None:
        thresholds = [0.10, 0.30, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]

    y_true_arr = np.asarray([str(x) for x in y_true])
    pred_indices = np.argmax(y_prob, axis=1)
    max_probs = np.max(y_prob, axis=1)
    raw_preds = np.array([classes[idx] for idx in pred_indices])

    total_samples = len(y_true_arr)
    curve_data: list[dict[str, Any]] = []

    for tau in thresholds:
        accepted_mask = max_probs >= tau
        accepted_count = int(accepted_mask.sum())
        rejected_count = total_samples - accepted_count

        coverage = float(accepted_count / total_samples) if total_samples > 0 else 0.0

        if accepted_count > 0:
            acc_on_accepted = float(np.mean(raw_preds[accepted_mask] == y_true_arr[accepted_mask]))
        else:
            acc_on_accepted = 0.0

        curve_data.append(
            {
                "threshold": tau,
                "coverage": round(coverage, 4),
                "accepted_count": accepted_count,
                "rejected_count": rejected_count,
                "accuracy_on_accepted": round(acc_on_accepted, 4),
            }
        )

    return curve_data


def analyze_ambiguity_classification_impact(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    is_ambiguous_flags: list[bool],
    label_column: str = "Label",
) -> dict[str, Any]:
    """Examine how ambiguous flows (130 conflicting vectors) are classified by the supervised model."""
    is_ambig_arr = np.asarray(is_ambiguous_flags, dtype=bool)
    y_true = df[label_column].to_numpy()

    ambig_count = int(is_ambig_arr.sum())
    unambig_count = len(df) - ambig_count

    if ambig_count == 0:
        return {
            "ambiguous_count": 0,
            "unambiguous_count": unambig_count,
            "message": "No ambiguous flows present in partition.",
        }

    ambig_true = y_true[is_ambig_arr]
    ambig_pred = y_pred[is_ambig_arr]

    # Breakdown by true label
    true_label_dist: dict[str, int] = {}
    pred_label_dist: dict[str, int] = {}
    for lbl in ambig_true:
        true_label_dist[str(lbl)] = true_label_dist.get(str(lbl), 0) + 1
    for lbl in ambig_pred:
        pred_label_dist[str(lbl)] = pred_label_dist.get(str(lbl), 0) + 1

    # Exact matching rate on ambiguous subset
    matches = int(np.sum(ambig_true == ambig_pred))
    match_rate = float(matches / ambig_count) if ambig_count > 0 else 0.0

    return {
        "ambiguous_count": ambig_count,
        "unambiguous_count": unambig_count,
        "true_label_distribution": true_label_dist,
        "predicted_label_distribution": pred_label_dist,
        "correct_predictions_in_ambiguous": matches,
        "accuracy_in_ambiguous": round(match_rate, 4),
    }
