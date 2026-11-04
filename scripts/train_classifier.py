#!/usr/bin/env python3
"""NETDEFY — Phase 4C: Train Supervised Attack Classifier & Evaluate Validation.

Trains an XGBoost multiclass attack classifier on 30k Tuesday/Wednesday flows,
handling class imbalance with sample weights and selecting checkpoints on validation loss.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import psutil
import pyarrow.parquet as pq
import xgboost as xgb  # noqa: F401
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from netdefy.evaluation.classifier_evaluator import ClassifierEvaluator
from netdefy.models.xgboost_classifier import XGBoostClassifierConfig
from netdefy.training.classifier_trainer import ClassifierTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("netdefy.train_classifier")


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

    for key in ["classifier_train", "validation"]:
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


def train_and_evaluate(
    config_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Main classifier training and validation evaluation routine."""
    start_total_time = time.perf_counter()
    process = psutil.Process()
    start_mem = process.memory_info().rss / (1024**2)

    logger.info("Loading config: %s (Initial RAM: %.2f MB)", config_path, start_mem)
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    benchmark_dir = PROJECT_ROOT / cfg["data"]["benchmark_dir"]
    train_file = benchmark_dir / cfg["data"]["train_file"]
    val_file = benchmark_dir / cfg["data"]["validation_file"]

    target_output_dir = output_dir or (PROJECT_ROOT / cfg["output"]["artifact_dir"])
    target_output_dir.mkdir(parents=True, exist_ok=True)

    # Copy feature schema and save model_config
    shutil.copy2(
        benchmark_dir / "metadata" / "feature_schema.json",
        target_output_dir / "feature_schema.json",
    )
    with open(target_output_dir / "model_config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    # 1. Pre-training verification
    logger.info("=== STEP 1: Pre-training Verification ===")
    feature_cols = verify_benchmark_integrity(benchmark_dir)

    train_df = pq.read_table(train_file).to_pandas()
    val_df = pq.read_table(val_file).to_pandas()

    label_col = cfg["data"]["label_column"]
    logger.info(
        "Loaded datasets: Train=%d rows (%d cols), Val=%d rows (%d cols)",
        len(train_df),
        len(train_df.columns),
        len(val_df),
        len(val_df.columns),
    )

    # 2. Train Model
    logger.info("=== STEP 2: Training XGBoost Multiclass Classifier ===")
    model_cfg = cfg["model"]
    clf_config = XGBoostClassifierConfig(
        n_estimators=model_cfg["n_estimators"],
        max_depth=model_cfg["max_depth"],
        learning_rate=model_cfg["learning_rate"],
        subsample=model_cfg["subsample"],
        colsample_bytree=model_cfg["colsample_bytree"],
        min_child_weight=model_cfg["min_child_weight"],
        gamma=model_cfg["gamma"],
        reg_alpha=model_cfg["reg_alpha"],
        reg_lambda=model_cfg["reg_lambda"],
        objective=model_cfg["objective"],
        eval_metric=model_cfg["eval_metric"],
        tree_method=model_cfg["tree_method"],
        random_state=model_cfg["random_state"],
        n_jobs=model_cfg["n_jobs"],
        early_stopping_rounds=model_cfg["early_stopping_rounds"],
        confidence_threshold=model_cfg["confidence_threshold"],
    )

    use_weights = bool(cfg["training"].get("use_class_weights", True))
    trainer = ClassifierTrainer(config=clf_config, use_class_weights=use_weights)

    train_res = trainer.train(
        train_df=train_df,
        val_df=val_df,
        feature_columns=feature_cols,
        label_column=label_col,
    )

    # Save model artifacts
    model_path = target_output_dir / "model.json"
    model_sha256 = train_res.classifier.save(model_path)
    logger.info("Saved model artifact to: %s (SHA-256=%s)", model_path, model_sha256[:12])

    # Save class mapping
    class_map_path = target_output_dir / "class_mapping.json"
    with open(class_map_path, "w", encoding="utf-8") as f:
        json.dump(train_res.class_mapping, f, indent=2)

    # Save feature importances
    feat_imp_path = target_output_dir / "feature_importance.json"
    with open(feat_imp_path, "w", encoding="utf-8") as f:
        json.dump(train_res.feature_importances, f, indent=2)

    # 3. Evaluate Validation
    logger.info("=== STEP 3: Diagnostic Evaluation on Validation Set ===")
    evaluator = ClassifierEvaluator(
        classifier=train_res.classifier,
        feature_columns=feature_cols,
        label_column=label_col,
    )
    val_report, val_curve = evaluator.evaluate_validation(val_df=val_df)

    val_metrics_path = target_output_dir / "validation_metrics.json"
    with open(val_metrics_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "validation_report": val_report.to_dict(),
                "confidence_curve": val_curve,
            },
            f,
            indent=2,
        )
    logger.info(
        "Validation Evaluation: Accuracy=%.4f, Macro F1=%.4f, Weighted F1=%.4f, Log Loss=%s",
        val_report.accuracy,
        val_report.macro_f1,
        val_report.weighted_f1,
        val_report.log_loss_value,
    )

    # Save training summary
    total_time = time.perf_counter() - start_total_time
    peak_mem = process.memory_info().rss / (1024**2)

    summary = {
        "status": "SUCCESS",
        "model_type": "xgboost_classifier",
        "model_artifact": str(model_path.relative_to(PROJECT_ROOT)),
        "model_sha256": model_sha256,
        "train_sample_count": len(train_df),
        "validation_sample_count": len(val_df),
        "fit_duration_seconds": round(train_res.train_duration_seconds, 2),
        "total_duration_seconds": round(total_time, 2),
        "peak_memory_mb": round(peak_mem, 2),
        "best_iteration": train_res.best_iteration,
        "class_mapping": train_res.class_mapping,
        "use_class_weights": use_weights,
        "validation_accuracy": val_report.accuracy,
        "validation_balanced_accuracy": val_report.balanced_accuracy,
        "validation_macro_f1": val_report.macro_f1,
        "validation_weighted_f1": val_report.weighted_f1,
        "validation_log_loss": val_report.log_loss_value,
        "top_5_features_gain": dict(list(train_res.feature_importances.items())[:5]),
    }

    with open(target_output_dir / "training_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info("Classifier training complete in %.2f s.", total_time)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Train NETDEFY Supervised Attack Classifier.")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "models" / "xgboost_classifier.yaml",
        help="Path to YAML configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override artifact output directory",
    )
    args = parser.parse_args()

    train_and_evaluate(config_path=args.config, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
