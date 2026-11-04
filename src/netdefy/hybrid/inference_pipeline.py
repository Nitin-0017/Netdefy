"""NETDEFY — Hybrid Inference Pipeline.

Unified, production-grade inference orchestration executing Isolation Forest,
Deep Autoencoder, and XGBoost classifier with score calibration, fusion,
confidence rejection, and explainable decision attribution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import yaml

from netdefy.hybrid.classifier_rejection import (
    ClassifierRejectionConfig,
    ClassifierRejectionEngine,
)
from netdefy.hybrid.decision_engine import DecisionEngine, DecisionPolicyConfig
from netdefy.hybrid.explanation import ExplanationGenerator
from netdefy.hybrid.model_registry import ModelRegistry
from netdefy.hybrid.schemas import (
    AnomalyEvidence,
    DecisionCategory,
    HybridBatchPrediction,
    HybridFlowPrediction,
)
from netdefy.hybrid.score_calibration import (
    BaseScoreCalibrator,
    PercentileCalibrator,
    RobustScalerCalibrator,
)
from netdefy.hybrid.score_fusion import ScoreFusionConfig, ScoreFusionEngine

logger = logging.getLogger(__name__)


class HybridInferencePipeline:
    """Production inference pipeline integrating the NETDEFY hybrid multi-model architecture."""

    def __init__(
        self,
        isolation_forest_path: Path | str,
        autoencoder_path: Path | str,
        classifier_path: Path | str,
        calibrator_if: BaseScoreCalibrator,
        calibrator_ae: BaseScoreCalibrator,
        fusion_engine: ScoreFusionEngine,
        rejection_engine: ClassifierRejectionEngine,
        decision_engine: DecisionEngine,
        device: torch.device | str = "cpu",
        top_k_features_explanation: int = 5,
    ) -> None:
        self.device = torch.device(device) if isinstance(device, str) else device
        self.bundle = ModelRegistry.load_bundle(
            isolation_forest_path=isolation_forest_path,
            autoencoder_path=autoencoder_path,
            classifier_path=classifier_path,
            device=self.device,
        )
        self.feature_names = self.bundle.feature_names
        self.calibrator_if = calibrator_if
        self.calibrator_ae = calibrator_ae
        self.fusion_engine = fusion_engine
        self.rejection_engine = rejection_engine
        self.decision_engine = decision_engine
        self.explanation_generator = ExplanationGenerator(top_k_features=top_k_features_explanation)

        self.model_versions = {
            "isolation_forest": "v1",
            "autoencoder": "v1",
            "xgboost_classifier": "v1",
            "hybrid_engine": "v1",
        }

    @classmethod
    def from_config(
        cls, config_path_or_dict: Path | str | dict[str, Any]
    ) -> HybridInferencePipeline:
        """Instantiate pipeline from a configuration YAML file or dictionary."""
        if isinstance(config_path_or_dict, (str, Path)):
            cfg_path = Path(config_path_or_dict).resolve()
            with open(cfg_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            base_dir = cfg_path.parent.parent
        else:
            cfg = config_path_or_dict
            base_dir = Path.cwd()

        paths = cfg.get("model_paths", {})
        if_path = base_dir / paths.get(
            "isolation_forest", "artifacts/models/isolation_forest/v1/model.joblib"
        )
        ae_path = base_dir / paths.get(
            "autoencoder", "artifacts/models/autoencoder/v1/best_model.pt"
        )
        clf_path = base_dir / paths.get(
            "classifier", "artifacts/models/xgboost_classifier/v1/model.json"
        )

        cal_cfg = cfg.get("calibration", {})
        cal_type = cal_cfg.get("calibrator_type", "percentile")

        # Load or instantiate calibrators
        if "calibrator_if_file" in cal_cfg and (base_dir / cal_cfg["calibrator_if_file"]).exists():
            calibrator_if = BaseScoreCalibrator.load(base_dir / cal_cfg["calibrator_if_file"])
        else:
            calibrator_if = (
                PercentileCalibrator() if cal_type == "percentile" else RobustScalerCalibrator()
            )

        if "calibrator_ae_file" in cal_cfg and (base_dir / cal_cfg["calibrator_ae_file"]).exists():
            calibrator_ae = BaseScoreCalibrator.load(base_dir / cal_cfg["calibrator_ae_file"])
        else:
            calibrator_ae = (
                PercentileCalibrator() if cal_type == "percentile" else RobustScalerCalibrator()
            )

        # Fusion engine
        fusion_cfg_dict = cfg.get("fusion", {})
        fusion_cfg = ScoreFusionConfig.from_dict(fusion_cfg_dict)
        fusion_engine = ScoreFusionEngine(fusion_cfg)

        # Rejection engine
        rejection_cfg_dict = cfg.get("rejection", {})
        rejection_cfg = ClassifierRejectionConfig.from_dict(rejection_cfg_dict)
        rejection_engine = ClassifierRejectionEngine(rejection_cfg)

        # Decision engine
        decision_cfg_dict = cfg.get("decision_policy", {})
        decision_cfg = DecisionPolicyConfig.from_dict(decision_cfg_dict)
        decision_engine = DecisionEngine(decision_cfg)

        device = cfg.get("device", "cpu")
        top_k = int(cfg.get("top_k_features_explanation", 5))

        return cls(
            isolation_forest_path=if_path,
            autoencoder_path=ae_path,
            classifier_path=clf_path,
            calibrator_if=calibrator_if,
            calibrator_ae=calibrator_ae,
            fusion_engine=fusion_engine,
            rejection_engine=rejection_engine,
            decision_engine=decision_engine,
            device=device,
            top_k_features_explanation=top_k,
        )

    def _sanitize_input(
        self, X: pd.DataFrame | pd.Series | dict[str, Any] | np.ndarray
    ) -> np.ndarray:
        """Convert input data structure into a validated 2D float32 numpy array."""
        if isinstance(X, dict):
            missing = [f for f in self.feature_names if f not in X]
            if missing:
                raise ValueError(
                    f"Input dictionary missing {len(missing)} required features: {missing[:5]}..."
                )
            arr = np.array([[float(X[f]) for f in self.feature_names]], dtype=np.float32)
        elif isinstance(X, pd.Series):
            missing = [f for f in self.feature_names if f not in X.index]
            if missing:
                raise ValueError(
                    f"Input Series missing {len(missing)} required features: {missing[:5]}..."
                )
            arr = np.array([X[self.feature_names].to_numpy(dtype=np.float32)], dtype=np.float32)
        elif isinstance(X, pd.DataFrame):
            missing = [f for f in self.feature_names if f not in X.columns]
            if missing:
                raise ValueError(
                    f"Input DataFrame missing {len(missing)} required features: {missing[:5]}..."
                )
            arr = np.ascontiguousarray(X[self.feature_names].to_numpy(dtype=np.float32))
        elif isinstance(X, np.ndarray):
            if X.ndim == 1:
                arr = np.array([X], dtype=np.float32)
            elif X.ndim == 2:
                arr = np.ascontiguousarray(X, dtype=np.float32)
            else:
                raise ValueError(f"Unsupported array dimension: {X.ndim} (must be 1D or 2D)")
            if arr.shape[1] != len(self.feature_names):
                raise ValueError(
                    f"Feature count mismatch: expected {len(self.feature_names)} features, got {arr.shape[1]}"
                )
        else:
            raise TypeError(f"Unsupported input type for inference: {type(X)}")

        if np.isnan(arr).any() or np.isinf(arr).any():
            raise ValueError("Input feature matrix contains NaN or Inf values!")

        return arr

    def predict(
        self,
        flow: pd.Series | dict[str, Any] | np.ndarray,
        flow_id: int | str | None = None,
    ) -> HybridFlowPrediction:
        """Execute complete hybrid inference on a single network traffic flow."""
        arr = self._sanitize_input(flow)
        batch_result = self.predict_batch(
            arr, batch_size=1, flow_ids=[flow_id] if flow_id is not None else None
        )
        return batch_result.predictions[0]

    def predict_batch(
        self,
        flows: pd.DataFrame | np.ndarray,
        batch_size: int = 1024,
        flow_ids: list[int | str | None] | None = None,
        include_explanations: bool = True,
    ) -> HybridBatchPrediction:
        """Execute vectorized hybrid inference across a batch of network flows."""
        X_arr = self._sanitize_input(flows)
        n_samples = len(X_arr)

        if n_samples == 0:
            return HybridBatchPrediction(
                predictions=[],
                total_flows=0,
                decision_counts={},
                anomaly_count=0,
                rejection_count=0,
            )

        # 1. Isolation Forest Scoring
        raw_if = self.bundle.isolation_forest.score_samples(X_arr)
        cal_if = self.calibrator_if.transform(raw_if)

        # 2. Deep Autoencoder Scoring & Reconstruction
        raw_ae = self.bundle.autoencoder.score_samples(X_arr, batch_size=batch_size)
        cal_ae = self.calibrator_ae.transform(raw_ae)

        # Optional Autoencoder forward pass for feature-level attribution
        rec_arr: np.ndarray | None = None
        if include_explanations:
            rec_list: list[np.ndarray] = []
            self.bundle.autoencoder.model.eval()
            with torch.no_grad():
                for i in range(0, n_samples, batch_size):
                    chunk = torch.tensor(
                        X_arr[i : i + batch_size],
                        dtype=torch.float32,
                        device=self.device,
                    )
                    chunk_rec = self.bundle.autoencoder.model.forward(chunk)
                    rec_list.append(chunk_rec.cpu().numpy().astype(np.float32))
            rec_arr = np.concatenate(rec_list, axis=0) if rec_list else None

        # 3. Supervised Classification
        clf_probs = self.bundle.classifier.predict_proba(X_arr)
        clf_evidence_list = self.rejection_engine.evaluate_batch(
            clf_probs, self.bundle.classifier.class_mapping
        )

        # 4. Score Fusion
        fused_scores = self.fusion_engine.fuse(cal_if, cal_ae)

        # 5. Decision Policy Execution
        op_thresh = self.decision_engine.config.anomaly_threshold
        thresh_tier = self.decision_engine.config.threshold_tier

        predictions: list[HybridFlowPrediction] = []
        decision_counts: dict[str, int] = {cat.value: 0 for cat in DecisionCategory}
        anomaly_count = 0
        rejection_count = 0

        for i in range(n_samples):
            f_score = float(fused_scores[i])
            is_anom = f_score >= op_thresh
            if is_anom:
                anomaly_count += 1

            anom_ev = AnomalyEvidence(
                isolation_forest_raw_score=float(raw_if[i]),
                isolation_forest_calibrated_score=float(cal_if[i]),
                autoencoder_raw_error=float(raw_ae[i]),
                autoencoder_calibrated_score=float(cal_ae[i]),
                fused_score=f_score,
                threshold=op_thresh,
                is_anomaly=is_anom,
                threshold_tier=thresh_tier,
            )

            clf_ev = clf_evidence_list[i]
            if clf_ev.rejected:
                rejection_count += 1

            dec_cat, dec_reason = self.decision_engine.evaluate_flow(
                anomaly_evidence=anom_ev,
                classifier_evidence=clf_ev,
            )
            decision_counts[dec_cat.value] += 1

            flow_x = X_arr[i] if include_explanations else None
            flow_rec = rec_arr[i] if rec_arr is not None else None

            explanation = self.explanation_generator.explain(
                decision=dec_cat,
                decision_reason=dec_reason,
                anomaly_evidence=anom_ev,
                classifier_evidence=clf_ev,
                feature_names=self.feature_names if include_explanations else None,
                x_raw_or_scaled=flow_x,
                x_reconstructed=flow_rec,
            )

            fid = flow_ids[i] if flow_ids is not None and i < len(flow_ids) else i
            pred_record = HybridFlowPrediction(
                flow_id=fid,
                decision=dec_cat,
                decision_reason=dec_reason,
                anomaly=anom_ev,
                classifier=clf_ev,
                explanation=explanation,
                model_versions=self.model_versions,
            )
            predictions.append(pred_record)

        return HybridBatchPrediction(
            predictions=predictions,
            total_flows=n_samples,
            decision_counts=decision_counts,
            anomaly_count=anomaly_count,
            rejection_count=rejection_count,
        )
