"""NETDEFY — ArcSight Common Event Format (CEF) Serializer (Phase 6).

Implements RFC-compliant CEF header generation, extension key-value encoding,
and character escaping for enterprise SIEM ingestion (ArcSight, Splunk, QRadar).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CEFSerializer:
    """Serializes NETDEFY SOC alerts into standardized CEF strings."""

    DEVICE_VENDOR = "NETDEFY"
    DEVICE_PRODUCT = "Network Defense Intelligence"
    DEVICE_VERSION = "0.1.0"

    SEVERITY_MAP: dict[str, int] = {
        "LOW": 3,
        "MEDIUM": 6,
        "HIGH": 8,
        "CRITICAL": 10,
    }

    @classmethod
    def _escape_header(cls, value: str) -> str:
        """Escape backslashes and pipes in CEF header fields."""
        if not value:
            return ""
        return value.replace("\\", "\\\\").replace("|", "\\|")

    @classmethod
    def _escape_extension_value(cls, value: Any) -> str:
        """Escape backslashes, equals signs, and newlines in CEF extension values."""
        if value is None:
            return ""
        s = str(value)
        return s.replace("\\", "\\\\").replace("=", "\\=").replace("\n", "\\n").replace("\r", "\\r")

    @classmethod
    def serialize_alert(cls, alert: dict[str, Any]) -> str:
        """Convert alert dictionary to valid CEF syslog line.

        Format:
        CEF:0|Device Vendor|Device Product|Device Version|Device Event Class ID|Name|Severity|Extension
        """
        severity_str = alert.get("severity", "MEDIUM").upper()
        severity_num = cls.SEVERITY_MAP.get(severity_str, 5)

        event_class_id = cls._escape_header(alert.get("decision", "SUSPICIOUS_UNKNOWN"))
        name = cls._escape_header(
            f"Netdefy Alert: {alert.get('threat_category', 'UNKNOWN')} ({alert.get('decision', 'ANOMALY')})"
        )

        # Header fields
        header = (
            f"CEF:0|"
            f"{cls._escape_header(cls.DEVICE_VENDOR)}|"
            f"{cls._escape_header(cls.DEVICE_PRODUCT)}|"
            f"{cls._escape_header(cls.DEVICE_VERSION)}|"
            f"{event_class_id}|"
            f"{name}|"
            f"{severity_num}|"
        )

        # Extension fields
        extensions: list[str] = [
            f"externalId={cls._escape_extension_value(alert.get('alert_id', ''))}",
            f"dvc={cls._escape_extension_value(alert.get('source_sensor', 'sensor-01'))}",
            f"dpt={int(alert.get('destination_port', 0))}",
            f"proto={cls._escape_extension_value(alert.get('protocol', 'TCP'))}",
            f"act={cls._escape_extension_value(alert.get('status', 'OPEN'))}",
            f"cat={cls._escape_extension_value(alert.get('threat_category', 'UNKNOWN'))}",
            f"cs1Label=ContextStatus cs1={cls._escape_extension_value(alert.get('context_status', 'FULL_CONTEXT'))}",
            f"cn1Label=AnomalyScore cn1={float(alert.get('anomaly_score', 0.0)):.4f}",
            f"msg={cls._escape_extension_value(alert.get('decision_reason', ''))}",
        ]

        if alert.get("source_ip"):
            extensions.append(f"src={cls._escape_extension_value(alert['source_ip'])}")
        if alert.get("destination_ip"):
            extensions.append(f"dst={cls._escape_extension_value(alert['destination_ip'])}")

        return header + " ".join(extensions)
