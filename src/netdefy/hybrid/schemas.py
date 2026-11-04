"""NETDEFY — Hybrid Intelligence & Decision Engine Schemas.

Defines strongly-typed data contracts, decision categories, evidence structures,
and prediction schemas for unified inference and reporting.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class DecisionCategory(StrEnum):
    """Unified threat intelligence decision classification."""

    NORMAL = "NORMAL"
    SUSPICIOUS_KNOWN = "SUSPICIOUS_KNOWN"
    SUSPICIOUS_UNKNOWN = "SUSPICIOUS_UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class AnomalyEvidence:
    """Quantitative evidence from unsupervised anomaly detection components."""

    isolation_forest_raw_score: float
    isolation_forest_calibrated_score: float
    autoencoder_raw_error: float
    autoencoder_calibrated_score: float
    fused_score: float
    threshold: float
    is_anomaly: bool
    threshold_tier: str = "p99.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClassifierEvidence:
    """Quantitative evidence from supervised attack classification components."""

    predicted_class: str
    top_probability: float
    second_probability: float
    probability_margin: float
    entropy: float
    rejected: bool
    rejection_reason: str | None
    class_probabilities: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeatureAttribution:
    """Feature-level attribution for high reconstruction error."""

    feature_name: str
    reconstruction_error: float
    input_value: float
    reconstructed_value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FlowExplanation:
    """Interpretable diagnostic explanation supporting a decision."""

    decision: DecisionCategory
    decision_reason: str
    evidence_summary: list[str] = field(default_factory=list)
    top_contributing_features: list[FeatureAttribution] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "decision_reason": self.decision_reason,
            "evidence_summary": self.evidence_summary,
            "top_contributing_features": [f.to_dict() for f in self.top_contributing_features],
        }


@dataclass(frozen=True)
class HybridFlowPrediction:
    """Complete prediction and evidence record for a single network traffic flow."""

    decision: DecisionCategory
    decision_reason: str
    anomaly: AnomalyEvidence
    classifier: ClassifierEvidence
    explanation: FlowExplanation
    model_versions: dict[str, str] = field(default_factory=dict)
    flow_id: int | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "decision": self.decision.value,
            "decision_reason": self.decision_reason,
            "anomaly": self.anomaly.to_dict(),
            "classifier": self.classifier.to_dict(),
            "explanation": self.explanation.to_dict(),
            "model_versions": self.model_versions,
        }


@dataclass(frozen=True)
class HybridBatchPrediction:
    """Aggregated prediction output across a batch of network traffic flows."""

    predictions: list[HybridFlowPrediction]
    total_flows: int
    decision_counts: dict[str, int]
    anomaly_count: int
    rejection_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_flows": self.total_flows,
            "decision_counts": self.decision_counts,
            "anomaly_count": self.anomaly_count,
            "rejection_count": self.rejection_count,
            "predictions": [p.to_dict() for p in self.predictions],
        }
