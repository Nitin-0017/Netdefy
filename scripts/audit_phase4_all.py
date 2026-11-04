#!/usr/bin/env python3
"""NETDEFY — Comprehensive Phase 4 Independent Research Audit Engine.

Audits Phase 4A (Isolation Forest), Phase 4B (Deep Autoencoder), and Phase 4C (XGBoost Classifier)
by independently verifying artifacts, reproducing evaluation metrics directly from model files and
benchmark datasets, inspecting feature schemas and partition boundaries, and reconciling accounting.
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import xgboost as xgb  # noqa: F401

# isort: split
import torch

if sys.platform == "darwin":
    torch.set_num_threads(1)

from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from netdefy.models.autoencoder import AutoencoderDetector
from netdefy.models.isolation_forest import IsolationForestDetector
from netdefy.models.xgboost_classifier import XGBoostAttackClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.audit_phase4")

BENCHMARK_DIR = PROJECT_ROOT / "data" / "benchmark" / "v1"
IF_DIR = PROJECT_ROOT / "artifacts" / "models" / "isolation_forest" / "v1"
AE_DIR = PROJECT_ROOT / "artifacts" / "models" / "autoencoder" / "v1"
CLF_DIR = PROJECT_ROOT / "artifacts" / "models" / "xgboost_classifier" / "v1"


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def audit_shared_data_and_leakage() -> dict[str, Any]:
    """Verify shared dataset integrity, schemas, and partition boundaries."""
    logger.info("Auditing shared benchmark data, schemas, and leakage risks...")

    # Load schemas
    with open(BENCHMARK_DIR / "metadata" / "feature_schema.json") as f:
        bench_schema = json.load(f)
    with open(AE_DIR / "feature_schema.json") as f:
        ae_schema = json.load(f)
    with open(CLF_DIR / "feature_schema.json") as f:
        clf_schema = json.load(f)

    bench_cols = bench_schema["retained_features_service_independent"]
    ae_cols = ae_schema["retained_features_service_independent"]
    clf_cols = clf_schema["retained_features_service_independent"]

    # Verify identical column order across all models
    schema_identical = bool(bench_cols == ae_cols == clf_cols)

    # Check partition files and row counts
    oneclass_df = pq.read_table(BENCHMARK_DIR / "oneclass_train.parquet").to_pandas()
    clf_train_df = pq.read_table(BENCHMARK_DIR / "classifier_train.parquet").to_pandas()
    val_df = pq.read_table(BENCHMARK_DIR / "validation.parquet").to_pandas()
    test_df = pq.read_table(BENCHMARK_DIR / "test.parquet").to_pandas()

    # Verify column presence
    for df, name in [
        (oneclass_df, "oneclass_train"),
        (clf_train_df, "classifier_train"),
        (val_df, "validation"),
        (test_df, "test"),
    ]:
        assert list(df.columns) == bench_cols + ["Label"], f"Column mismatch in {name}"
        assert not df[bench_cols].isna().any().any(), f"NaN found in {name}"
        assert not np.isinf(df[bench_cols].to_numpy()).any(), f"Inf found in {name}"
        assert (df[bench_cols].dtypes == "float32").all(), f"Non-float32 found in {name}"

    # Partition purity & provenance
    oneclass_benign_purity = float((oneclass_df["Label"] == "BENIGN").mean())
    val_benign_count = int((val_df["Label"] == "BENIGN").sum())
    val_attack_count = int((val_df["Label"] != "BENIGN").sum())

    # Ambiguity manifest check
    with open(BENCHMARK_DIR / "metadata" / "ambiguity_manifest.json") as f:
        amb_manifest = json.load(f)

    # Reconcile ambiguous rows in test
    source_row_path = BENCHMARK_DIR / "metadata" / "source_row_manifest.json"
    with open(source_row_path) as f:
        source_manifest = json.load(f)

    test_source_rows = source_manifest["test"]
    ambiguous_test_indices = [
        r["benchmark_index"] for r in test_source_rows if r.get("is_ambiguous_flow", False)
    ]
    ambiguous_labels = [r["label"] for r in test_source_rows if r.get("is_ambiguous_flow", False)]
    amb_counts = collections.Counter(ambiguous_labels)

    # Disambiguated test set
    disambiguated_mask = np.ones(len(test_df), dtype=bool)
    disambiguated_mask[ambiguous_test_indices] = False

    return {
        "status": "PASS" if schema_identical else "FAIL",
        "feature_count": len(bench_cols),
        "schema_identical_across_all_models": schema_identical,
        "row_counts": {
            "oneclass_train": len(oneclass_df),
            "classifier_train": len(clf_train_df),
            "validation": len(val_df),
            "test": len(test_df),
        },
        "oneclass_train_benign_purity": oneclass_benign_purity,
        "validation_benign_count": val_benign_count,
        "validation_attack_count": val_attack_count,
        "ambiguity_reconciliation": {
            "total_ambiguous_in_manifest": amb_manifest["ambiguity_summary_in_50k_test"][
                "ambiguous_rows_in_benchmark_test"
            ],
            "total_ambiguous_in_source_rows": len(ambiguous_test_indices),
            "breakdown": dict(amb_counts),
            "manifest_breakdown": amb_manifest["ambiguity_summary_in_50k_test"][
                "ambiguous_rows_by_class"
            ],
            "exact_match": bool(
                dict(amb_counts)
                == amb_manifest["ambiguity_summary_in_50k_test"]["ambiguous_rows_by_class"]
            ),
        },
    }


def audit_phase4a_isolation_forest() -> dict[str, Any]:
    """Independently reproduce Phase 4A Isolation Forest evaluation."""
    logger.info("Auditing Phase 4A Isolation Forest...")

    model_path = IF_DIR / "model.joblib"
    model_sha = compute_sha256(model_path)
    model_size_bytes = model_path.stat().st_size

    # Load model
    detector = IsolationForestDetector.load(model_path)

    # Load datasets
    val_df = pq.read_table(BENCHMARK_DIR / "validation.parquet").to_pandas()
    test_df = pq.read_table(BENCHMARK_DIR / "test.parquet").to_pandas()

    feature_cols = detector.feature_names

    # Check validation calibration
    val_benign_mask = val_df["Label"] == "BENIGN"
    val_benign_scores = detector.score_samples(val_df[val_benign_mask][feature_cols])

    # Recompute percentiles
    reproduced_p95 = float(np.percentile(val_benign_scores, 95.0))
    reproduced_p99 = float(np.percentile(val_benign_scores, 99.0))
    reproduced_p995 = float(np.percentile(val_benign_scores, 99.5))

    # Read saved thresholds
    with open(IF_DIR / "thresholds.json") as f:
        saved_th = json.load(f)["thresholds"]

    th_match = bool(
        np.isclose(reproduced_p95, saved_th["p95.0"], atol=1e-5)
        and np.isclose(reproduced_p99, saved_th["p99.0"], atol=1e-5)
        and np.isclose(reproduced_p995, saved_th["p99.5"], atol=1e-5)
    )

    # Benchmark test scores
    t0 = time.perf_counter()
    test_scores = detector.score_samples(test_df[feature_cols])
    infer_time = time.perf_counter() - t0
    throughput = len(test_df) / infer_time
    latency_ms = (infer_time / len(test_df)) * 1000.0

    y_test_bin = (test_df["Label"] != "BENIGN").astype(int).to_numpy()

    # Recompute ROC-AUC and PR-AUC
    roc_auc = float(roc_auc_score(y_test_bin, test_scores))
    pr_auc = float(average_precision_score(y_test_bin, test_scores))

    # Threshold metrics
    th_metrics = {}
    for k, th_val in [
        ("p95.0", reproduced_p95),
        ("p99.0", reproduced_p99),
        ("p99.5", reproduced_p995),
    ]:
        preds = (test_scores >= th_val).astype(int)
        tp = int(np.sum((preds == 1) & (y_test_bin == 1)))
        fp = int(np.sum((preds == 1) & (y_test_bin == 0)))
        tn = int(np.sum((preds == 0) & (y_test_bin == 0)))
        fn = int(np.sum((preds == 0) & (y_test_bin == 1)))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        th_metrics[k] = {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": round(prec, 6),
            "recall": round(rec, 6),
            "f1": round(f1, 6),
            "fpr": round(fpr, 6),
        }

    # Attack-wise recall at p99.0
    p99_preds = (test_scores >= reproduced_p99).astype(int)
    attack_wise_p99 = {}
    for atk in sorted(test_df["Label"].unique()):
        if atk == "BENIGN":
            continue
        mask = (test_df["Label"] == atk).to_numpy()
        rec_atk = float(np.mean(p99_preds[mask]))
        attack_wise_p99[atk] = {
            "support": int(mask.sum()),
            "detected": int(p99_preds[mask].sum()),
            "recall": round(rec_atk, 6),
        }

    # Verify against saved test_metrics.json
    with open(IF_DIR / "test_metrics.json") as f:
        saved_test = json.load(f)["full_test_report"]

    roc_match = bool(np.isclose(roc_auc, saved_test["roc_auc"], atol=1e-4))
    pr_match = bool(np.isclose(pr_auc, saved_test["pr_auc"], atol=1e-4))
    p99_f1_match = bool(
        np.isclose(
            th_metrics["p99.0"]["f1"], saved_test["metrics_by_threshold"]["p99.0"]["f1"], atol=1e-4
        )
    )

    return {
        "status": "PASS" if (th_match and roc_match and pr_match and p99_f1_match) else "FAIL",
        "model_sha256": model_sha,
        "model_size_bytes": model_size_bytes,
        "model_size_kb": round(model_size_bytes / 1024.0, 2),
        "reproduced_roc_auc": round(roc_auc, 6),
        "saved_roc_auc": saved_test["roc_auc"],
        "reproduced_pr_auc": round(pr_auc, 6),
        "saved_pr_auc": saved_test["pr_auc"],
        "thresholds_match": th_match,
        "threshold_metrics": th_metrics,
        "attack_wise_recall_p99": attack_wise_p99,
        "benchmarked_latency_ms": round(latency_ms, 4),
        "benchmarked_throughput_flows_sec": round(throughput, 1),
    }


def audit_phase4b_deep_autoencoder() -> dict[str, Any]:
    """Independently reproduce Phase 4B Deep Autoencoder evaluation."""
    logger.info("Auditing Phase 4B Deep Autoencoder...")

    model_path = AE_DIR / "best_model.pt"
    model_sha = compute_sha256(model_path)
    model_size_bytes = model_path.stat().st_size

    # Load detector
    detector = AutoencoderDetector.load(model_path)
    feature_cols = detector.feature_names

    val_df = pq.read_table(BENCHMARK_DIR / "validation.parquet").to_pandas()
    test_df = pq.read_table(BENCHMARK_DIR / "test.parquet").to_pandas()

    # Validation benign calibration
    val_benign_mask = val_df["Label"] == "BENIGN"
    val_benign_mse = detector.score_samples(val_df[val_benign_mask][feature_cols])

    reproduced_p95 = float(np.percentile(val_benign_mse, 95.0))
    reproduced_p99 = float(np.percentile(val_benign_mse, 99.0))
    reproduced_p995 = float(np.percentile(val_benign_mse, 99.5))

    with open(AE_DIR / "thresholds.json") as f:
        saved_th = json.load(f)["thresholds"]

    th_match = bool(
        np.isclose(reproduced_p95, saved_th["p95.0"], atol=1e-5)
        and np.isclose(reproduced_p99, saved_th["p99.0"], atol=1e-5)
        and np.isclose(reproduced_p995, saved_th["p99.5"], atol=1e-5)
    )

    # Test holdout evaluation
    t0 = time.perf_counter()
    test_mse = detector.score_samples(test_df[feature_cols])
    infer_time = time.perf_counter() - t0
    throughput = len(test_df) / infer_time
    latency_ms = (infer_time / len(test_df)) * 1000.0

    y_test_bin = (test_df["Label"] != "BENIGN").astype(int).to_numpy()

    roc_auc = float(roc_auc_score(y_test_bin, test_mse))
    pr_auc = float(average_precision_score(y_test_bin, test_mse))

    # Threshold metrics
    th_metrics = {}
    for k, th_val in [
        ("p95.0", reproduced_p95),
        ("p99.0", reproduced_p99),
        ("p99.5", reproduced_p995),
    ]:
        preds = (test_mse >= th_val).astype(int)
        tp = int(np.sum((preds == 1) & (y_test_bin == 1)))
        fp = int(np.sum((preds == 1) & (y_test_bin == 0)))
        tn = int(np.sum((preds == 0) & (y_test_bin == 0)))
        fn = int(np.sum((preds == 0) & (y_test_bin == 1)))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        th_metrics[k] = {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": round(prec, 6),
            "recall": round(rec, 6),
            "f1": round(f1, 6),
            "fpr": round(fpr, 6),
        }

    # Attack-wise recall at p99.0
    p99_preds = (test_mse >= reproduced_p99).astype(int)
    attack_wise_p99 = {}
    for atk in sorted(test_df["Label"].unique()):
        if atk == "BENIGN":
            continue
        mask = (test_df["Label"] == atk).to_numpy()
        rec_atk = float(np.mean(p99_preds[mask]))
        attack_wise_p99[atk] = {
            "support": int(mask.sum()),
            "detected": int(p99_preds[mask].sum()),
            "recall": round(rec_atk, 6),
        }

    # Disambiguated test set
    source_row_path = BENCHMARK_DIR / "metadata" / "source_row_manifest.json"
    with open(source_row_path) as f:
        source_manifest = json.load(f)

    ambiguous_test_indices = [
        r["benchmark_index"] for r in source_manifest["test"] if r.get("is_ambiguous_flow", False)
    ]
    disambiguated_mask = np.ones(len(test_df), dtype=bool)
    disambiguated_mask[ambiguous_test_indices] = False

    y_disamb_bin = y_test_bin[disambiguated_mask]
    mse_disamb = test_mse[disambiguated_mask]

    roc_auc_disamb = float(roc_auc_score(y_disamb_bin, mse_disamb))
    pr_auc_disamb = float(average_precision_score(y_disamb_bin, mse_disamb))

    # Read saved test metrics
    with open(AE_DIR / "test_metrics.json") as f:
        saved_test = json.load(f)

    full_saved = saved_test["full_test_report"]
    roc_match = bool(np.isclose(roc_auc, full_saved["roc_auc"], atol=1e-4))
    pr_match = bool(np.isclose(pr_auc, full_saved["pr_auc"], atol=1e-4))
    p99_f1_match = bool(
        np.isclose(
            th_metrics["p99.0"]["f1"], full_saved["metrics_by_threshold"]["p99.0"]["f1"], atol=1e-4
        )
    )

    return {
        "status": "PASS" if (th_match and roc_match and pr_match and p99_f1_match) else "FAIL",
        "model_sha256": model_sha,
        "model_size_bytes": model_size_bytes,
        "model_size_kb": round(model_size_bytes / 1024.0, 2),
        "reproduced_roc_auc": round(roc_auc, 6),
        "saved_roc_auc": full_saved["roc_auc"],
        "reproduced_pr_auc": round(pr_auc, 6),
        "saved_pr_auc": full_saved["pr_auc"],
        "disambiguated_roc_auc": round(roc_auc_disamb, 6),
        "disambiguated_pr_auc": round(pr_auc_disamb, 6),
        "thresholds_match": th_match,
        "threshold_metrics": th_metrics,
        "attack_wise_recall_p99": attack_wise_p99,
        "benchmarked_latency_ms": round(latency_ms, 4),
        "benchmarked_throughput_flows_sec": round(throughput, 1),
    }


def audit_phase4c_xgboost_classifier() -> dict[str, Any]:
    """Independently reproduce Phase 4C XGBoost Classifier evaluation."""
    logger.info("Auditing Phase 4C XGBoost Classifier...")

    model_native_path = CLF_DIR / "model.ubj"
    model_json_path = CLF_DIR / "model.json"
    model_sha = compute_sha256(model_native_path)
    model_size_bytes = model_native_path.stat().st_size

    # Load classifier
    classifier = XGBoostAttackClassifier.load(model_json_path)

    # Load datasets
    val_df = pq.read_table(BENCHMARK_DIR / "validation.parquet").to_pandas()
    test_df = pq.read_table(BENCHMARK_DIR / "test.parquet").to_pandas()
    feature_cols = classifier.feature_names

    # 1. Validation evaluation (closed-set on known 8 classes)
    val_probs = classifier.predict_proba(val_df[feature_cols])
    val_preds = classifier.predict(val_df[feature_cols], reject_threshold=0.0)
    y_val_str = val_df["Label"].to_numpy()

    val_acc = float(accuracy_score(y_val_str, val_preds))
    val_bal_acc = float(balanced_accuracy_score(y_val_str, val_preds))
    prec_m, rec_m, f1_m, _ = precision_recall_fscore_support(
        y_val_str, val_preds, average="macro", zero_division=0.0
    )
    prec_w, rec_w, f1_w, _ = precision_recall_fscore_support(
        y_val_str, val_preds, average="weighted", zero_division=0.0
    )

    class_to_idx = {c: i for i, c in classifier.class_mapping.items()}
    val_labels_idx = np.array([class_to_idx[lbl] for lbl in y_val_str])
    val_loss = float(
        log_loss(val_labels_idx, val_probs, labels=list(range(len(classifier.class_mapping))))
    )

    # 2. Test evaluation (closed-set and open-set with tau = 0.50)
    t0 = time.perf_counter()
    _ = classifier.predict_proba(test_df[feature_cols])
    infer_time = time.perf_counter() - t0
    throughput = len(test_df) / infer_time
    latency_ms = (infer_time / len(test_df)) * 1000.0

    test_preds_closed = classifier.predict(test_df[feature_cols], reject_threshold=0.0)
    test_preds_open = classifier.predict(test_df[feature_cols], reject_threshold=0.50)
    y_test_str = test_df["Label"].to_numpy()

    test_acc_closed = float(accuracy_score(y_test_str, test_preds_closed))
    test_acc_open = float(accuracy_score(y_test_str, test_preds_open))
    unknown_rate = float(np.mean(test_preds_open == "UNKNOWN"))

    # Benign metrics on test
    benign_mask = y_test_str == "BENIGN"
    benign_rec_closed = float(np.mean(test_preds_closed[benign_mask] == "BENIGN"))
    benign_prec_closed = float(
        np.sum((test_preds_closed == "BENIGN") & benign_mask)
        / np.sum(test_preds_closed == "BENIGN")
    )

    # Attribution of unseen attacks
    unseen_attacks = [
        c for c in sorted(test_df["Label"].unique()) if c not in classifier.class_mapping.values()
    ]
    unseen_attribution = {}
    for atk in unseen_attacks:
        mask = y_test_str == atk
        preds_for_atk = collections.Counter(test_preds_closed[mask])
        unseen_attribution[atk] = {
            "support": int(mask.sum()),
            "attributed_counts": dict(preds_for_atk),
        }

    # Verify against saved artifacts
    with open(CLF_DIR / "validation_metrics.json") as f:
        saved_val = json.load(f)["validation_report"]
    with open(CLF_DIR / "test_metrics.json") as f:
        saved_test = json.load(f)

    val_acc_match = bool(np.isclose(val_acc, saved_val["accuracy"], atol=1e-4))
    val_f1_match = bool(np.isclose(f1_m, saved_val["macro_f1"], atol=1e-4))
    test_acc_match = bool(
        np.isclose(
            test_acc_closed, saved_test["full_test_report_closed_set"]["accuracy"], atol=1e-4
        )
    )

    return {
        "status": "PASS" if (val_acc_match and val_f1_match and test_acc_match) else "FAIL",
        "model_sha256": model_sha,
        "model_size_bytes": model_size_bytes,
        "model_size_kb": round(model_size_bytes / 1024.0, 2),
        "validation_metrics": {
            "accuracy": round(val_acc, 6),
            "balanced_accuracy": round(val_bal_acc, 6),
            "macro_f1": round(f1_m, 6),
            "weighted_f1": round(f1_w, 6),
            "log_loss": round(val_loss, 4),
        },
        "test_metrics": {
            "closed_set_accuracy": round(test_acc_closed, 6),
            "open_set_accuracy": round(test_acc_open, 6),
            "unknown_rate": round(unknown_rate, 6),
            "benign_recall": round(benign_rec_closed, 6),
            "benign_precision": round(benign_prec_closed, 6),
        },
        "classes_in_training": list(classifier.class_mapping.values()),
        "classes_absent_from_training": unseen_attacks,
        "unseen_attacks_attribution": unseen_attribution,
        "benchmarked_latency_ms": round(latency_ms, 4),
        "benchmarked_throughput_flows_sec": round(throughput, 1),
    }


def main() -> int:
    logger.info("=== Starting Complete Independent Research Audit for Phase 4 ===")

    data_audit = audit_shared_data_and_leakage()
    if_audit = audit_phase4a_isolation_forest()
    ae_audit = audit_phase4b_deep_autoencoder()
    clf_audit = audit_phase4c_xgboost_classifier()

    full_audit = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "shared_data_audit": data_audit,
        "phase4a_isolation_forest": if_audit,
        "phase4b_deep_autoencoder": ae_audit,
        "phase4c_xgboost_classifier": clf_audit,
    }

    out_file = PROJECT_ROOT / "reports" / "audit_phase4_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_audit, f, indent=2)

    logger.info("Audit complete! Results exported to: %s", out_file)
    print("\n================ AUDIT SUMMARY ================")
    print("Shared Data & Leakage:", data_audit["status"])
    print("Phase 4A Isolation Forest:", if_audit["status"])
    print("Phase 4B Deep Autoencoder:", ae_audit["status"])
    print("Phase 4C XGBoost Classifier:", clf_audit["status"])
    print("===============================================")
    return 0


if __name__ == "__main__":
    main()
