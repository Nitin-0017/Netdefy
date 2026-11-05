"""NETDEFY — API Request & Response Schemas (Phase 6).

Pydantic schemas for REST endpoints, health probes, model manifests,
and analyst patch payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str = "ok"
    version: str = "0.1.0"
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Readiness probe evaluating broker and storage connectivity."""

    status: Literal["ready", "not_ready"]
    broker_connected: bool
    database_connected: bool
    models_loaded: bool
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class AlertPatchRequest(BaseModel):
    """Analyst workflow update payload."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"]
    analyst_id: str = Field(..., min_length=2, max_length=64)
    notes: str = Field(default="", max_length=2000)


class AlertDetailResponse(BaseModel):
    """Full alert representation with audit trail."""

    alert_id: str
    event_id: str
    created_at: str | None
    severity: str
    status: str
    decision: str
    threat_category: str
    anomaly_score: float
    source_sensor: str
    source_ip: str | None
    destination_ip: str | None
    destination_port: int
    protocol: str
    context_status: str
    decision_reason: str
    behavioural_evidence: list[str]
    model_versions: dict[str, str]
    audit_history: list[dict[str, Any]] = Field(default_factory=list)


class AlertListResponse(BaseModel):
    """Paginated collection of SOC alerts."""

    total_count: int
    limit: int
    offset: int
    alerts: list[dict[str, Any]]


class StreamStatusResponse(BaseModel):
    """Broker stream depth, group lag, and backpressure telemetry."""

    stream: str
    queue_depth: int
    groups_count: int
    backpressure_active: bool
    rejection_active: bool
    uptime_seconds: float
    rss_memory_mb: float
    events_received: int
    events_accepted: int
    events_processed: int
    alerts_generated: int
    alerts_persisted: int


class ModelManifestResponse(BaseModel):
    """Active model bundle metadata, versions, and checksum hashes."""

    pipeline_name: str
    pipeline_version: str
    device: str
    models: dict[str, dict[str, Any]]
