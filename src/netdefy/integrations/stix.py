"""NETDEFY — STIX 2.1 Threat Intelligence Serializer (Phase 6).

Generates Oasis STIX 2.1 compliant objects (Observed-Data, Sightings, Indicators,
and Bundles) from NETDEFY SOC alerts and behavioural evidence.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class STIXSerializer:
    """Serializes NETDEFY alert records into valid STIX 2.1 JSON structures."""

    IDENTITY_ID = "identity--3d46a81b-5321-4f92-a169-74d32a4501a2"

    @classmethod
    def serialize_alert_to_bundle(cls, alert: dict[str, Any]) -> dict[str, Any]:
        """Convert a NETDEFY alert into a STIX 2.1 Bundle containing Observed Data and Sightings."""
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        alert_id = alert.get("alert_id", uuid.uuid4().hex)
        stable_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, alert_id)

        objects: list[dict[str, Any]] = []

        # 1. Identity Object (NETDEFY Platform)
        identity_obj = {
            "type": "identity",
            "spec_version": "2.1",
            "id": cls.IDENTITY_ID,
            "created": "2026-01-01T00:00:00.000Z",
            "modified": "2026-01-01T00:00:00.000Z",
            "name": "NETDEFY Network Defense Intelligence",
            "identity_class": "system",
        }
        objects.append(identity_obj)

        # 2. Observed-Data Object
        obs_id = f"observed-data--{stable_uuid}"
        dst_port = int(alert.get("destination_port", 0))
        proto = str(alert.get("protocol", "tcp")).lower()

        # Build SCO network-traffic representation
        sco_traffic: dict[str, Any] = {
            "type": "network-traffic",
            "spec_version": "2.1",
            "id": f"network-traffic--{stable_uuid}",
            "dst_port": dst_port,
            "protocols": [proto],
        }
        if alert.get("source_ip"):
            sco_traffic["src_ref"] = (
                f"ipv4-addr--{uuid.uuid5(uuid.NAMESPACE_DNS, alert['source_ip'])}"
            )
        if alert.get("destination_ip"):
            sco_traffic["dst_ref"] = (
                f"ipv4-addr--{uuid.uuid5(uuid.NAMESPACE_DNS, alert['destination_ip'])}"
            )

        observed_data_obj = {
            "type": "observed-data",
            "spec_version": "2.1",
            "id": obs_id,
            "created_by_ref": cls.IDENTITY_ID,
            "created": now_iso,
            "modified": now_iso,
            "first_observed": now_iso,
            "last_observed": now_iso,
            "number_observed": 1,
            "object_refs": [sco_traffic["id"]],
        }
        objects.append(sco_traffic)
        objects.append(observed_data_obj)

        # 3. Sighting or Indicator (Only when verified threat category exists)
        threat_cat = alert.get("threat_category", "UNKNOWN")
        if threat_cat not in ("UNKNOWN", "BENIGN"):
            indicator_id = (
                f"indicator--{uuid.uuid5(uuid.NAMESPACE_DNS, f'{threat_cat}:{dst_port}')}"
            )
            indicator_obj = {
                "type": "indicator",
                "spec_version": "2.1",
                "id": indicator_id,
                "created_by_ref": cls.IDENTITY_ID,
                "created": now_iso,
                "modified": now_iso,
                "name": f"NETDEFY Rule: {threat_cat} on Port {dst_port}",
                "description": alert.get("decision_reason", f"Detected {threat_cat} traffic"),
                "indicator_types": ["anomalous-activity"],
                "pattern_type": "stix",
                "pattern": f"[network-traffic:dst_port = {dst_port}]",
                "valid_from": now_iso,
            }
            objects.append(indicator_obj)

            sighting_id = f"sighting--{uuid.uuid4()}"
            sighting_obj = {
                "type": "sighting",
                "spec_version": "2.1",
                "id": sighting_id,
                "created_by_ref": cls.IDENTITY_ID,
                "created": now_iso,
                "modified": now_iso,
                "sighting_of_ref": indicator_id,
                "observed_data_refs": [obs_id],
                "count": 1,
                "summary": True,
                "description": f"Observed anomaly score {alert.get('anomaly_score', 0.0):.4f} for {threat_cat}",
            }
            objects.append(sighting_obj)

        # 4. Construct Top-Level STIX Bundle
        bundle = {
            "type": "bundle",
            "id": f"bundle--{uuid.uuid4()}",
            "objects": objects,
        }
        return bundle
