#!/usr/bin/env python3
"""NETDEFY — Phase 4A: Isolation Forest Final Test Evaluation & Error Analysis.

Evaluates the frozen Isolation Forest baseline on the untouched 50k final test holdout,
measuring full protocol, disambiguated protocol, and ambiguous subset performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil
import pyarrow.parquet as pq
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from netdefy.evaluation.error_analysis import (
    analyze_ambiguity_impact,
    analyze_false_negatives,
    analyze_false_positives,
)
from netdefy.evaluation.metrics import evaluate_anomaly_detector
from netdefy.evaluation.thresholds import ThresholdCalibrationResult
from netdefy.models.isolation_forest import IsolationForestDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.evaluate_isolation_forest")


def compute_file_sha256(file_path: Path) -> str:
    """Compute standard SHA-256 checksum."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def run_evaluation(
    config_path: Path,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute final test evaluation and forensic error analysis."""
    start_time = time.perf_counter()
    process = psutil.Process()

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    benchmark_dir = PROJECT_ROOT / cfg["data"]["benchmark_dir"]
    test_file = benchmark_dir / cfg["data"]["test_file"]
    manifest_path = benchmark_dir / "metadata" / "benchmark_manifest.json"
    provenance_path = benchmark_dir / "metadata" / "source_row_manifest.json"
    schema_path = benchmark_dir / "metadata" / "feature_schema.json"

    target_artifact_dir = artifact_dir or (PROJECT_ROOT / cfg["output"]["artifact_dir"])
    model_path = target_artifact_dir / "model.joblib"
    thresholds_path = target_artifact_dir / "thresholds.json"

    logger.info("=== STEP 1: Verifying Final Test Partition Integrity ===")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    test_expected_sha = manifest["files"]["test"]["sha256"]
    test_actual_sha = compute_file_sha256(test_file)
    if test_actual_sha != test_expected_sha:
        raise ValueError(
            f"Test file checksum mismatch: expected {test_expected_sha}, got {test_actual_sha}"
        )
    logger.info("Test file checksum verified: %s", test_actual_sha[:12])

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    feature_cols: list[str] = schema["retained_features_service_independent"]

    # Load frozen model and thresholds
    logger.info("Loading frozen model artifact: %s", model_path)
    detector = IsolationForestDetector.load(model_path)

    logger.info("Loading calibrated thresholds: %s", thresholds_path)
    calib_result = ThresholdCalibrationResult.load(thresholds_path)
    thresholds = calib_result.thresholds

    # Load test dataset
    test_df = pq.read_table(test_file).to_pandas()
    logger.info("Loaded test partition: %d rows, %d cols", len(test_df), len(test_df.columns))

    label_col = cfg["data"]["label_column"]
    benign_label = cfg["data"]["benign_label"]

    # 2. Score Final Test Flows
    logger.info("=== STEP 2: Scoring 50,000 Test Flows ===")
    test_features = test_df[feature_cols].to_numpy(dtype=np.float32)

    score_start = time.perf_counter()
    test_scores = detector.score_samples(test_features)
    score_duration = time.perf_counter() - score_start

    latency_ms_per_flow = (score_duration / len(test_df)) * 1000.0
    throughput_flows_sec = len(test_df) / score_duration

    logger.info(
        "Scored %d test flows in %.3f s (%.4f ms/flow, %.1f flows/s)",
        len(test_df),
        score_duration,
        latency_ms_per_flow,
        throughput_flows_sec,
    )

    # 3. Full Protocol Evaluation (All 50,000 flows)
    logger.info("=== STEP 3: Full Protocol Evaluation (All 50,000 flows) ===")
    full_report = evaluate_anomaly_detector(
        y_true_labels=test_df[label_col],
        anomaly_scores=test_scores,
        thresholds=thresholds,
        dataset_name="test_v1_full",
        benign_label=benign_label,
    )

    # 4. Disambiguated vs Ambiguous Evaluation
    logger.info("=== STEP 4: Ambiguity Disaggregation (130 Conflicting Vectors) ===")
    with open(provenance_path, encoding="utf-8") as f:
        provenance = json.load(f)

    is_ambiguous = [rec["is_ambiguous_flow"] for rec in provenance["test"]]
    ambig_count = sum(is_ambiguous)
    logger.info(
        "Test ambiguity breakdown: %d ambiguous rows (%.2f%%), %d unambiguous rows (%.2f%%)",
        ambig_count,
        (ambig_count / len(test_df)) * 100.0,
        len(test_df) - ambig_count,
        ((len(test_df) - ambig_count) / len(test_df)) * 100.0,
    )

    ambiguity_comparison: dict[str, Any] = {}
    for th_key, th_val in thresholds.items():
        ambiguity_comparison[th_key] = analyze_ambiguity_impact(
            df=test_df,
            anomaly_scores=test_scores,
            threshold=th_val,
            is_ambiguous_flags=is_ambiguous,
            label_column=label_col,
            benign_label=benign_label,
        )

    # Disambiguated Report (Unambiguous subset only)
    unambig_mask = ~np.asarray(is_ambiguous, dtype=bool)
    disambiguated_report = evaluate_anomaly_detector(
        y_true_labels=test_df.iloc[unambig_mask][label_col],
        anomaly_scores=test_scores[unambig_mask],
        thresholds=thresholds,
        dataset_name="test_v1_disambiguated",
        benign_label=benign_label,
    )

    # 5. Error Analysis (False Positives and False Negatives at default p99.0)
    logger.info("=== STEP 5: Error Analysis & Diagnostic Inspection ===")
    default_th_key = f"p{cfg['calibration']['default_percentile']:.1f}"
    default_th_val = thresholds[default_th_key]

    fp_analysis = analyze_false_positives(
        df=test_df,
        anomaly_scores=test_scores,
        threshold=default_th_val,
        feature_columns=feature_cols,
        label_column=label_col,
        benign_label=benign_label,
        top_k=10,
    )

    fn_analysis = analyze_false_negatives(
        df=test_df,
        anomaly_scores=test_scores,
        threshold=default_th_val,
        label_column=label_col,
        benign_label=benign_label,
    )

    error_analysis_data = {
        "evaluation_threshold": {
            "key": default_th_key,
            "value": default_th_val,
        },
        "false_positive_analysis": fp_analysis,
        "false_negative_analysis": fn_analysis,
        "ambiguity_comparison_by_threshold": ambiguity_comparison,
    }

    # Save artifacts
    test_metrics_path = target_artifact_dir / "test_metrics.json"
    with open(test_metrics_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "full_test_report": full_report.to_dict(),
                "disambiguated_test_report": disambiguated_report.to_dict(),
                "latency_ms_per_flow": round(latency_ms_per_flow, 4),
                "throughput_flows_per_second": round(throughput_flows_sec, 1),
            },
            f,
            indent=2,
        )

    error_analysis_path = target_artifact_dir / "error_analysis.json"
    with open(error_analysis_path, "w", encoding="utf-8") as f:
        json.dump(error_analysis_data, f, indent=2)

    total_eval_duration = time.perf_counter() - start_time
    peak_mem = process.memory_info().rss / (1024**2)

    logger.info("Saved test metrics to: %s", test_metrics_path)
    logger.info("Saved error analysis to: %s", error_analysis_path)

    # Print summary tables to console
    print("\n" + "=" * 90)
    print("        NETDEFY — PHASE 4A: ISOLATION FOREST FINAL TEST RESULTS        ")
    print("=" * 90)
    print("Dataset: 50,000 flows (37,474 BENIGN, 12,526 ATTACKS) — Thursday + Friday Holdout")
    print(f"Overall ROC-AUC: {full_report.roc_auc:.4f} | Overall PR-AUC: {full_report.pr_auc:.4f}")
    print("-" * 90)
    print(
        f"{'Threshold':<10}{'Val Target FPR':<16}{'Test FPR':<12}{'Precision':<12}{'Recall':<10}{'F1':<10}{'FP / 1,000'}"
    )
    print("-" * 90)
    for th_k, m in full_report.metrics_by_threshold.items():
        nom_fpr = f"{(100.0 - float(th_k[1:])) / 100.0:.3f}"
        print(
            f"{th_k:<10}{nom_fpr:<16}{m.benign_fpr:<12.4f}{m.precision:<12.4f}{m.recall:<10.4f}{m.f1:<10.4f}{m.false_alarms_per_1000_benign:<10.2f}"
        )
    print("=" * 90)

    print("\n" + "=" * 90)
    print("             ATTACK-WISE RECALL ACROSS CHRONOLOGICAL TEST HOLDOUT             ")
    print("=" * 90)
    print(
        f"{'Attack Category':<32}{'Total Flows':<15}{'Recall (p95.0)':<16}{'Recall (p99.0)':<16}{'Recall (p99.5)'}"
    )
    print("-" * 90)
    for cls_name, count in full_report.attack_counts.items():
        r95 = full_report.attack_wise_recall_by_threshold.get("p95.0", {}).get(cls_name, 0.0)
        r99 = full_report.attack_wise_recall_by_threshold.get("p99.0", {}).get(cls_name, 0.0)
        r995 = full_report.attack_wise_recall_by_threshold.get("p99.5", {}).get(cls_name, 0.0)
        print(f"{cls_name:<32}{count:<15}{r95:<16.4f}{r99:<16.4f}{r995:<16.4f}")
    print("=" * 90)

    print("\n" + "=" * 90)
    print("     AMBIGUITY DISAGGREGATION (130 Conflicting Feature Vectors in Test)      ")
    print("=" * 90)
    print(
        f"{'Protocol':<20}{'Flows':<12}{'Precision (p99.0)':<20}{'Recall (p99.0)':<16}{'F1 (p99.0)'}"
    )
    print("-" * 90)
    f_p99 = full_report.metrics_by_threshold["p99.0"]
    d_p99 = disambiguated_report.metrics_by_threshold["p99.0"]
    amb_p99 = ambiguity_comparison["p99.0"]["ambiguous"]
    print(
        f"{'Full Test (50k)':<20}{len(test_df):<12}{f_p99.precision:<20.4f}{f_p99.recall:<16.4f}{f_p99.f1:<16.4f}"
    )
    print(
        f"{'Disambiguated':<20}{len(test_df) - ambig_count:<12}{d_p99.precision:<20.4f}{d_p99.recall:<16.4f}{d_p99.f1:<16.4f}"
    )
    print(
        f"{'Ambiguous Subset':<20}{ambig_count:<12}{amb_p99['precision']:<20.4f}{amb_p99['recall']:<16.4f}{amb_p99['f1']:<16.4f}"
    )
    print("=" * 90 + "\n")

    return {
        "status": "SUCCESS",
        "full_report": full_report.to_dict(),
        "disambiguated_report": disambiguated_report.to_dict(),
        "error_analysis": error_analysis_data,
        "peak_memory_mb": round(peak_mem, 2),
        "total_duration_seconds": round(total_eval_duration, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate NETDEFY Isolation Forest Baseline.")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "models" / "isolation_forest.yaml",
        help="Path to YAML configuration",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Override artifact directory",
    )
    args = parser.parse_args()

    run_evaluation(config_path=args.config, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
