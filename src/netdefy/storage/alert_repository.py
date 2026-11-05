"""NETDEFY — Persistent Alert Repository (Phase 6).

Data access layer managing alert queries, state transitions, analyst audit logs,
pagination, and idempotent insertion.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from netdefy.storage.models import AlertRecord, AnalystActionRecord

logger = logging.getLogger(__name__)


class AlertRepository:
    """Repository managing SOC alert persistence and workflow lifecycles."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_alert(self, data: dict[str, Any]) -> tuple[AlertRecord, bool]:
        """Idempotently insert an alert. Returns (record, is_created)."""
        alert_id = data["alert_id"]
        existing = self.session.get(AlertRecord, alert_id)
        if existing is not None:
            return existing, False

        record = AlertRecord(
            alert_id=alert_id,
            event_id=data["event_id"],
            created_at=data.get("created_at") or datetime.now(UTC),
            severity=data.get("severity", "MEDIUM"),
            status=data.get("status", "OPEN"),
            decision=data["decision"],
            threat_category=data.get("threat_category", "UNKNOWN"),
            anomaly_score=float(data["anomaly_score"]),
            source_sensor=data.get("source_sensor", "sensor-default"),
            source_ip=data.get("source_ip"),
            destination_ip=data.get("destination_ip"),
            destination_port=int(data["destination_port"]),
            protocol=str(data.get("protocol", "TCP")),
            context_status=data.get("context_status", "FULL_CONTEXT"),
            decision_reason=data.get("decision_reason", ""),
            behavioural_evidence_json=json.dumps(data.get("behavioural_evidence", [])),
            model_versions_json=json.dumps(data.get("model_versions", {})),
        )

        self.session.add(record)
        self.session.flush()
        return record, True

    def get_alert(self, alert_id: str) -> AlertRecord | None:
        """Fetch alert by its unique alert_id."""
        return self.session.get(AlertRecord, alert_id)

    def list_alerts(
        self,
        status: str | None = None,
        severity: str | None = None,
        destination_port: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AlertRecord], int]:
        """Query alerts with filtering and pagination. Returns (records, total_count)."""
        stmt = select(AlertRecord)

        if status:
            stmt = stmt.where(AlertRecord.status == status)
        if severity:
            stmt = stmt.where(AlertRecord.severity == severity)
        if destination_port is not None:
            stmt = stmt.where(AlertRecord.destination_port == destination_port)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = self.session.scalar(count_stmt) or 0

        stmt = stmt.order_by(AlertRecord.created_at.desc()).limit(limit).offset(offset)
        records = list(self.session.scalars(stmt).all())

        return records, total_count

    def update_status(
        self,
        alert_id: str,
        new_status: str,
        analyst_id: str,
        notes: str = "",
    ) -> AlertRecord | None:
        """Transition alert workflow state and append an auditable action record."""
        alert = self.get_alert(alert_id)
        if not alert:
            return None

        old_status = alert.status
        alert.status = new_status

        action = AnalystActionRecord(
            alert_id=alert_id,
            timestamp=datetime.now(UTC),
            analyst_id=analyst_id,
            action_type="STATUS_CHANGE",
            old_status=old_status,
            new_status=new_status,
            notes=notes,
        )
        self.session.add(action)
        self.session.flush()

        logger.info(
            "Alert %s status transitioned from %s to %s by %s",
            alert_id,
            old_status,
            new_status,
            analyst_id,
        )
        return alert

    def get_audit_trail(self, alert_id: str) -> list[AnalystActionRecord]:
        """Fetch chronological analyst action history for an alert."""
        stmt = (
            select(AnalystActionRecord)
            .where(AnalystActionRecord.alert_id == alert_id)
            .order_by(AnalystActionRecord.timestamp.asc())
        )
        return list(self.session.scalars(stmt).all())
