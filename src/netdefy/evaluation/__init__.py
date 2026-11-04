"""Evaluation metrics, threshold calibration, and error analysis for NETDEFY."""

from netdefy.evaluation.autoencoder_evaluator import (
    AutoencoderEvaluationBundle,
    AutoencoderEvaluator,
)
from netdefy.evaluation.classification_error_analysis import (
    analyze_ambiguity_classification_impact,
    analyze_confidence_rejection_curve,
    analyze_confused_classes,
)
from netdefy.evaluation.classification_metrics import (
    MulticlassClassificationReport,
    evaluate_multiclass_classifier,
)
from netdefy.evaluation.classifier_evaluator import (
    ClassifierEvaluationBundle,
    ClassifierEvaluator,
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
    "ClassifierEvaluationBundle",
    "ClassifierEvaluator",
    "MulticlassClassificationReport",
    "ThresholdCalibrationResult",
    "ThresholdEntry",
    "analyze_ambiguity_classification_impact",
    "analyze_ambiguity_impact",
    "analyze_confidence_rejection_curve",
    "analyze_confused_classes",
    "analyze_false_negatives",
    "analyze_false_positives",
    "compute_attack_wise_recall",
    "compute_binary_metrics",
    "evaluate_anomaly_detector",
    "evaluate_multiclass_classifier",
]
