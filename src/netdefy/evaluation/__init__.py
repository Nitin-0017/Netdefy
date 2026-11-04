"""Evaluation metrics, threshold calibration, and error analysis for NETDEFY."""

from netdefy.evaluation.autoencoder_evaluator import (
    AutoencoderEvaluationBundle,
    AutoencoderEvaluator,
)
from netdefy.evaluation.error_analysis import (
    analyze_ambiguity_impact,
    analyze_false_negatives,
    analyze_false_positives,
)
from netdefy.evaluation.metrics import (
    AnomalyEvaluationReport,
    BinaryEvaluationMetrics,
    compute_attack_wise_recall,
    compute_binary_metrics,
    evaluate_anomaly_detector,
)
from netdefy.evaluation.thresholds import (
    BenignThresholdCalibrator,
    ThresholdCalibrationResult,
    ThresholdEntry,
)

__all__ = [
    "AnomalyEvaluationReport",
    "AutoencoderEvaluationBundle",
    "AutoencoderEvaluator",
    "BenignThresholdCalibrator",
    "BinaryEvaluationMetrics",
    "ThresholdCalibrationResult",
    "ThresholdEntry",
    "analyze_ambiguity_impact",
    "analyze_false_negatives",
    "analyze_false_positives",
    "compute_attack_wise_recall",
    "compute_binary_metrics",
    "evaluate_anomaly_detector",
]
