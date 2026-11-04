#!/usr/bin/env python3
"""NETDEFY — Phase 4C: Generate Classification and Multi-Engine Visualizations."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

CLF_DIR = PROJECT_ROOT / "artifacts" / "models" / "xgboost_classifier" / "v1"
IF_DIR = PROJECT_ROOT / "artifacts" / "models" / "isolation_forest" / "v1"
AE_DIR = PROJECT_ROOT / "artifacts" / "models" / "autoencoder" / "v1"


def plot_feature_importance() -> Path:
    """Plot top 15 features by XGBoost gain importance."""
    with open(CLF_DIR / "feature_importance.json", encoding="utf-8") as f:
        feat_imp = json.load(f)

    top_features = list(feat_imp.items())[:15]
    top_features.reverse()  # ascending for horizontal bar chart

    names = [k for k, v in top_features]
    scores = [v for k, v in top_features]

    plt.figure(figsize=(10, 6), dpi=300)
    bars = plt.barh(names, scores, color="#2b5c8f", edgecolor="#1a365d", alpha=0.85)

    for bar in bars:
        width = bar.get_width()
        plt.text(
            width + (max(scores) * 0.01),
            bar.get_y() + bar.get_height() / 2,
            f"{width:.1f}",
            va="center",
            ha="left",
            fontsize=8,
            color="#333333",
        )

    plt.title(
        "Top 15 Feature Importances by Gain (XGBoost Attack Classifier)",
        fontsize=13,
        fontweight="bold",
    )
    plt.xlabel("Total Gain", fontsize=11)
    plt.ylabel("Feature Name", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.5, axis="x")
    plt.tight_layout()

    out_path = FIGURES_DIR / "phase4c_feature_importance.png"
    plt.savefig(out_path)
    plt.close()
    return out_path


def plot_validation_confusion_matrix() -> Path:
    """Plot validation confusion matrix across 8 known classes."""
    with open(CLF_DIR / "validation_metrics.json", encoding="utf-8") as f:
        val_data = json.load(f)

    cm_info = val_data["validation_report"]["confusion_matrix_data"]
    labels = cm_info["labels"]
    matrix = np.array(cm_info["matrix"], dtype=float)

    # Normalize rows
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    norm_matrix = matrix / row_sums

    fig, ax = plt.subplots(figsize=(9, 8), dpi=300)
    cax = ax.matshow(norm_matrix, cmap="Blues", alpha=0.85)
    fig.colorbar(cax, fraction=0.046, pad=0.04)

    for i in range(len(labels)):
        for j in range(len(labels)):
            val = norm_matrix[i, j]
            count = int(matrix[i, j])
            text_color = "white" if val > 0.5 else "black"
            ax.text(
                j,
                i,
                f"{val:.2f}\n({count})",
                ha="center",
                va="center",
                color=text_color,
                fontsize=7.5,
            )

    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="left", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)

    plt.title(
        "Validation Set Confusion Matrix — Normalized (Raw Counts)\nKnown Attack Attribution (XGBoost)",
        fontsize=12,
        fontweight="bold",
        pad=20,
    )
    plt.xlabel("Predicted Class", fontsize=10, labelpad=10)
    plt.ylabel("Ground Truth Class", fontsize=10)
    plt.tight_layout()

    out_path = FIGURES_DIR / "phase4c_validation_confusion_matrix.png"
    plt.savefig(out_path)
    plt.close()
    return out_path


def plot_confidence_threshold_curve() -> Path:
    """Plot Accuracy and Rejection Rate vs Rejection Threshold tau."""
    with open(CLF_DIR / "validation_metrics.json", encoding="utf-8") as f:
        val_metrics = json.load(f)

    curve = val_metrics["confidence_curve"]
    thresholds = [pt["threshold"] for pt in curve]
    accuracies = [pt["accuracy_on_accepted"] * 100 for pt in curve]
    rejection_rates = [
        (pt["rejected_count"] / (pt["accepted_count"] + pt["rejected_count"])) * 100 for pt in curve
    ]

    plt.figure(figsize=(9, 5), dpi=300)
    plt.plot(
        thresholds,
        accuracies,
        label="Accuracy on Accepted Flows (%)",
        color="#1f77b4",
        linewidth=2.2,
        marker="o",
        markersize=5,
    )
    plt.plot(
        thresholds,
        rejection_rates,
        label="Rejected / Unknown Rate (%)",
        color="#d62728",
        linewidth=2.2,
        marker="s",
        markersize=5,
    )

    plt.axvline(
        0.50,
        color="#2ca02c",
        linestyle="--",
        label="Operating Threshold (τ = 0.50)",
        alpha=0.8,
    )

    plt.title(
        "Confidence-Based Risk Rejection: Accuracy & Rejection Rate vs. Threshold (τ)",
        fontsize=12,
        fontweight="bold",
    )
    plt.xlabel("Confidence Rejection Threshold (τ)", fontsize=11)
    plt.ylabel("Percentage (%)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(fontsize=10)
    plt.tight_layout()

    out_path = FIGURES_DIR / "phase4c_confidence_threshold_curve.png"
    plt.savefig(out_path)
    plt.close()
    return out_path


def plot_three_engine_comparison() -> Path:
    """Compare Phase 4A, 4B, and 4C across detection and attribution capabilities."""
    categories = [
        "BENIGN Specificity (%)",
        "Known Val Macro F1 (%)",
        "Holdout DDoS Detection (%)",
        "Holdout PortScan Detection (%)",
    ]

    # IF (4A) at p99: Benign specificity = 98.62%, Val ROC = 82.97, DDoS = 2.99%, PortScan = 0.04%
    # AE (4B) at p99: Benign specificity = 97.60%, Val ROC = 87.36, DDoS = 60.58%, PortScan = 0.06%
    # XGB (4C): Benign recall = 99.74%, Val Macro F1 = 97.59%, DDoS detected as Hulk = 64.03%, PortScan = 0.20%
    if_scores = [98.62, 82.97, 2.99, 0.04]
    ae_scores = [97.60, 87.36, 60.58, 0.06]
    xgb_scores = [99.74, 97.59, 64.03, 0.20]

    x = np.arange(len(categories))
    width = 0.25

    plt.figure(figsize=(10, 5.5), dpi=300)
    plt.bar(x - width, if_scores, width, label="Isolation Forest (Phase 4A)", color="#7293cb")
    plt.bar(x, ae_scores, width, label="Deep Autoencoder (Phase 4B)", color="#e1974c")
    plt.bar(x + width, xgb_scores, width, label="XGBoost Classifier (Phase 4C)", color="#84ba5b")

    for i in range(len(categories)):
        plt.text(i - width, if_scores[i] + 1.5, f"{if_scores[i]:.1f}%", ha="center", fontsize=7.5)
        plt.text(i, ae_scores[i] + 1.5, f"{ae_scores[i]:.1f}%", ha="center", fontsize=7.5)
        plt.text(i + width, xgb_scores[i] + 1.5, f"{xgb_scores[i]:.1f}%", ha="center", fontsize=7.5)

    plt.title(
        "Cross-Engine Benchmark: Isolation Forest vs. Deep Autoencoder vs. XGBoost Classifier",
        fontsize=12,
        fontweight="bold",
    )
    plt.ylabel("Score (%)", fontsize=11)
    plt.xticks(x, categories, fontsize=9.5)
    plt.ylim(0, 115)
    plt.grid(True, linestyle=":", alpha=0.5, axis="y")
    plt.legend(fontsize=10, loc="upper right")
    plt.tight_layout()

    out_path = FIGURES_DIR / "phase4_three_engine_comparison.png"
    plt.savefig(out_path)
    plt.close()
    return out_path


def main() -> int:
    print("Generating Phase 4C plots...")
    p1 = plot_feature_importance()
    print("Saved:", p1)
    p2 = plot_validation_confusion_matrix()
    print("Saved:", p2)
    p3 = plot_confidence_threshold_curve()
    print("Saved:", p3)
    p4 = plot_three_engine_comparison()
    print("Saved:", p4)
    print("All Phase 4C visualizations generated successfully!")
    return 0


if __name__ == "__main__":
    main()
