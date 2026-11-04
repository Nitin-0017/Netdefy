"""NETDEFY — Hybrid Decision Explanation & Feature Attribution Engine.

Generates structured diagnostic evidence, feature-level reconstruction attributions,
and human-auditable decision justifications for every network flow prediction.
"""

from __future__ import annotations

import numpy as np

from netdefy.hybrid.schemas import (
    AnomalyEvidence,
    ClassifierEvidence,
    DecisionCategory,
    FeatureAttribution,
    FlowExplanation,
)


class ExplanationGenerator:
    """Produces structured evidence and feature-level reconstruction deviations."""

    def __init__(self, top_k_features: int = 5) -> None:
        self.top_k_features = top_k_features

    def explain(
        self,
        decision: DecisionCategory,
        decision_reason: str,
        anomaly_evidence: AnomalyEvidence,
        classifier_evidence: ClassifierEvidence,
        feature_names: list[str] | None = None,
        x_raw_or_scaled: np.ndarray | None = None,
        x_reconstructed: np.ndarray | None = None,
    ) -> FlowExplanation:
        """Construct structured explanation record."""
        evidence_summary: list[str] = []

        # Anomaly evidence statements
        if anomaly_evidence.is_anomaly:
            evidence_summary.append(
                f"Fused anomaly score ({anomaly_evidence.fused_score:.4f}) exceeded "
                f"{anomaly_evidence.threshold_tier} operational threshold ({anomaly_evidence.threshold:.4f})."
            )
            evidence_summary.append(
                f"Component scores: Isolation Forest (cal={anomaly_evidence.isolation_forest_calibrated_score:.4f}, raw={anomaly_evidence.isolation_forest_raw_score:.4f}), "
                f"Autoencoder (cal={anomaly_evidence.autoencoder_calibrated_score:.4f}, MSE={anomaly_evidence.autoencoder_raw_error:.6f})."
            )
        else:
            evidence_summary.append(
                f"Fused anomaly score ({anomaly_evidence.fused_score:.4f}) remains below "
                f"{anomaly_evidence.threshold_tier} operational threshold ({anomaly_evidence.threshold:.4f})."
            )

        # Classification evidence statements
        if classifier_evidence.rejected:
            evidence_summary.append(
                f"Supervised attribution was REJECTED: {classifier_evidence.rejection_reason} "
                f"(top candidate '{classifier_evidence.predicted_class}' with confidence {classifier_evidence.top_probability:.4f})."
            )
        else:
            evidence_summary.append(
                f"Supervised classifier attributed flow to known category '{classifier_evidence.predicted_class}' "
                f"with high confidence ({classifier_evidence.top_probability:.4f}) and decision margin ({classifier_evidence.probability_margin:.4f})."
            )

        # Feature-level reconstruction attribution
        top_features: list[FeatureAttribution] = []
        if (
            feature_names is not None
            and x_raw_or_scaled is not None
            and x_reconstructed is not None
        ):
            x_in = np.asarray(x_raw_or_scaled, dtype=np.float32).ravel()
            x_rec = np.asarray(x_reconstructed, dtype=np.float32).ravel()
            if len(x_in) == len(x_rec) == len(feature_names):
                sq_errors = (x_in - x_rec) ** 2
                top_indices = np.argsort(-sq_errors)[: self.top_k_features]
                for idx in top_indices:
                    top_features.append(
                        FeatureAttribution(
                            feature_name=feature_names[idx],
                            reconstruction_error=float(sq_errors[idx]),
                            input_value=float(x_in[idx]),
                            reconstructed_value=float(x_rec[idx]),
                        )
                    )

        return FlowExplanation(
            decision=decision,
            decision_reason=decision_reason,
            evidence_summary=evidence_summary,
            top_contributing_features=top_features,
        )
