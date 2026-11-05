"""NETDEFY — Alert Correlation Engine (Phase 6).

Correlates individual SOC alerts into cohesive threat incidents based on available
telemetry metadata without fabricating host identities.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class CorrelatedIncident:
    """Group of correlated security alerts representing a coherent threat event."""

    def __init__(self, correlation_key: str, initial_alert: dict[str, Any]) -> None:
        self.correlation_key = correlation_key
        self.incident_id = f"INC-{correlation_key[:16]}"
        self.first_seen = time.time()
        self.last_seen = self.first_seen
        self.alert_count = 1
        self.alerts: list[str] = [initial_alert["alert_id"]]
        self.severity = initial_alert.get("severity", "MEDIUM")
        self.threat_category = initial_alert.get("threat_category", "UNKNOWN")
        self.destination_ports: set[int] = {initial_alert["destination_port"]}
        self.context_status = initial_alert.get("context_status", "FULL_CONTEXT")

    def add_alert(self, alert: dict[str, Any]) -> None:
        """Incorporate another alert into this incident."""
        self.last_seen = time.time()
        self.alert_count += 1
        self.alerts.append(alert["alert_id"])
        self.destination_ports.add(alert["destination_port"])

        # Escalate severity if incoming alert is higher
        sev_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        if sev_rank.get(alert.get("severity", "LOW"), 1) > sev_rank.get(self.severity, 1):
            self.severity = alert.get("severity", "MEDIUM")

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "correlation_key": self.correlation_key,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "alert_count": self.alert_count,
            "severity": self.severity,
            "threat_category": self.threat_category,
            "unique_destination_ports": len(self.destination_ports),
            "context_status": self.context_status,
            "alert_ids": self.alerts[-20:],  # retain last 20 IDs
        }


class AlertCorrelator:
    """Stateful aggregator correlating alerts across a sliding time window."""

    def __init__(self, correlation_window_seconds: float = 60.0) -> None:
        self.correlation_window_seconds = correlation_window_seconds
        self._incidents: dict[str, CorrelatedIncident] = {}
        self._lock = threading.Lock()

    def _make_key(self, alert: dict[str, Any]) -> str:
        """Derive correlation key strictly using available telemetry."""
        sensor = alert.get("source_sensor", "unknown")
        threat = alert.get("threat_category", "unknown")
        src_ip = alert.get("source_ip")

        if src_ip:
            return f"{sensor}:src={src_ip}:{threat}"

        # Reduced context fallback (port & protocol clustering)
        dst_port = alert.get("destination_port", 0)
        proto = alert.get("protocol", "TCP")
        return f"{sensor}:port={dst_port}:{proto}:{threat}"

    def correlate(self, alert: dict[str, Any]) -> CorrelatedIncident:
        """Incorporate alert into an active incident or create a new one."""
        with self._lock:
            now = time.time()
            self._prune_expired(now)

            key = self._make_key(alert)
            if key in self._incidents:
                incident = self._incidents[key]
                incident.add_alert(alert)
                return incident

            incident = CorrelatedIncident(correlation_key=key, initial_alert=alert)
            self._incidents[key] = incident
            return incident

    def _prune_expired(self, now: float) -> None:
        """Remove incidents inactive beyond the correlation window."""
        expired = [
            k
            for k, inc in self._incidents.items()
            if now - inc.last_seen > self.correlation_window_seconds
        ]
        for k in expired:
            del self._incidents[k]

    def get_active_incidents(self) -> list[dict[str, Any]]:
        """Return snapshot of active correlated incidents."""
        with self._lock:
            now = time.time()
            self._prune_expired(now)
            return [inc.to_dict() for inc in self._incidents.values()]
