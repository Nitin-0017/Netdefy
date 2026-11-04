#!/usr/bin/env python3
"""NETDEFY — Phase 4B: Deep Autoencoder Final Test Evaluation & Error Analysis.

Evaluates the frozen Deep Autoencoder on the untouched 50k final test holdout,
measuring full protocol, disambiguated protocol, and ambiguous subset performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import sys
import time
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import torch
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from netdefy.evaluation.autoencoder_evaluator import AutoencoderEvaluator
from netdefy.evaluation.thresholds import ThresholdCalibrationResult
from netdefy.models.autoencoder import AutoencoderDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.evaluate_autoencoder")


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
    """Execute final test evaluation, ambiguity analysis, and manifest generation."""
    start_time = time.perf_counter()

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    benchmark_dir = PROJECT_ROOT / cfg["data"]["benchmark_dir"]
    test_file = benchmark_dir / cfg["data"]["test_file"]
    manifest_path = benchmark_dir / "metadata" / "benchmark_manifest.json"
    provenance_path = benchmark_dir / "metadata" / "source_row_manifest.json"
    schema_path = benchmark_dir / "metadata" / "feature_schema.json"

    target_artifact_dir = artifact_dir or (PROJECT_ROOT / cfg["output"]["artifact_dir"])
    model_path = target_artifact_dir / "best_model.pt"
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
    detector = AutoencoderDetector.load(model_path, device="cpu")

    logger.info("Loading calibrated thresholds: %s", thresholds_path)
    calib_result = ThresholdCalibrationResult.load(thresholds_path)
    thresholds = calib_result.thresholds

    # Load test dataset
    test_df = pq.read_table(test_file).to_pandas()
    logger.info("Loaded test partition: %d rows, %d cols", len(test_df), len(test_df.columns))

    label_col = cfg["data"]["label_column"]
    benign_label = cfg["data"]["benign_label"]

    # Load provenance for ambiguity flags
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

    # 2. Run Comprehensive Evaluation
    evaluator = AutoencoderEvaluator(
        detector=detector,
        feature_columns=feature_cols,
        label_column=label_col,
        benign_label=benign_label,
    )

    default_th_key = f"p{cfg['calibration']['default_percentile']:.1f}"
    default_th_val = thresholds[default_th_key]

    eval_bundle = evaluator.evaluate_test_holdout(
        test_df=test_df,
        thresholds=thresholds,
        is_ambiguous_flags=is_ambiguous,
        default_threshold_key=default_th_key,
        batch_size=cfg["inference"].get("batch_size", 1024),
    )

    # 3. Save test_metrics.json and error_analysis.json
    test_metrics_data = eval_bundle.to_test_metrics_dict()
    test_metrics_path = target_artifact_dir / "test_metrics.json"
    with open(test_metrics_path, "w", encoding="utf-8") as f:
        json.dump(test_metrics_data, f, indent=2)
    logger.info("Saved test metrics to: %s", test_metrics_path)

    error_analysis_data = eval_bundle.to_error_analysis_dict(
        default_th_key=default_th_key,
        default_th_val=default_th_val,
    )
    error_analysis_path = target_artifact_dir / "error_analysis.json"
    with open(error_analysis_path, "w", encoding="utf-8") as f:
        json.dump(error_analysis_data, f, indent=2)
    logger.info("Saved error analysis to: %s", error_analysis_path)

    # 4. Generate artifact_manifest.json
    logger.info("=== STEP 4: Generating Immutable Artifact Manifest ===")
    training_file = benchmark_dir / cfg["data"]["train_file"]
    val_file = benchmark_dir / cfg["data"]["validation_file"]

    manifest_bundle = {
        "model_name": cfg["model"]["name"],
        "model_version": cfg["model"]["version"],
        "model_type": "deep_autoencoder",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_benchmark_version": "v1",
        "benchmark_partition_checksums": {
            "oneclass_train": compute_file_sha256(training_file),
            "validation": compute_file_sha256(val_file),
            "test": test_actual_sha,
        },
        "feature_schema_fingerprint": compute_file_sha256(schema_path),
        "model_configuration_hash": compute_file_sha256(target_artifact_dir / "model_config.yaml"),
        "artifacts": {
            "best_model_pt": {
                "path": "best_model.pt",
                "sha256": compute_file_sha256(model_path),
            },
            "thresholds_json": {
                "path": "thresholds.json",
                "sha256": compute_file_sha256(thresholds_path),
            },
            "training_history_json": {
                "path": "training_history.json",
                "sha256": compute_file_sha256(target_artifact_dir / "training_history.json"),
            },
            "validation_metrics_json": {
                "path": "validation_metrics.json",
                "sha256": compute_file_sha256(target_artifact_dir / "validation_metrics.json"),
            },
            "test_metrics_json": {
                "path": "test_metrics.json",
                "sha256": compute_file_sha256(test_metrics_path),
            },
            "error_analysis_json": {
                "path": "error_analysis.json",
                "sha256": compute_file_sha256(error_analysis_path),
            },
            "feature_schema_json": {
                "path": "feature_schema.json",
                "sha256": compute_file_sha256(target_artifact_dir / "feature_schema.json"),
            },
        },
        "random_seed": cfg["model"]["random_seed"],
        "training_device": cfg["training"].get("device", "cpu"),
        "hardware_environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
        },
    }

    manifest_output_path = target_artifact_dir / "artifact_manifest.json"
    with open(manifest_output_path, "w", encoding="utf-8") as f:
        json.dump(manifest_bundle, f, indent=2)
    logger.info("Saved artifact manifest to: %s", manifest_output_path)

    total_duration = time.perf_counter() - start_time
    logger.info(
        "Evaluation completed in %.2f s (Full Test ROC-AUC: %.4f, PR-AUC: %.4f | Disambiguated ROC-AUC: %.4f, PR-AUC: %.4f)",
        total_duration,
        eval_bundle.full_report.roc_auc,
        eval_bundle.full_report.pr_auc,
        eval_bundle.disambiguated_report.roc_auc,
        eval_bundle.disambiguated_report.pr_auc,
    )

    return test_metrics_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate NETDEFY Deep Autoencoder on Test Holdout."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "models" / "autoencoder.yaml",
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
