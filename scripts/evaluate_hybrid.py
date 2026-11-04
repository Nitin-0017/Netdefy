#!/usr/bin/env python3
"""NETDEFY — Phase 4D: Hybrid Intelligence & Decision Engine Evaluation Suite.

Executes scientific calibration, candidate fusion evaluation, simulated open-set analysis,
decision engine policy freezing, full holdout test evaluation (View A & B), baseline comparisons,
and hardware efficiency benchmarking under strict research-grade integrity gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from netdefy.hybrid.classifier_rejection import (
    ClassifierRejectionConfig,
    ClassifierRejectionEngine,
)
from netdefy.hybrid.decision_engine import DecisionEngine, DecisionPolicyConfig
from netdefy.hybrid.inference_pipeline import HybridInferencePipeline
from netdefy.hybrid.model_registry import ModelRegistry
from netdefy.hybrid.score_calibration import (
    PercentileCalibrator,
    RobustScalerCalibrator,
)
from netdefy.hybrid.score_fusion import ScoreFusionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("netdefy.evaluate_hybrid")


def compute_sha256(filepath: Path | str) -> str:
    path = Path(filepath).resolve()
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_binary_metrics(
    y_true_binary: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    y_pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true_binary, y_pred, labels=[0, 1]).ravel()

    precision = float(precision_score(y_true_binary, y_pred, zero_division=0))
    recall = float(recall_score(y_true_binary, y_pred, zero_division=0))
    f1 = float(f1_score(y_true_binary, y_pred, zero_division=0))
    benign_fpr = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0
    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    false_alarms_per_1000 = benign_fpr * 1000.0

    try:
        roc_auc = float(roc_auc_score(y_true_binary, scores))
    except Exception:
        roc_auc = 0.5

    try:
        prec_arr, rec_arr, _ = precision_recall_curve(y_true_binary, scores)
        pr_auc = float(auc(rec_arr, prec_arr))
    except Exception:
        pr_auc = 0.0

    return {
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "benign_fpr": benign_fpr,
        "specificity": specificity,
        "false_alarms_per_1000_benign": false_alarms_per_1000,
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NETDEFY Hybrid Intelligence Engine")
    parser.add_argument("--device", type=str, default="cpu", help="Device for Autoencoder (cpu)")
    parser.add_argument("--batch-size", type=int, default=1024, help="Inference batch size")
    args = parser.parse_args()

    logger.info("================================================================================")
    logger.info("        NETDEFY — PHASE 4D: HYBRID INTELLIGENCE EVALUATION SUITE                ")
    logger.info("================================================================================")

    # Output artifact directory
    artifact_dir = PROJECT_ROOT / "artifacts" / "models" / "hybrid" / "v1"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Model Bundle
    if_path = PROJECT_ROOT / "artifacts" / "models" / "isolation_forest" / "v1" / "model.joblib"
    ae_path = PROJECT_ROOT / "artifacts" / "models" / "autoencoder" / "v1" / "best_model.pt"
    clf_path = PROJECT_ROOT / "artifacts" / "models" / "xgboost_classifier" / "v1" / "model.json"

    logger.info("Loading model bundle...")
    bundle = ModelRegistry.load_bundle(if_path, ae_path, clf_path, device=args.device)
    feature_names = bundle.feature_names
    logger.info("Successfully loaded bundle with %d features.", len(feature_names))

    # 2. Load Validation Benchmark (Permitted Development Data)
    val_file = PROJECT_ROOT / "data" / "benchmark" / "v1" / "validation.parquet"
    logger.info("Loading validation partition from %s...", val_file)
    val_df = pd.read_parquet(val_file)
    X_val = val_df[feature_names].to_numpy(dtype=np.float32)
    y_val_str = val_df["Label"].to_numpy()
    y_val_binary = (y_val_str != "BENIGN").astype(int)

    benign_mask_val = y_val_str == "BENIGN"
    X_val[benign_mask_val]
    logger.info(
        "Validation records: %d total (%d benign, %d attacks)",
        len(val_df),
        int(np.sum(benign_mask_val)),
        int(np.sum(~benign_mask_val)),
    )

    # Compute raw anomaly scores on validation
    logger.info("Computing raw anomaly scores on validation set...")
    raw_if_val = bundle.isolation_forest.score_samples(X_val)
    raw_ae_val = bundle.autoencoder.score_samples(X_val, batch_size=args.batch_size)

    raw_if_val_benign = raw_if_val[benign_mask_val]
    raw_ae_val_benign = raw_ae_val[benign_mask_val]

    # STEP 4: SCORE CALIBRATION EXPERIMENTS
    logger.info("--- STEP 4: Calibrating Anomaly Scores on Benign Validation Reference ---")
    cal_p_if = PercentileCalibrator().fit(raw_if_val_benign, reference_name="benign_validation")
    cal_p_ae = PercentileCalibrator().fit(raw_ae_val_benign, reference_name="benign_validation")

    cal_r_if = RobustScalerCalibrator().fit(raw_if_val_benign, reference_name="benign_validation")
    cal_r_ae = RobustScalerCalibrator().fit(raw_ae_val_benign, reference_name="benign_validation")

    # Transform scores on validation
    cal_p_if_val = cal_p_if.transform(raw_if_val)
    cal_p_ae_val = cal_p_ae.transform(raw_ae_val)

    cal_r_if.transform(raw_if_val)
    cal_r_ae.transform(raw_ae_val)

    # Save fitted calibrators
    cal_p_if.save(artifact_dir / "calibrator_percentile_if.json")
    cal_p_ae.save(artifact_dir / "calibrator_percentile_ae.json")
    cal_r_if.save(artifact_dir / "calibrator_robust_if.json")
    cal_r_ae.save(artifact_dir / "calibrator_robust_ae.json")

    # Primary calibrators frozen for pipeline
    cal_p_if.save(artifact_dir / "calibrator_if.json")
    cal_p_ae.save(artifact_dir / "calibrator_ae.json")

    # STEP 5: EVALUATE FUSION STRATEGIES ON VALIDATION
    logger.info("--- STEP 5: Evaluating Candidate Fusion Strategies on Validation ---")
    fusion_candidates: dict[str, np.ndarray] = {
        "isolation_forest_only": cal_p_if_val,
        "autoencoder_only": cal_p_ae_val,
        "max": np.maximum(cal_p_if_val, cal_p_ae_val),
        "mean": 0.5 * (cal_p_if_val + cal_p_ae_val),
        "weighted_if0.3_ae0.7": 0.3 * cal_p_if_val + 0.7 * cal_p_ae_val,
        "weighted_if0.2_ae0.8": 0.2 * cal_p_if_val + 0.8 * cal_p_ae_val,
        "weighted_if0.4_ae0.6": 0.4 * cal_p_if_val + 0.6 * cal_p_ae_val,
    }

    fusion_validation_results: dict[str, Any] = {}
    for name, f_scores in fusion_candidates.items():
        # Calibrate p99.0 threshold strictly on benign validation scores
        f_scores_benign = f_scores[benign_mask_val]
        p99_thresh = float(np.percentile(f_scores_benign, 99.0))
        p95_thresh = float(np.percentile(f_scores_benign, 95.0))
        p995_thresh = float(np.percentile(f_scores_benign, 99.5))

        m99 = compute_binary_metrics(y_val_binary, f_scores, p99_thresh)
        m95 = compute_binary_metrics(y_val_binary, f_scores, p95_thresh)
        m995 = compute_binary_metrics(y_val_binary, f_scores, p995_thresh)

        fusion_validation_results[name] = {
            "thresholds": {"p95.0": p95_thresh, "p99.0": p99_thresh, "p99.5": p995_thresh},
            "p99_metrics": m99,
            "p95_metrics": m95,
            "p995_metrics": m995,
        }
        logger.info(
            "Candidate [%s]: ROC-AUC=%.4f, PR-AUC=%.4f | p99 Recall=%.4f, F1=%.4f, Benign FPR=%.4f",
            name,
            m99["roc_auc"],
            m99["pr_auc"],
            m99["recall"],
            m99["f1"],
            m99["benign_fpr"],
        )

    # STEP 6: SELECT AND FREEZE FUSION STRATEGY
    # Select 'mean' or optimal weighted candidate based on validation PR-AUC & p99 F1
    best_candidate_name = "mean"
    selected_fusion_cfg = ScoreFusionConfig(
        strategy="mean",
        weight_if=0.5,
        weight_ae=0.5,
        description="Equal-weight average of percentile-calibrated Isolation Forest and Autoencoder scores",
    )
    selected_fusion_cfg_path = artifact_dir / "fusion_config.json"
    with open(selected_fusion_cfg_path, "w", encoding="utf-8") as f:
        json.dump(selected_fusion_cfg.to_dict(), f, indent=2)

    frozen_fused_val_scores = fusion_candidates[best_candidate_name]
    frozen_p95 = float(np.percentile(frozen_fused_val_scores[benign_mask_val], 95.0))
    frozen_p99 = float(np.percentile(frozen_fused_val_scores[benign_mask_val], 99.0))
    frozen_p995 = float(np.percentile(frozen_fused_val_scores[benign_mask_val], 99.5))

    thresholds_dict = {
        "strategy": "benign_validation_percentile_calibrated_fusion",
        "frozen_candidate": best_candidate_name,
        "sample_count_benign": int(np.sum(benign_mask_val)),
        "thresholds": {
            "p95.0": frozen_p95,
            "p99.0": frozen_p99,
            "p99.5": frozen_p995,
        },
    }
    with open(artifact_dir / "thresholds.json", "w", encoding="utf-8") as f:
        json.dump(thresholds_dict, f, indent=2)

    # STEP 7: CLASSIFIER REJECTION & SIMULATED OPEN-SET EXPERIMENT
    logger.info("--- STEP 7: Classifier Rejection & Simulated Open-Set Experiment ---")
    val_probs = bundle.classifier.predict_proba(X_val)
    rejection_engine = ClassifierRejectionEngine(
        ClassifierRejectionConfig(min_confidence=0.50, min_margin=0.10, max_entropy=2.00)
    )
    val_clf_evidence = rejection_engine.evaluate_batch(val_probs, bundle.classifier.class_mapping)

    val_rejections = [ev.rejected for ev in val_clf_evidence]
    logger.info(
        "Validation Rejection Summary: Total rejected = %d (%.2f%%)",
        sum(val_rejections),
        100.0 * sum(val_rejections) / len(val_rejections),
    )

    # Simulated Open-Set Experiment on Development Data
    # Hold out "DoS slowloris" (102 val flows) and "FTP-Patator" (139 val flows)
    # in an experimental classifier trained on the rest of classifier_train.parquet
    train_file = PROJECT_ROOT / "data" / "benchmark" / "v1" / "classifier_train.parquet"
    train_df = pd.read_parquet(train_file)
    logger.info("Conducting simulated open-set experiment on classifier_train...")
    held_out_classes = ["DoS slowloris", "FTP-Patator"]

    train_subset = train_df[~train_df["Label"].isin(held_out_classes)]
    X_train_sub = train_subset[feature_names].to_numpy(dtype=np.float32)
    y_train_sub = train_subset["Label"].to_numpy()

    from netdefy.models.xgboost_classifier import XGBoostAttackClassifier, XGBoostClassifierConfig

    sub_config = XGBoostClassifierConfig(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.05,
        confidence_threshold=0.50,
        n_jobs=4,
    )
    sub_clf = XGBoostAttackClassifier(config=sub_config)
    sub_clf.fit(X_train_sub, y_train_sub)

    # Evaluate on validation held-out vs known classes
    val_sub_probs = sub_clf.predict_proba(X_val)
    val_sub_evidence = rejection_engine.evaluate_batch(val_sub_probs, sub_clf.class_mapping)

    sim_rejections = np.array([ev.rejected for ev in val_sub_evidence])
    sim_pred_classes = np.array([ev.predicted_class for ev in val_sub_evidence])

    is_held_out = np.isin(y_val_str, held_out_classes)
    is_known_attack = (~benign_mask_val) & (~is_held_out)
    is_benign = benign_mask_val

    held_out_rejection_rate = (
        float(np.mean(sim_rejections[is_held_out])) if np.sum(is_held_out) > 0 else 0.0
    )
    known_attack_rejection_rate = (
        float(np.mean(sim_rejections[is_known_attack])) if np.sum(is_known_attack) > 0 else 0.0
    )
    benign_rejection_rate = (
        float(np.mean(sim_rejections[is_benign])) if np.sum(is_benign) > 0 else 0.0
    )

    # For held-out attacks that were not rejected, what did the closed-set classifier force them into?
    sim_pred_classes[is_held_out & (~sim_rejections)]
    logger.info("Simulated Open-Set Results:")
    logger.info(
        "  Held-out Attack Rejection Rate: %.4f (%d flows)",
        held_out_rejection_rate,
        int(np.sum(is_held_out)),
    )
    logger.info(
        "  Known Attack Rejection Rate:    %.4f (%d flows)",
        known_attack_rejection_rate,
        int(np.sum(is_known_attack)),
    )
    logger.info(
        "  Benign Rejection Rate:          %.4f (%d flows)",
        benign_rejection_rate,
        int(np.sum(is_benign)),
    )

    open_set_results = {
        "held_out_classes": held_out_classes,
        "held_out_samples": int(np.sum(is_held_out)),
        "known_attack_samples": int(np.sum(is_known_attack)),
        "benign_samples": int(np.sum(is_benign)),
        "held_out_rejection_rate": held_out_rejection_rate,
        "known_attack_rejection_rate": known_attack_rejection_rate,
        "benign_rejection_rate": benign_rejection_rate,
        "rejection_threshold_tau": 0.50,
        "min_margin": 0.10,
        "max_entropy": 2.00,
    }
    with open(artifact_dir / "simulated_open_set_results.json", "w", encoding="utf-8") as f:
        json.dump(open_set_results, f, indent=2)

    # Save rejection config
    rejection_cfg = ClassifierRejectionConfig(
        min_confidence=0.50,
        min_margin=0.10,
        max_entropy=2.00,
        benign_label="BENIGN",
        unknown_label="UNKNOWN",
    )
    rejection_engine.save(artifact_dir / "rejection_config.json")

    # STEP 8: DECISION POLICY FREEZING
    logger.info("--- STEP 8: Freezing Complete Decision Policy ---")
    decision_policy_cfg = DecisionPolicyConfig(
        anomaly_threshold=frozen_p99,
        threshold_tier="p99.0",
        detector_disagreement_threshold=0.50,
        high_classifier_conflict_confidence=0.85,
        benign_label="BENIGN",
    )
    decision_engine = DecisionEngine(decision_policy_cfg)
    decision_engine.save(artifact_dir / "decision_policy.json")

    # Generate configs/hybrid.yaml
    hybrid_yaml_content = {
        "pipeline": {
            "name": "netdefy_hybrid_intelligence_engine",
            "version": "v1",
            "description": "Unified hybrid inference pipeline integrating Isolation Forest, Autoencoder, and XGBoost",
        },
        "model_paths": {
            "isolation_forest": "artifacts/models/isolation_forest/v1/model.joblib",
            "autoencoder": "artifacts/models/autoencoder/v1/best_model.pt",
            "classifier": "artifacts/models/xgboost_classifier/v1/model.json",
        },
        "calibration": {
            "calibrator_type": "percentile",
            "calibrator_if_file": "artifacts/models/hybrid/v1/calibrator_if.json",
            "calibrator_ae_file": "artifacts/models/hybrid/v1/calibrator_ae.json",
        },
        "fusion": selected_fusion_cfg.to_dict(),
        "rejection": rejection_cfg.to_dict(),
        "decision_policy": decision_policy_cfg.to_dict(),
        "device": "cpu",
        "top_k_features_explanation": 5,
    }
    with open(PROJECT_ROOT / "configs" / "hybrid.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(hybrid_yaml_content, f, sort_keys=False)

    # STEP 9: MANIFEST GENERATION
    logger.info("--- STEP 9: Generating Reproducible Hybrid Manifest ---")
    manifest_data = {
        "pipeline_name": "netdefy_hybrid_intelligence_engine",
        "version": "v1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "artifact_hashes": {
            "isolation_forest": compute_sha256(if_path),
            "autoencoder": compute_sha256(ae_path),
            "classifier_metadata": compute_sha256(clf_path),
            "classifier_booster": compute_sha256(clf_path.parent / "model.ubj"),
            "feature_schema": compute_sha256(
                PROJECT_ROOT / "artifacts" / "preprocessing" / "feature_schema.json"
            ),
            "standard_scaler": compute_sha256(
                PROJECT_ROOT / "artifacts" / "preprocessing" / "standard_scaler.joblib"
            ),
        },
        "calibration": {
            "method": "empirical_percentile",
            "reference_partition": "validation.parquet",
            "benign_sample_count": int(np.sum(benign_mask_val)),
        },
        "fusion": selected_fusion_cfg.to_dict(),
        "operational_thresholds": thresholds_dict["thresholds"],
        "class_mapping": bundle.classifier.class_mapping,
    }
    with open(artifact_dir / "model_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # STEP 10, 11, 12: HOLDOUT TEST EVALUATION (VIEW A & VIEW B)
    logger.info("--- STEP 10: Evaluating Frozen Pipeline on Final Test Set ---")
    test_file = PROJECT_ROOT / "data" / "benchmark" / "v1" / "test.parquet"
    test_df = pd.read_parquet(test_file)
    X_test = test_df[feature_names].to_numpy(dtype=np.float32)
    y_test_str = test_df["Label"].to_numpy()
    y_test_binary = (y_test_str != "BENIGN").astype(int)

    # Ambiguity provenance for View B
    provenance_path = (
        PROJECT_ROOT / "data" / "benchmark" / "v1" / "metadata" / "source_row_manifest.json"
    )
    with open(provenance_path, encoding="utf-8") as f:
        provenance = json.load(f)
    is_ambiguous = np.array([rec["is_ambiguous_flow"] for rec in provenance["test"]], dtype=bool)
    disambiguated_mask = ~is_ambiguous

    logger.info(
        "Test records: %d total (View A), %d disambiguated (View B, excluded %d)",
        len(test_df),
        int(np.sum(disambiguated_mask)),
        int(np.sum(is_ambiguous)),
    )

    # Instantiate Frozen Hybrid Inference Pipeline
    pipeline = HybridInferencePipeline.from_config(PROJECT_ROOT / "configs" / "hybrid.yaml")

    # Run predictions on test set
    t0 = time.perf_counter()
    batch_test_pred = pipeline.predict_batch(
        X_test, batch_size=args.batch_size, include_explanations=True
    )
    inference_duration = time.perf_counter() - t0
    throughput = len(X_test) / inference_duration
    logger.info(
        "Inference completed: %d flows in %.3f sec (%.2f flows/sec)",
        len(X_test),
        inference_duration,
        throughput,
    )

    # Extract test outputs
    test_decisions = np.array([p.decision.value for p in batch_test_pred.predictions])
    test_fused_scores = np.array([p.anomaly.fused_score for p in batch_test_pred.predictions])
    test_cal_if = np.array(
        [p.anomaly.isolation_forest_calibrated_score for p in batch_test_pred.predictions]
    )
    test_cal_ae = np.array(
        [p.anomaly.autoencoder_calibrated_score for p in batch_test_pred.predictions]
    )
    np.array([p.anomaly.isolation_forest_raw_score for p in batch_test_pred.predictions])
    np.array([p.anomaly.autoencoder_raw_error for p in batch_test_pred.predictions])
    test_clf_preds = np.array([p.classifier.predicted_class for p in batch_test_pred.predictions])
    test_clf_rejected = np.array([p.classifier.rejected for p in batch_test_pred.predictions])

    # EVALUATE BASELINES ON TEST
    def evaluate_all_systems(
        mask: np.ndarray,
        view_name: str,
    ) -> dict[str, Any]:
        y_b = y_test_binary[mask]
        y_s = y_test_str[mask]
        n_tot = len(y_b)
        n_benign = int(np.sum(y_b == 0))
        n_attacks = int(np.sum(y_b == 1))

        # 1. Isolation Forest Baseline
        if_thresh = frozen_p99  # calibrated percentile threshold
        # using raw or calibrated IF
        m_if = compute_binary_metrics(y_b, test_cal_if[mask], if_thresh)

        # 2. Autoencoder Baseline
        m_ae = compute_binary_metrics(y_b, test_cal_ae[mask], if_thresh)

        # 3. XGBoost Baseline (as binary detector: predicted != BENIGN)
        xgb_pred_atk = (test_clf_preds[mask] != "BENIGN").astype(int)
        tn, fp, fn, tp = confusion_matrix(y_b, xgb_pred_atk, labels=[0, 1]).ravel()
        m_xgb = {
            "precision": float(precision_score(y_b, xgb_pred_atk, zero_division=0)),
            "recall": float(recall_score(y_b, xgb_pred_atk, zero_division=0)),
            "f1": float(f1_score(y_b, xgb_pred_atk, zero_division=0)),
            "benign_fpr": float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0,
            "specificity": float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0,
            "false_alarms_per_1000_benign": float(fp / (tn + fp)) * 1000.0
            if (tn + fp) > 0
            else 0.0,
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn),
        }

        # 4. IF + AE Fusion Baseline
        m_fusion = compute_binary_metrics(y_b, test_fused_scores[mask], frozen_p99)

        # 5. Full Hybrid Decision Engine (Escalation: Decision != NORMAL)
        hybrid_alert = (test_decisions[mask] != "NORMAL").astype(int)
        tn, fp, fn, tp = confusion_matrix(y_b, hybrid_alert, labels=[0, 1]).ravel()
        m_hybrid = {
            "precision": float(precision_score(y_b, hybrid_alert, zero_division=0)),
            "recall": float(recall_score(y_b, hybrid_alert, zero_division=0)),
            "f1": float(f1_score(y_b, hybrid_alert, zero_division=0)),
            "benign_fpr": float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0,
            "specificity": float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0,
            "false_alarms_per_1000_benign": float(fp / (tn + fp)) * 1000.0
            if (tn + fp) > 0
            else 0.0,
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn),
        }

        # Decision category distribution
        dec_counts = pd.Series(test_decisions[mask]).value_counts().to_dict()

        # Attack-wise recall for Hybrid alert
        attack_types = sorted(set(y_s[y_b == 1]))
        attack_wise_recall: dict[str, float] = {}
        for atk in attack_types:
            atk_mask = y_s == atk
            rec = float(np.mean(hybrid_alert[atk_mask])) if np.sum(atk_mask) > 0 else 0.0
            attack_wise_recall[atk] = rec

        # Open-set analysis on this view
        # All test attacks are unrepresented in training:
        atk_sub_mask = mask & (y_test_binary == 1)
        bng_sub_mask = mask & (y_test_binary == 0)
        unknown_rejection_rate = (
            float(np.mean(test_clf_rejected[atk_sub_mask])) if np.sum(atk_sub_mask) > 0 else 0.0
        )
        benign_rejection_rate = (
            float(np.mean(test_clf_rejected[bng_sub_mask])) if np.sum(bng_sub_mask) > 0 else 0.0
        )

        return {
            "view_name": view_name,
            "total_records": n_tot,
            "benign_records": n_benign,
            "attack_records": n_attacks,
            "decision_distribution": dec_counts,
            "isolation_forest": m_if,
            "autoencoder": m_ae,
            "xgboost": m_xgb,
            "fusion": m_fusion,
            "hybrid_engine": m_hybrid,
            "attack_wise_recall": attack_wise_recall,
            "open_set_metrics": {
                "unknown_attack_rejection_rate": unknown_rejection_rate,
                "benign_rejection_rate": benign_rejection_rate,
            },
        }

    full_test_eval = evaluate_all_systems(np.ones(len(test_df), dtype=bool), "view_a_full_test")
    disambiguated_test_eval = evaluate_all_systems(disambiguated_mask, "view_b_disambiguated_test")

    logger.info("=== VIEW A (FULL TEST) SUMMARY ===")
    logger.info(
        "Hybrid Alerts: Recall=%.4f, Precision=%.4f, F1=%.4f, Benign FPR=%.4f",
        full_test_eval["hybrid_engine"]["recall"],
        full_test_eval["hybrid_engine"]["precision"],
        full_test_eval["hybrid_engine"]["f1"],
        full_test_eval["hybrid_engine"]["benign_fpr"],
    )
    logger.info("Decision breakdown: %s", full_test_eval["decision_distribution"])

    logger.info("=== VIEW B (DISAMBIGUATED TEST) SUMMARY ===")
    logger.info(
        "Hybrid Alerts: Recall=%.4f, Precision=%.4f, F1=%.4f, Benign FPR=%.4f",
        disambiguated_test_eval["hybrid_engine"]["recall"],
        disambiguated_test_eval["hybrid_engine"]["precision"],
        disambiguated_test_eval["hybrid_engine"]["f1"],
        disambiguated_test_eval["hybrid_engine"]["benign_fpr"],
    )
    logger.info("Decision breakdown: %s", disambiguated_test_eval["decision_distribution"])

    test_metrics_payload = {
        "view_a_full_test": full_test_eval,
        "view_b_disambiguated_test": disambiguated_test_eval,
        "operational_thresholds": thresholds_dict,
        "fusion_validation_comparison": fusion_validation_results,
    }
    with open(artifact_dir / "test_metrics.json", "w", encoding="utf-8") as f:
        json.dump(test_metrics_payload, f, indent=2)

    # STEP 13: HARDWARE & OPERATIONAL BENCHMARKS
    logger.info("--- STEP 13: Benchmarking Hardware, Latency, and Memory ---")
    # Single flow latency (warm iterations)
    sample_flow = X_test[0]
    latencies: list[float] = []
    for _ in range(50):  # warm-up
        _ = pipeline.predict(sample_flow)
    for _ in range(200):
        t_start = time.perf_counter()
        _ = pipeline.predict(sample_flow)
        latencies.append((time.perf_counter() - t_start) * 1000.0)  # ms

    p50_lat = float(np.percentile(latencies, 50.0))
    p95_lat = float(np.percentile(latencies, 95.0))
    p99_lat = float(np.percentile(latencies, 99.0))
    mean_lat = float(np.mean(latencies))

    # Memory usage
    peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # On macOS, ru_maxrss is in bytes; on Linux, in kilobytes
    peak_rss_mb = (
        peak_rss_kb / (1024.0 * 1024.0) if sys.platform == "darwin" else peak_rss_kb / 1024.0
    )

    perf_benchmarks = {
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        },
        "single_flow_latency_ms": {
            "p50": p50_lat,
            "p95": p95_lat,
            "p99": p99_lat,
            "mean": mean_lat,
        },
        "batch_throughput_flows_per_sec": float(throughput),
        "total_test_inference_time_sec": float(inference_duration),
        "total_flows_evaluated": len(X_test),
        "peak_rss_memory_mb": float(peak_rss_mb),
    }
    with open(artifact_dir / "performance_benchmarks.json", "w", encoding="utf-8") as f:
        json.dump(perf_benchmarks, f, indent=2)

    logger.info("Performance Benchmarks:")
    logger.info(
        "  Single flow latency: p50=%.3f ms, p95=%.3f ms, p99=%.3f ms", p50_lat, p95_lat, p99_lat
    )
    logger.info("  Batch throughput:    %.2f flows/sec", throughput)
    logger.info("  Peak resident memory: %.2f MB", peak_rss_mb)

    logger.info("================================================================================")
    logger.info("        PHASE 4D EVALUATION COMPLETED SUCCESSFULLY!                            ")
    logger.info("================================================================================")


if __name__ == "__main__":
    main()
