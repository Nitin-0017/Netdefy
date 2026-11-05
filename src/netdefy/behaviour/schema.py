"""NETDEFY — Behavioral Network Intelligence Schemas.

Defines strongly-typed data contracts for network events, intra-flow dynamics,
multi-flow sliding window contexts, and behavioral decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class BehavioralDecisionCategory(StrEnum):
    """Decision classification for behavioral context engine."""

    NORMAL = "NORMAL"
    SUSPICIOUS_BEHAVIOUR = "SUSPICIOUS_BEHAVIOUR"
    SCANNING_BEHAVIOUR = "SCANNING_BEHAVIOUR"
    BURST_ACTIVITY = "BURST_ACTIVITY"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


@dataclass(frozen=True)
class NetworkEvent:
    """Standardized network traffic event representation."""

    flow_id: str | None = None
    timestamp: float | None = None  # Unix timestamp in seconds
    source_ip: str | None = None
    destination_ip: str | None = None
    source_port: int | None = None
    destination_port: int | None = None
    protocol: int | str | None = None
    features: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntraFlowBehavior:
    """Behavioral dynamics computed purely from intra-flow metrics (Tier A)."""

    directional_packet_ratio: float
    directional_byte_ratio: float
    burstiness_index: float
    iat_asymmetry: float
    active_duration_ratio: float
    window_disparity: float
    is_scan_signature: bool
    service_category: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MultiFlowContext:
    """Multi-flow temporal window aggregation metrics (Tier B)."""

    window_duration_seconds: float
    connection_count: int
    unique_destinations: int
    unique_destination_ports: int
    destination_diversity_ratio: float
    port_diversity_ratio: float
    connection_rate: float
    burst_z_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BehavioralEvidence:
    """Aggregated evidence from behavioral and temporal engines."""

    decision: BehavioralDecisionCategory
    intra_flow: IntraFlowBehavior
    multi_flow: MultiFlowContext | None = None
    evidence_summary: list[str] = field(default_factory=list)
    confidence_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "intra_flow": self.intra_flow.to_dict(),
            "multi_flow": self.multi_flow.to_dict() if self.multi_flow else None,
            "evidence_summary": self.evidence_summary,
            "confidence_score": self.confidence_score,
        }


@dataclass(frozen=True)
class EnhancedHybridPrediction:
    """Final combined prediction fusing Phase 4D Hybrid with Phase 5 Behavioral Context."""

    flow_id: int | str | None
    original_phase4d_decision: str
    behavioral_decision: BehavioralDecisionCategory
    final_decision: str
    decision_reason: str
    phase4d_evidence: dict[str, Any]
    behavioral_evidence: BehavioralEvidence
    model_versions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "original_phase4d_decision": self.original_phase4d_decision,
            "behavioral_decision": self.behavioral_decision.value,
            "final_decision": self.final_decision,
            "decision_reason": self.decision_reason,
            "phase4d_evidence": self.phase4d_evidence,
            "behavioral_evidence": self.behavioral_evidence.to_dict(),
            "model_versions": self.model_versions,
        }
