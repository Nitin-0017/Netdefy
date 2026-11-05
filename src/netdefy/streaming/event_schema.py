"""NETDEFY — Versioned Network Flow Event Schema (Phase 6).

Defines production-grade Pydantic V2 schemas for network flow ingestion,
source metadata, flow counters, model features, and context attribution.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceMetadata(BaseModel):
    """Source network telemetry and host endpoint metadata."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str = Field(..., description="Unique identifier of capturing sensor or probe")
    source_ip: str | None = Field(default=None, description="Source IPv4/IPv6 address, if unmasked")
    destination_ip: str | None = Field(
        default=None, description="Destination IPv4/IPv6 address, if unmasked"
    )
    source_port: int | None = Field(
        default=None, ge=0, le=65535, description="Source transport port"
    )
    destination_port: int = Field(..., ge=0, le=65535, description="Destination transport port")
    protocol: str = Field(
        default="TCP", description="Transport protocol name or number (e.g. TCP, UDP, 6, 17)"
    )


class FlowSummary(BaseModel):
    """Essential transport layer packet and byte summary statistics."""

    model_config = ConfigDict(extra="forbid")

    duration: float = Field(default=0.0, ge=0.0, description="Flow duration in seconds")
    forward_packets: int = Field(default=0, ge=0, description="Forward direction packet count")
    backward_packets: int = Field(default=0, ge=0, description="Backward direction packet count")
    forward_bytes: int = Field(default=0, ge=0, description="Forward direction byte count")
    backward_bytes: int = Field(default=0, ge=0, description="Backward direction byte count")


class NetworkFlowEvent(BaseModel):
    """Versioned canonical event ingested into the NETDEFY real-time stream."""

    model_config = ConfigDict(extra="allow")

    event_id: str = Field(
        default="", description="Unique event identifier. If empty, deterministically generated"
    )
    schema_version: str = Field(default="1.0", description="Contract schema version")
    event_timestamp: datetime = Field(..., description="Timestamp of flow termination at sensor")
    ingestion_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when event arrived at the ingestion gateway",
    )
    source: SourceMetadata = Field(..., description="Endpoint and network context")
    flow: FlowSummary = Field(default_factory=FlowSummary, description="Basic flow summary")
    features: dict[str, float] = Field(
        default_factory=dict, description="Pre-computed 76 model features"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary auxiliary telemetry or sensor flags"
    )
    context_status: Literal["FULL_CONTEXT", "REDUCED_CONTEXT"] = Field(
        default="FULL_CONTEXT",
        description="Indicates whether genuine host IPs are available or masked",
    )

    @field_validator("features")
    @classmethod
    def validate_finite_features(cls, v: dict[str, float]) -> dict[str, float]:
        """Verify that all model features are strictly finite (reject NaN and Inf)."""
        for k, val in v.items():
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(
                    f"Feature '{k}' contains non-finite or invalid numeric value: {val}"
                )
        return v

    @model_validator(mode="after")
    def post_validate_and_enrich(self) -> NetworkFlowEvent:
        """Enforce context status and deterministic event_id generation."""
        # 1. Detect reduced host context
        if self.source.source_ip is None or self.source.destination_ip is None:
            self.context_status = "REDUCED_CONTEXT"
        else:
            self.context_status = "FULL_CONTEXT"

        # 2. Deterministic event ID generation if empty
        if not self.event_id:
            fingerprint_seed = (
                f"{self.source.sensor_id}:"
                f"{self.event_timestamp.isoformat()}:"
                f"{self.source.destination_port}:"
                f"{self.source.protocol}:"
                f"{self.flow.duration}:"
                f"{self.flow.forward_packets}:"
                f"{self.flow.forward_bytes}"
            )
            self.event_id = hashlib.sha256(fingerprint_seed.encode("utf-8")).hexdigest()[:32]

        return self

    def to_stream_payload(self) -> dict[str, Any]:
        """Serialize event into a JSON-compatible dictionary for message broker publishing."""
        return self.model_dump(mode="json")


class EventBatch(BaseModel):
    """Batch of network flow events for bulk ingestion."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str = Field(default="", description="Unique batch identifier")
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Batch submission timestamp",
    )
    events: list[NetworkFlowEvent] = Field(
        ..., min_length=1, max_length=5000, description="Collection of events"
    )

    @model_validator(mode="after")
    def enrich_batch_id(self) -> EventBatch:
        """Generate batch_id if empty."""
        if not self.batch_id:
            seed = f"{self.submitted_at.isoformat()}:{len(self.events)}"
            self.batch_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return self


class IngestionErrorDetail(BaseModel):
    """Detailed description of an event rejection."""

    event_index: int | None = None
    event_id: str | None = None
    error_code: str
    message: str


class IngestionResponse(BaseModel):
    """Response returned by event ingestion endpoints."""

    status: Literal["ACCEPTED", "PARTIALLY_ACCEPTED", "REJECTED"]
    accepted_count: int
    rejected_count: int
    event_ids: list[str] = Field(default_factory=list)
    errors: list[IngestionErrorDetail] = Field(default_factory=list)
