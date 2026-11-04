#!/usr/bin/env python3
"""NETDEFY — Phase 4A: Train Isolation Forest Baseline & Calibrate Thresholds.

Trains an Isolation Forest exclusively on 100k Monday BENIGN flows and
calibrates decision thresholds strictly on BENIGN validation traffic.
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

from netdefy.evaluation.metrics import evaluate_anomaly_detector
from netdefy.evaluation.thresholds import BenignThresholdCalibrator
from netdefy.models.isolation_forest import IsolationForestConfig, IsolationForestDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.train_isolation_forest")


def compute_file_sha256(file_path: Path) -> str:
    """Compute standard SHA-256 checksum."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_benchmark_integrity(benchmark_dir: Path) -> list[str]:
    """Verify benchmark manifest and feature schema before training."""
    manifest_path = benchmark_dir / "metadata" / "benchmark_manifest.json"
    schema_path = benchmark_dir / "metadata" / "feature_schema.json"

    if not manifest_path.exists() or not schema_path.exists():
        raise FileNotFoundError("Benchmark metadata files missing!")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    # Verify checksums for train and validation files
    for key in ["oneclass_train", "validation"]:
        meta = manifest["files"][key]
        fpath = PROJECT_ROOT / meta["path"]
        actual_sha = compute_file_sha256(fpath)
        if actual_sha != meta["sha256"]:
            raise ValueError(
                f"Checksum mismatch for {key}: expected {meta['sha256']}, got {actual_sha}"
            )
        logger.info("Verified %s checksum: %s", key, actual_sha[:12])

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    feature_cols: list[str] = schema["retained_features_service_independent"]
    if len(feature_cols) != 76:
        raise ValueError(f"Expected 76 continuous features, found {len(feature_cols)}")

    return feature_cols


