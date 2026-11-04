#!/usr/bin/env python3
"""NETDEFY — Generate Phase 4B & Phase 4 Comparative Empirical Visualizations."""

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

AE_DIR = PROJECT_ROOT / "artifacts" / "models" / "autoencoder" / "v1"
IF_DIR = PROJECT_ROOT / "artifacts" / "models" / "isolation_forest" / "v1"


def plot_training_convergence() -> Path:
    """Plot training vs validation reconstruction loss across epochs."""
    with open(AE_DIR / "training_history.json", encoding="utf-8") as f:
        hist = json.load(f)

    epochs = list(range(1, len(hist["train_losses"]) + 1))
    train_loss = hist["train_losses"]
    val_loss = hist["val_losses"]
    best_epoch = hist["best_epoch"]
    best_val_loss = hist["best_val_loss"]

    plt.figure(figsize=(9, 5), dpi=300)
    plt.plot(
        epochs,
        train_loss,
        label="Training Reconstruction Loss (MSE)",
        color="#1f77b4",
        linewidth=2.0,
    )
    plt.plot(epochs, val_loss, label="Benign Validation Loss (MSE)", color="#ff7f0e", linewidth=2.0)
    plt.axvline(
        best_epoch,
        color="#2ca02c",
        linestyle="--",
        alpha=0.8,
        label=f"Best Checkpoint (Epoch {best_epoch})",
    )
    plt.scatter([best_epoch], [best_val_loss], color="#2ca02c", s=80, zorder=5)

    plt.title(
        "Deep Autoencoder Training Convergence & Early Stopping (Unsupervised One-Class)",
        fontsize=13,
        fontweight="bold",
    )
    plt.xlabel("Epoch", fontsize=11)
    plt.ylabel("Mean Squared Error (MSE)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(fontsize=10)
    plt.tight_layout()

    out_path = FIGURES_DIR / "phase4b_training_convergence.png"
    plt.savefig(out_path)
    plt.close()
    return out_path


def plot_model_comparison_metrics() -> Path:
    """Bar plot comparing ROC-AUC, PR-AUC, and F1 across Isolation Forest and Autoencoder."""
    with open(IF_DIR / "test_metrics.json", encoding="utf-8") as f:
        if_test = json.load(f)["full_test_report"]
    with open(AE_DIR / "test_metrics.json", encoding="utf-8") as f:
        ae_test = json.load(f)["full_test_report"]

    metrics = [
        "Test ROC-AUC",
        "Test PR-AUC",
        "F1 at p95.0",
        "F1 at p99.0",
        "Precision at p99.0",
    ]
    if_vals = [
        if_test["roc_auc"],
        if_test["pr_auc"],
        if_test["metrics_by_threshold"]["p95.0"]["f1"],
        if_test["metrics_by_threshold"]["p99.0"]["f1"],
        if_test["metrics_by_threshold"]["p99.0"]["precision"],
    ]
    ae_vals = [
        ae_test["roc_auc"],
        ae_test["pr_auc"],
        ae_test["metrics_by_threshold"]["p95.0"]["f1"],
        ae_test["metrics_by_threshold"]["p99.0"]["f1"],
        ae_test["metrics_by_threshold"]["p99.0"]["precision"],
    ]

    x = np.arange(len(metrics))
    width = 0.35

    plt.figure(figsize=(10, 5.5), dpi=300)
    rects1 = plt.bar(x - width / 2, if_vals, width, label="Isolation Forest (4A)", color="#4682B4")
    rects2 = plt.bar(x + width / 2, ae_vals, width, label="Deep Autoencoder (4B)", color="#D9534F")

    plt.title(
        "Empirical Baseline Comparison: Isolation Forest vs. Deep Autoencoder",
        fontsize=13,
        fontweight="bold",
    )
    plt.ylabel("Score", fontsize=11)
    plt.xticks(x, metrics, fontsize=10)
    plt.ylim(0, 1.0)
    plt.grid(True, axis="y", linestyle=":", alpha=0.6)
    plt.legend(fontsize=10)

    # Add values on top of bars
    for rect in rects1:
        h = rect.get_height()
        plt.annotate(
            f"{h:.3f}",
            xy=(rect.get_x() + rect.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    for rect in rects2:
        h = rect.get_height()
        plt.annotate(
            f"{h:.3f}",
            xy=(rect.get_x() + rect.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.tight_layout()
    out_path = FIGURES_DIR / "phase4_model_comparison_metrics.png"
    plt.savefig(out_path)
    plt.close()
    return out_path


def plot_attack_wise_recall() -> Path:
    """Comparison of attack-wise recall across represented test classes."""
    with open(IF_DIR / "test_metrics.json", encoding="utf-8") as f:
        if_test = json.load(f)["full_test_report"]
    with open(AE_DIR / "test_metrics.json", encoding="utf-8") as f:
        ae_test = json.load(f)["full_test_report"]

    attacks = [
        "DDoS\n(5.5k)",
        "Bot\n(85)",
        "Infiltration\n(2)",
        "PortScan\n(6.8k)",
        "Web Attacks\n(94)",
    ]
    if_rec = [
        if_test["attack_wise_recall_by_threshold"]["p99.0"].get("DDoS", 0.0),
        if_test["attack_wise_recall_by_threshold"]["p99.0"].get("Bot", 0.0),
        if_test["attack_wise_recall_by_threshold"]["p99.0"].get("Infiltration", 0.0),
        if_test["attack_wise_recall_by_threshold"]["p99.0"].get("PortScan", 0.0),
        (
            if_test["attack_wise_recall_by_threshold"]["p99.0"].get("Web Attack  Brute Force", 0.0)
            * 65
            + if_test["attack_wise_recall_by_threshold"]["p99.0"].get("Web Attack  XSS", 0.0) * 28
            + if_test["attack_wise_recall_by_threshold"]["p99.0"].get(
                "Web Attack  Sql Injection", 0.0
            )
            * 1
        )
        / 94.0,
    ]
    ae_rec = [
        ae_test["attack_wise_recall_by_threshold"]["p99.0"].get("DDoS", 0.0),
        ae_test["attack_wise_recall_by_threshold"]["p99.0"].get("Bot", 0.0),
        ae_test["attack_wise_recall_by_threshold"]["p99.0"].get("Infiltration", 0.0),
        ae_test["attack_wise_recall_by_threshold"]["p99.0"].get("PortScan", 0.0),
        (
            ae_test["attack_wise_recall_by_threshold"]["p99.0"].get("Web Attack  Brute Force", 0.0)
            * 65
            + ae_test["attack_wise_recall_by_threshold"]["p99.0"].get("Web Attack  XSS", 0.0) * 28
            + ae_test["attack_wise_recall_by_threshold"]["p99.0"].get(
                "Web Attack  Sql Injection", 0.0
            )
            * 1
        )
        / 94.0,
    ]

    x = np.arange(len(attacks))
    width = 0.35

    plt.figure(figsize=(10, 5), dpi=300)
    plt.bar(
        x - width / 2,
        [v * 100 for v in if_rec],
        width,
        label="Isolation Forest Recall (%)",
        color="#4682B4",
    )
    plt.bar(
        x + width / 2,
        [v * 100 for v in ae_rec],
        width,
        label="Deep Autoencoder Recall (%)",
        color="#D9534F",
    )

    plt.title(
        "Attack-Wise Recall Comparison on Test Holdout (Threshold: p99.0)",
        fontsize=13,
        fontweight="bold",
    )
    plt.ylabel("Recall (%)", fontsize=11)
    plt.xticks(x, attacks, fontsize=10)
    plt.ylim(0, 100)
    plt.grid(True, axis="y", linestyle=":", alpha=0.6)
    plt.legend(fontsize=10)
    plt.tight_layout()

    out_path = FIGURES_DIR / "phase4_attack_wise_recall.png"
    plt.savefig(out_path)
    plt.close()
    return out_path


def main() -> None:
    p1 = plot_training_convergence()
    print(f"Generated: {p1}")
    p2 = plot_model_comparison_metrics()
    print(f"Generated: {p2}")
    p3 = plot_attack_wise_recall()
    print(f"Generated: {p3}")


if __name__ == "__main__":
    main()
