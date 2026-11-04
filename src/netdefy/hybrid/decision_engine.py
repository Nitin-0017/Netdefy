"""NETDEFY — Hybrid Decision Policy Engine.

Evaluates multi-model evidence (Isolation Forest, Deep Autoencoder, and XGBoost)
under transparent, deterministic, and configurable security rules to produce
final threat intelligence decisions across 4 distinct operational categories.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from netdefy.hybrid.schemas import (
    AnomalyEvidence,
    ClassifierEvidence,
    DecisionCategory,
)


@dataclass(frozen=True)
class DecisionPolicyConfig:
    """Configuration and thresholds for the hybrid decision engine."""

    anomaly_threshold: float = 0.990
    threshold_tier: str = "p99.0"
    detector_disagreement_threshold: float = 0.50
    high_classifier_conflict_confidence: float = 0.85
    benign_label: str = "BENIGN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionPolicyConfig:
        return cls(
            anomaly_threshold=float(data.get("anomaly_threshold", 0.990)),
            threshold_tier=str(data.get("threshold_tier", "p99.0")),
            detector_disagreement_threshold=float(
                data.get("detector_disagreement_threshold", 0.50)
            ),
            high_classifier_conflict_confidence=float(
                data.get("high_classifier_conflict_confidence", 0.85)
            ),
            benign_label=str(data.get("benign_label", "BENIGN")),
        )


class DecisionEngine:
    """Deterministic, policy-driven decision engine for unified threat classification."""

    def __init__(self, config: DecisionPolicyConfig | None = None) -> None:
        self.config = config or DecisionPolicyConfig()

    def evaluate_flow(
        self,
        anomaly_evidence: AnomalyEvidence,
        classifier_evidence: ClassifierEvidence,
    ) -> tuple[DecisionCategory, str]:
        """Apply deterministic decision rules to a single flow's multi-model evidence.

        Returns:
            Tuple of (DecisionCategory, decision_reason_string).
        """
        is_anomaly = anomaly_evidence.is_anomaly
        pred_class = classifier_evidence.predicted_class
        is_rejected = classifier_evidence.rejected
        top_prob = classifier_evidence.top_probability
        c_if = anomaly_evidence.isolation_forest_calibrated_score
        c_ae = anomaly_evidence.autoencoder_calibrated_score

        # Check for detector divergence
        detector_diff = abs(c_if - c_ae)
        is_severe_divergence = detector_diff >= self.config.detector_disagreement_threshold

        # RULE SET 1: Below Operational Anomaly Threshold (Normal Baseline Evidence)
        if not is_anomaly:
            # Check for conflict: Anomaly detector says normal, but classifier insists known attack
            if (
                not is_rejected
                and pred_class != self.config.benign_label
                and top_prob >= self.config.high_classifier_conflict_confidence
            ):
                return (
                    DecisionCategory.REVIEW_REQUIRED,
                    f"Model conflict: Anomaly detectors indicate normal baseline, but supervised "
                    f"classifier confidently predicts known attack '{pred_class}' ({top_prob:.4f}).",
                )

            return (
                DecisionCategory.NORMAL,
                f"Flow metrics conform to learned benign baseline (fused score "
                f"{anomaly_evidence.fused_score:.4f} < {anomaly_evidence.threshold:.4f}).",
            )

        # RULE SET 2: Above Operational Anomaly Threshold (Anomalous Evidence)
        # Check severe detector divergence on borderline anomaly
        if is_severe_divergence and anomaly_evidence.fused_score < (
            anomaly_evidence.threshold + 0.05
        ):
            return (
                DecisionCategory.REVIEW_REQUIRED,
                f"Detector divergence: Isolation Forest ({c_if:.4f}) and Autoencoder ({c_ae:.4f}) "
                f"differ by {detector_diff:.4f} on borderline anomalous flow.",
            )

        # If classifier attribution was rejected (low confidence, small margin, or high entropy)
        if is_rejected:
            return (
                DecisionCategory.SUSPICIOUS_UNKNOWN,
                f"Anomalous flow verified, but supervised attribution was rejected "
                f"({classifier_evidence.rejection_reason}).",
            )

        # If classifier predicted BENIGN despite high anomaly score (open-set signature)
        if pred_class == self.config.benign_label:
            return (
                DecisionCategory.SUSPICIOUS_UNKNOWN,
                "Anomalous flow verified; classifier assigned benign label with insufficient "
                "evidence against unsupervised anomaly detection.",
            )

        # Confident attribution to a known non-benign category
        return (
            DecisionCategory.SUSPICIOUS_KNOWN,
            f"Anomalous flow verified and confidently attributed to known category '{pred_class}' "
            f"(confidence {top_prob:.4f}, margin {classifier_evidence.probability_margin:.4f}).",
        )

    def save(self, filepath: Path | str) -> str:
        """Save decision policy configuration and return SHA-256."""
        path = Path(filepath).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = self.config.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, filepath: Path | str) -> DecisionEngine:
        """Load decision engine from JSON configuration."""
        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Decision policy file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        config = DecisionPolicyConfig.from_dict(data)
        return cls(config=config)
