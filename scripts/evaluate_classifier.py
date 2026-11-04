#!/usr/bin/env python3
"""NETDEFY — Phase 4C: Supervised Attack Classifier Test Evaluation & Error Analysis.

Evaluates the frozen XGBoost classifier on the untouched 50k final test holdout,
measuring closed-set accuracy, open-set unknown attack rejection, and ambiguity impact.
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
import xgboost as xgb
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from netdefy.evaluation.classifier_evaluator import ClassifierEvaluator
from netdefy.models.xgboost_classifier import XGBoostAttackClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.evaluate_classifier")


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
    """Execute final test evaluation, open-set rejection, and artifact manifest generation."""
    start_time = time.perf_counter()

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    benchmark_dir = PROJECT_ROOT / cfg["data"]["benchmark_dir"]
    test_file = benchmark_dir / cfg["data"]["test_file"]
    manifest_path = benchmark_dir / "metadata" / "benchmark_manifest.json"
    provenance_path = benchmark_dir / "metadata" / "source_row_manifest.json"
    schema_path = benchmark_dir / "metadata" / "feature_schema.json"

    target_artifact_dir = artifact_dir or (PROJECT_ROOT / cfg["output"]["artifact_dir"])
    model_path = target_artifact_dir / "model.json"

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

    # Load frozen classifier
    logger.info("Loading frozen classifier from: %s", model_path)
    classifier = XGBoostAttackClassifier.load(model_path)

    # Load test dataset
    test_df = pq.read_table(test_file).to_pandas()
    logger.info("Loaded test partition: %d rows, %d cols", len(test_df), len(test_df.columns))

    label_col = cfg["data"]["label_column"]

    # Load provenance for ambiguity flags
    with open(provenance_path, encoding="utf-8") as f:
        provenance = json.load(f)
    is_ambiguous = [rec["is_ambiguous_flow"] for rec in provenance["test"]]

    # 2. Run Comprehensive Evaluation
    logger.info("=== STEP 2: Running Multi-Protocol Test Evaluation ===")
    evaluator = ClassifierEvaluator(
        classifier=classifier,
        feature_columns=feature_cols,
        label_column=label_col,
    )

    conf_thresh = float(cfg["model"].get("confidence_threshold", 0.50))
    bundle = evaluator.evaluate_test_holdout(
        test_df=test_df,
        is_ambiguous_flags=is_ambiguous,
        reject_threshold=conf_thresh,
    )

    # 3. Save test_metrics.json, confusion_matrix.json, error_analysis.json
    test_metrics_data = bundle.to_test_metrics_dict()
    test_metrics_path = target_artifact_dir / "test_metrics.json"
    with open(test_metrics_path, "w", encoding="utf-8") as f:
        json.dump(test_metrics_data, f, indent=2)
    logger.info("Saved test metrics to: %s", test_metrics_path)

    cm_data = {
        "closed_set_confusion_matrix": bundle.full_test_report_closed.confusion_matrix_data,
        "open_set_confusion_matrix": bundle.full_test_report_open.confusion_matrix_data,
    }
    cm_path = target_artifact_dir / "confusion_matrix.json"
    with open(cm_path, "w", encoding="utf-8") as f:
        json.dump(cm_data, f, indent=2)
    logger.info("Saved confusion matrix to: %s", cm_path)

    error_analysis_data = bundle.to_error_analysis_dict()
    error_analysis_path = target_artifact_dir / "error_analysis.json"
    with open(error_analysis_path, "w", encoding="utf-8") as f:
        json.dump(error_analysis_data, f, indent=2)
    logger.info("Saved error analysis to: %s", error_analysis_path)

    # 4. Generate artifact_manifest.json
    logger.info("=== STEP 3: Generating Immutable Artifact Manifest ===")
    training_file = benchmark_dir / cfg["data"]["train_file"]
    val_file = benchmark_dir / cfg["data"]["validation_file"]

    manifest_bundle = {
        "model_name": cfg["model"]["name"],
        "model_version": cfg["model"]["version"],
        "model_type": "xgboost_classifier",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_benchmark_version": "v1",
        "benchmark_partition_checksums": {
            "classifier_train": compute_file_sha256(training_file),
            "validation": compute_file_sha256(val_file),
            "test": test_actual_sha,
        },
        "feature_schema_fingerprint": compute_file_sha256(schema_path),
        "model_configuration_hash": compute_file_sha256(target_artifact_dir / "model_config.yaml"),
        "artifacts": {
            "model_json": {
                "path": "model.json",
                "sha256": compute_file_sha256(model_path),
            },
            "model_ubj": {
                "path": "model.ubj",
                "sha256": compute_file_sha256(target_artifact_dir / "model.ubj"),
            },
            "class_mapping_json": {
                "path": "class_mapping.json",
                "sha256": compute_file_sha256(target_artifact_dir / "class_mapping.json"),
            },
            "feature_importance_json": {
                "path": "feature_importance.json",
                "sha256": compute_file_sha256(target_artifact_dir / "feature_importance.json"),
            },
            "validation_metrics_json": {
                "path": "validation_metrics.json",
                "sha256": compute_file_sha256(target_artifact_dir / "validation_metrics.json"),
            },
            "test_metrics_json": {
                "path": "test_metrics.json",
                "sha256": compute_file_sha256(test_metrics_path),
            },
            "confusion_matrix_json": {
                "path": "confusion_matrix.json",
                "sha256": compute_file_sha256(cm_path),
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
        "random_seed": cfg["model"]["random_state"],
        "hardware_environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "xgboost_version": xgb.__version__,
        },
    }

    manifest_output_path = target_artifact_dir / "artifact_manifest.json"
    with open(manifest_output_path, "w", encoding="utf-8") as f:
        json.dump(manifest_bundle, f, indent=2)
    logger.info("Saved artifact manifest to: %s", manifest_output_path)

    total_duration = time.perf_counter() - start_time
    logger.info(
        "Evaluation finished in %.2f s (Closed-Set Acc: %.4f | Open-Set Acc: %.4f | Unknown Rate: %.2f%%)",
        total_duration,
        bundle.full_test_report_closed.accuracy,
        bundle.full_test_report_open.accuracy,
        bundle.full_test_report_open.unknown_rate * 100.0,
    )

    return test_metrics_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate NETDEFY XGBoost Attack Classifier.")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "models" / "xgboost_classifier.yaml",
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
