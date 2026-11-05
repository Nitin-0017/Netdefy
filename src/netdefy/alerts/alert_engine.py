"""NETDEFY — Alert Decision Engine (Phase 6).

Evaluates enhanced hybrid predictions and behavioural telemetry to generate
structured SOC alerts with deterministic severity assignment and deduplication.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from netdefy.behaviour.schema import (
    BehavioralDecisionCategory,
    EnhancedHybridPrediction,
)
from netdefy.hybrid.schemas import DecisionCategory

if TYPE_CHECKING:
    from netdefy.streaming.event_schema import NetworkFlowEvent

logger = logging.getLogger(__name__)


class AlertEngine:
    """Translates model predictions into actionable SOC security alerts."""

    def __init__(
        self,
        critical_anomaly_threshold: float = 0.995,
        high_anomaly_threshold: float = 0.982,
        medium_anomaly_threshold: float = 0.950,
    ) -> None:
        self.critical_anomaly_threshold = critical_anomaly_threshold
        self.high_anomaly_threshold = high_anomaly_threshold
        self.medium_anomaly_threshold = medium_anomaly_threshold

    def assign_severity(
        self,
        decision: str,
        anomaly_score: float,
        predicted_threat: str,
        behavioral_cat: str,
    ) -> str:
        """Deterministically determine alert severity based on calibrated multi-model evidence."""
        # 1. CRITICAL
        if decision == DecisionCategory.SUSPICIOUS_KNOWN.value and (
            anomaly_score >= self.high_anomaly_threshold
            or predicted_threat in ("Bot", "Infiltration")
        ):
            return "CRITICAL"
        if (
            behavioral_cat == BehavioralDecisionCategory.SCANNING_BEHAVIOUR.value
            and anomaly_score >= self.high_anomaly_threshold
        ):
            return "CRITICAL"

        # 2. HIGH
        if decision == DecisionCategory.SUSPICIOUS_KNOWN.value:
            return "HIGH"
        if (
            decision == DecisionCategory.SUSPICIOUS_UNKNOWN.value
            and anomaly_score >= self.high_anomaly_threshold
        ):
            return "HIGH"
        if behavioral_cat in (
            BehavioralDecisionCategory.SCANNING_BEHAVIOUR.value,
            BehavioralDecisionCategory.BURST_ACTIVITY.value,
        ):
            return "HIGH"

        # 3. MEDIUM
        if decision == DecisionCategory.SUSPICIOUS_UNKNOWN.value:
            return "MEDIUM"
        if decision == DecisionCategory.REVIEW_REQUIRED.value:
            return "MEDIUM"
        if anomaly_score >= self.medium_anomaly_threshold:
            return "MEDIUM"

        return "LOW"

    def generate_alert(
        self,
        prediction: EnhancedHybridPrediction,
        event: NetworkFlowEvent,
    ) -> dict[str, Any] | None:
        """Synthesize an alert if the flow decision indicates suspicious or review-worthy activity."""
        decision = prediction.final_decision

        # Benign / Normal flows do not generate alerts
        if decision == DecisionCategory.NORMAL.value:
            return None

        p4d = prediction.phase4d_evidence
        anomaly_score = float(
            p4d.get("anomaly", {}).get(
                "fused_score", p4d.get("anomaly", {}).get("fused_anomaly_score", 0.5)
            )
        )
        classifier_info = p4d.get("classifier", {})
        predicted_class = classifier_info.get("predicted_class", "UNKNOWN")
        threat_cat = predicted_class if predicted_class != "BENIGN" else "UNKNOWN"

        b_cat = prediction.behavioral_decision.value

        severity = self.assign_severity(
            decision=decision,
            anomaly_score=anomaly_score,
            predicted_threat=threat_cat,
            behavioral_cat=b_cat,
        )

        # Deterministic alert_id generated from event_id and decision
        alert_seed = f"{event.event_id}:{decision}:{threat_cat}:{severity}"
        alert_id = hashlib.sha256(alert_seed.encode("utf-8")).hexdigest()[:32]

        # Collect behavioural evidence
        b_evidence: list[str] = list(prediction.behavioral_evidence.evidence_summary)
        if prediction.behavioral_evidence.multi_flow:
            mf = prediction.behavioral_evidence.multi_flow
            b_evidence.append(
                f"Multi-flow window ({mf.window_duration_seconds}s): {mf.connection_count} connections, "
                f"{mf.unique_destination_ports} unique ports, port diversity {mf.port_diversity_ratio:.2f}"
            )

        alert_payload: dict[str, Any] = {
            "alert_id": alert_id,
            "event_id": event.event_id,
            "created_at": datetime.now(UTC),
            "severity": severity,
            "status": "OPEN",
            "decision": decision,
            "threat_category": threat_cat,
            "anomaly_score": anomaly_score,
            "source_sensor": event.source.sensor_id,
            "source_ip": event.source.source_ip,
            "destination_ip": event.source.destination_ip,
            "destination_port": event.source.destination_port,
            "protocol": event.source.protocol,
            "context_status": event.context_status,
            "decision_reason": prediction.decision_reason,
            "behavioural_evidence": b_evidence,
            "model_versions": prediction.model_versions,
        }

        return alert_payload
