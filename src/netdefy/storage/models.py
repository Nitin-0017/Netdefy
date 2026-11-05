"""NETDEFY — Relational Database Models (Phase 6).

SQLAlchemy ORM schemas for persistent SOC alerts, event telemetry references,
analyst audit history, and baseline version snapshots.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all Netdefy ORM entities."""


class AlertRecord(Base):
    """Persistent SOC security alert record."""

    __tablename__ = "soc_alerts"

    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    severity: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # CRITICAL, HIGH, MEDIUM, LOW
    status: Mapped[str] = mapped_column(
        String(24), index=True, default="OPEN", nullable=False
    )  # OPEN, ACKNOWLEDGED, INVESTIGATING, RESOLVED, FALSE_POSITIVE
    decision: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # SUSPICIOUS_KNOWN, etc.
    threat_category: Mapped[str] = mapped_column(String(64), index=True, default="UNKNOWN")
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    source_sensor: Mapped[str] = mapped_column(String(64), index=True, default="sensor-default")
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    destination_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    destination_port: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    context_status: Mapped[str] = mapped_column(String(24), default="FULL_CONTEXT")
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    behavioural_evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    model_versions_json: Mapped[str] = mapped_column(Text, default="{}")

    # Relationship to audit history
    actions: Mapped[list[AnalystActionRecord]] = relationship(
        "AnalystActionRecord", back_populates="alert", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_alerts_severity_status", "severity", "status"),
        Index("ix_alerts_port_time", "destination_port", "created_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary for API response serialization."""
        return {
            "alert_id": self.alert_id,
            "event_id": self.event_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "severity": self.severity,
            "status": self.status,
            "decision": self.decision,
            "threat_category": self.threat_category,
            "anomaly_score": round(self.anomaly_score, 4),
            "source_sensor": self.source_sensor,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "destination_port": self.destination_port,
            "protocol": self.protocol,
            "context_status": self.context_status,
            "decision_reason": self.decision_reason,
            "behavioural_evidence": json.loads(self.behavioural_evidence_json),
            "model_versions": json.loads(self.model_versions_json),
        }


class AnalystActionRecord(Base):
    """Immutable audit log of human SOC analyst actions taken on an alert."""

    __tablename__ = "analyst_actions"

    action_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("soc_alerts.alert_id"), index=True, nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    analyst_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # STATUS_CHANGE, NOTE_ADDED, FP_MARKED
    old_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    alert: Mapped[AlertRecord] = relationship("AlertRecord", back_populates="actions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "analyst_id": self.analyst_id,
            "action_type": self.action_type,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "notes": self.notes,
        }


class BaselineVersionRecord(Base):
    """Snapshot record of historical or adaptive baseline distributions."""

    __tablename__ = "baseline_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    observations_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_score: Mapped[float] = mapped_column(Float, default=0.0)
    p95_score: Mapped[float] = mapped_column(Float, default=0.0)
    p99_score: Mapped[float] = mapped_column(Float, default=0.0)
    feature_stats_json: Mapped[str] = mapped_column(Text, default="{}")
    description: Mapped[str] = mapped_column(String(255), default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": bool(self.is_active),
            "observations_count": self.observations_count,
            "mean_score": round(self.mean_score, 4),
            "p95_score": round(self.p95_score, 4),
            "p99_score": round(self.p99_score, 4),
            "description": self.description,
        }