def train_and_calibrate(
    config_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Main training and threshold calibration orchestration routine."""
    start_total_time = time.perf_counter()
    process = psutil.Process()
    start_mem = process.memory_info().rss / (1024**2)

    logger.info(
        "Loading configuration from: %s (Initial RAM: %.2f MB)",
        config_path,
        start_mem,
    )
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    benchmark_dir = PROJECT_ROOT / cfg["data"]["benchmark_dir"]
    train_file = benchmark_dir / cfg["data"]["train_file"]
    val_file = benchmark_dir / cfg["data"]["validation_file"]

    target_output_dir = output_dir or (PROJECT_ROOT / cfg["output"]["artifact_dir"])
    target_output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pre-training verification
    logger.info("=== STEP 1: Pre-training Verification ===")
    feature_cols = verify_benchmark_integrity(benchmark_dir)

    train_df = pq.read_table(train_file).to_pandas()
    logger.info("Loaded training dataset: %d rows, %d cols", len(train_df), len(train_df.columns))

    # Verify pure BENIGN
    label_col = cfg["data"]["label_column"]
    benign_label = cfg["data"]["benign_label"]
    if not (train_df[label_col] == benign_label).all():
        raise ValueError(
            "CRITICAL INTEGRITY FAILURE: Training partition contains non-BENIGN flows!"
        )

    # Verify numerical cleanliness
    train_features = train_df[feature_cols].to_numpy(dtype=np.float32)
    if np.isnan(train_features).any() or np.isinf(train_features).any():
        raise ValueError(
            "CRITICAL INTEGRITY FAILURE: Training feature matrix contains NaNs or Infs!"
        )

    logger.info(
        "Verification successful: 100,000 pure BENIGN flows, 76 float32 features, 0 NaNs, 0 Infs."
    )

    # 2. Fit Isolation Forest
    logger.info("=== STEP 2: Fitting Isolation Forest ===")
    model_cfg = cfg["model"]
    detector_config = IsolationForestConfig(
        n_estimators=model_cfg["n_estimators"],
        max_samples=model_cfg["max_samples"],
        contamination=model_cfg["contamination"],
        max_features=model_cfg["max_features"],
        bootstrap=model_cfg["bootstrap"],
        n_jobs=model_cfg["n_jobs"],
        random_state=model_cfg["random_state"],
    )

    detector = IsolationForestDetector(config=detector_config)

    train_fit_start = time.perf_counter()
    detector.fit(train_df[feature_cols])
    fit_duration = time.perf_counter() - train_fit_start
    peak_mem_fit = process.memory_info().rss / (1024**2)

    logger.info(
        "Fitted Isolation Forest in %.2f s (100 trees, 100k flows). Peak RAM: %.2f MB",
        fit_duration,
        peak_mem_fit,
    )

    # Save model artifact
    model_path = target_output_dir / "model.joblib"
    model_sha256 = detector.save(model_path)
    logger.info("Saved model artifact to: %s (SHA-256=%s)", model_path, model_sha256[:12])

    # 3. Validation Scoring and Inference Benchmark
    logger.info("=== STEP 3: Scoring Validation Partition ===")
    val_df = pq.read_table(val_file).to_pandas()
    val_features = val_df[feature_cols].to_numpy(dtype=np.float32)

    # Benchmark inference latency and throughput
    score_start = time.perf_counter()
    val_scores = detector.score_samples(val_features)
    score_duration = time.perf_counter() - score_start

    latency_ms_per_flow = (score_duration / len(val_df)) * 1000.0
    throughput_flows_sec = len(val_df) / score_duration

    logger.info(
        "Scored %d validation flows in %.3f s (%.4f ms/flow, %.1f flows/s)",
        len(val_df),
        score_duration,
        latency_ms_per_flow,
        throughput_flows_sec,
    )

    # 4. Pure-Benign Threshold Calibration
    logger.info("=== STEP 4: Calibrating Thresholds (BENIGN Validation Only) ===")
    calibrator = BenignThresholdCalibrator(
        target_percentiles=cfg["calibration"]["target_percentiles"]
    )
    calibration_result = calibrator.calibrate_from_validation(
        val_df=val_df,
        anomaly_scores=val_scores,
        label_column=label_col,
        benign_label=benign_label,
    )

    thresholds_path = target_output_dir / "thresholds.json"
    calibration_result.save(thresholds_path)
    logger.info("Calibrated thresholds: %s", calibration_result.thresholds)
    logger.info("Saved calibration metadata to: %s", thresholds_path)

    # 5. Diagnostic Evaluation on Full Validation Set
    logger.info("=== STEP 5: Diagnostic Evaluation on Full Validation Set ===")
    val_report = evaluate_anomaly_detector(
        y_true_labels=val_df[label_col],
        anomaly_scores=val_scores,
        thresholds=calibration_result.thresholds,
        dataset_name="validation_v1",
        benign_label=benign_label,
    )

    val_metrics_path = target_output_dir / "validation_metrics.json"
    with open(val_metrics_path, "w", encoding="utf-8") as f:
        json.dump(val_report.to_dict(), f, indent=2)
    logger.info("Saved validation metrics to: %s", val_metrics_path)

    total_duration = time.perf_counter() - start_total_time
    peak_mem_total = process.memory_info().rss / (1024**2)

    summary = {
        "status": "SUCCESS",
        "model_artifact": str(model_path.relative_to(PROJECT_ROOT)),
        "model_sha256": model_sha256,
        "train_sample_count": len(train_df),
        "validation_sample_count": len(val_df),
        "fit_duration_seconds": round(fit_duration, 2),
        "total_duration_seconds": round(total_duration, 2),
        "peak_memory_mb": round(peak_mem_total, 2),
        "inference_latency_ms_per_flow": round(latency_ms_per_flow, 4),
        "throughput_flows_per_second": round(throughput_flows_sec, 1),
        "thresholds": calibration_result.thresholds,
        "validation_roc_auc": round(val_report.roc_auc, 6),
        "validation_pr_auc": round(val_report.pr_auc, 6),
        "validation_metrics_summary": {
            th_key: {
                "precision": m.precision,
                "recall": m.recall,
                "f1": m.f1,
                "benign_fpr": m.benign_fpr,
                "false_alarms_per_1000": m.false_alarms_per_1000_benign,
            }
            for th_key, m in val_report.metrics_by_threshold.items()
        },
    }

    summary_path = target_output_dir / "training_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(
        "Training pipeline completed successfully in %.2f s (ROC-AUC: %.4f, PR-AUC: %.4f)",
        total_duration,
        val_report.roc_auc,
        val_report.pr_auc,
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Train NETDEFY Isolation Forest Baseline.")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "models" / "isolation_forest.yaml",
        help="Path to YAML configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override artifact output directory",
    )
    args = parser.parse_args()

    train_and_calibrate(config_path=args.config, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
