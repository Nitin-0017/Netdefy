"""NETDEFY — Error Analysis & Diagnostic Engine.

Performs deep forensic inspection of false positives, false negatives,
attack-specific evasion patterns, and ambiguous feature vector distributions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def analyze_false_positives(
    df: pd.DataFrame,
    anomaly_scores: np.ndarray,
    threshold: float,
    feature_columns: list[str],
    label_column: str = "Label",
    benign_label: str = "BENIGN",
    top_k: int = 10,
) -> dict[str, Any]:
    """Inspect top false positive benign flows with highest anomaly scores."""
    scores = np.asarray(anomaly_scores, dtype=np.float32)
    benign_mask = (df[label_column] == benign_label).to_numpy()
    fp_mask = benign_mask & (scores >= threshold)

    n_benign = int(np.sum(benign_mask))
    n_fp = int(np.sum(fp_mask))

    fp_indices = np.where(fp_mask)[0]
    if len(fp_indices) == 0:
        return {
            "total_benign": n_benign,
            "false_positive_count": 0,
            "false_positive_rate": 0.0,
            "top_false_positives": [],
            "divergent_features": {},
        }

    # Rank FPs by anomaly score descending
    sorted_order = np.argsort(-scores[fp_indices])
    top_fp_idx = fp_indices[sorted_order[:top_k]]

    top_fp_records: list[dict[str, Any]] = []
    for idx in top_fp_idx:
        top_fp_records.append(
            {
                "index": int(idx),
                "anomaly_score": float(scores[idx]),
                "features": {col: float(df.iloc[idx][col]) for col in feature_columns[:5]},
            }
        )

    # Feature comparison: FP mean vs TN mean
    tn_mask = benign_mask & (~fp_mask)
    divergent: dict[str, dict[str, float]] = {}
    if np.sum(tn_mask) > 0 and n_fp > 0:
        fp_means = df.loc[fp_mask, feature_columns].mean()
        tn_means = df.loc[tn_mask, feature_columns].mean()
        tn_stds = df.loc[tn_mask, feature_columns].std().replace(0, 1e-6)

        # Compute z-score difference for each feature
        z_diffs = ((fp_means - tn_means) / tn_stds).abs()
        top_diff_cols = z_diffs.nlargest(8).index.tolist()

        for col in top_diff_cols:
            divergent[col] = {
                "fp_mean": float(fp_means[col]),
                "tn_mean": float(tn_means[col]),
                "z_difference": float(z_diffs[col]),
            }

    return {
        "total_benign": n_benign,
        "false_positive_count": n_fp,
        "false_positive_rate": round(float(n_fp / n_benign), 6) if n_benign > 0 else 0.0,
        "top_false_positives": top_fp_records,
        "divergent_features": divergent,
    }


def analyze_false_negatives(
    df: pd.DataFrame,
    anomaly_scores: np.ndarray,
    threshold: float,
    label_column: str = "Label",
    benign_label: str = "BENIGN",
) -> dict[str, Any]:
    """Inspect false negative attacks that evaded the anomaly threshold."""
    scores = np.asarray(anomaly_scores, dtype=np.float32)
    attack_mask = (df[label_column] != benign_label).to_numpy()
    fn_mask = attack_mask & (scores < threshold)

    n_attacks = int(np.sum(attack_mask))
    n_fn = int(np.sum(fn_mask))

    fn_by_class: dict[str, dict[str, Any]] = {}
    if n_attacks > 0:
        attack_labels = df.loc[attack_mask, label_column]
        for cls_name in sorted(attack_labels.unique()):
            cls_mask = df[label_column] == cls_name
            total_cls = int(np.sum(cls_mask))
            fn_cls = int(np.sum(cls_mask & fn_mask))
            miss_rate = float(fn_cls / total_cls) if total_cls > 0 else 0.0
            avg_score = float(np.mean(scores[cls_mask])) if total_cls > 0 else 0.0

            fn_by_class[cls_name] = {
                "total_instances": total_cls,
                "missed_count": fn_cls,
                "miss_rate": round(miss_rate, 4),
                "recall": round(1.0 - miss_rate, 4),
                "mean_anomaly_score": round(avg_score, 6),
            }

    return {
        "total_attacks": n_attacks,
        "total_false_negatives": n_fn,
        "overall_miss_rate": round(float(n_fn / n_attacks), 6) if n_attacks > 0 else 0.0,
        "evasion_by_attack_class": fn_by_class,
    }


def analyze_ambiguity_impact(
    df: pd.DataFrame,
    anomaly_scores: np.ndarray,
    threshold: float,
    is_ambiguous_flags: list[bool] | np.ndarray,
    label_column: str = "Label",
    benign_label: str = "BENIGN",
) -> dict[str, Any]:
    """Compare detection performance on ambiguous subset vs unambiguous subset."""
    scores = np.asarray(anomaly_scores, dtype=np.float32)
    ambig_mask = np.asarray(is_ambiguous_flags, dtype=bool)
    unambig_mask = ~ambig_mask

    results: dict[str, Any] = {}
    for subset_name, mask in [("ambiguous", ambig_mask), ("disambiguated", unambig_mask)]:
        sub_df = df.iloc[mask]
        sub_scores = scores[mask]
        sub_labels = sub_df[label_column].to_numpy()

        sub_attacks = sub_labels != benign_label
        sub_benign = ~sub_attacks

        n_attacks = int(np.sum(sub_attacks))
        n_benign = int(np.sum(sub_benign))

        preds = (sub_scores >= threshold).astype(int)

        tp = int(np.sum((preds == 1) & sub_attacks))
        fp = int(np.sum((preds == 1) & sub_benign))
        tn = int(np.sum((preds == 0) & sub_benign))
        fn = int(np.sum((preds == 0) & sub_attacks))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / n_attacks) if n_attacks > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        fpr = float(fp / n_benign) if n_benign > 0 else 0.0

        results[subset_name] = {
            "sample_count": len(sub_df),
            "attack_count": n_attacks,
            "benign_count": n_benign,
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": round(prec, 6),
            "recall": round(rec, 6),
            "f1": round(f1, 6),
            "benign_fpr": round(fpr, 6),
            "false_alarms_per_1000": round(fpr * 1000.0, 4),
        }

    return results
