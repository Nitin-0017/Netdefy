"""NETDEFY — Phase 4D: Hybrid Intelligence & Decision Engine.

Provides unified inference, calibrated multi-detector score fusion,
supervised open-set rejection, and transparent threat attribution.
"""

from __future__ import annotations

from netdefy.hybrid.classifier_rejection import (
    ClassifierRejectionConfig,
    ClassifierRejectionEngine,
)
from netdefy.hybrid.decision_engine import DecisionEngine, DecisionPolicyConfig
from netdefy.hybrid.explanation import ExplanationGenerator
from netdefy.hybrid.inference_pipeline import HybridInferencePipeline
from netdefy.hybrid.model_registry import ModelBundle, ModelRegistry
from netdefy.hybrid.schemas import (
    AnomalyEvidence,
    ClassifierEvidence,
    DecisionCategory,
    FeatureAttribution,
    FlowExplanation,
    HybridBatchPrediction,
    HybridFlowPrediction,
)
from netdefy.hybrid.score_calibration import (
    BaseScoreCalibrator,
    PercentileCalibrator,
    RobustScalerCalibrator,
)
from netdefy.hybrid.score_fusion import (
    FusionStrategyType,
    ScoreFusionConfig,
    ScoreFusionEngine,
)

__all__ = [
    "AnomalyEvidence",
    "BaseScoreCalibrator",
    "ClassifierEvidence",
    "ClassifierRejectionConfig",
    "ClassifierRejectionEngine",
    "DecisionCategory",
    "DecisionEngine",
    "DecisionPolicyConfig",
    "ExplanationGenerator",
    "FeatureAttribution",
    "FlowExplanation",
    "FusionStrategyType",
    "HybridBatchPrediction",
    "HybridFlowPrediction",
    "HybridInferencePipeline",
    "ModelBundle",
    "ModelRegistry",
    "PercentileCalibrator",
    "RobustScalerCalibrator",
    "ScoreFusionConfig",
    "ScoreFusionEngine",
]
