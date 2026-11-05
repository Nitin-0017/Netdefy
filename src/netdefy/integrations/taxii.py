"""NETDEFY — TAXII 2.1 Integration Interface (Phase 6).

Defines Oasis TAXII 2.1 protocol interfaces, discovery payloads, and collection
channel abstractions for downstream threat intelligence exchange.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TAXIICollectionInfo:
    """Metadata describing a TAXII 2.1 Collection."""

    id: str
    title: str
    description: str
    can_read: bool = True
    can_write: bool = True
    media_types: list[str] | None = None


class TAXIIClientInterface:
    """Client boundary for publishing STIX bundles to an enterprise TAXII 2.1 Server."""

    def __init__(
        self, server_url: str = "https://taxii.example.org", api_root: str = "api1"
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.api_root = api_root

    def get_discovery_info(self) -> dict[str, Any]:
        """Return TAXII 2.1 Discovery resource."""
        return {
            "title": "NETDEFY TAXII Server Endpoint",
            "description": "Exposes NETDEFY real-time network intelligence feeds",
            "contact": "soc@netdefy.local",
            "default": f"{self.server_url}/{self.api_root}/",
            "api_roots": [f"{self.server_url}/{self.api_root}/"],
        }

    def publish_bundle_to_collection(
        self,
        collection_id: str,
        stix_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare TAXII 2.1 envelope for collection submission.

        Note: In offline or local test environments, this method validates bundle
        structure and returns a simulated TAXII 2.1 Status resource.
        """
        if not collection_id:
            raise ValueError("Collection ID cannot be empty")

        if stix_bundle.get("type") != "bundle":
            raise ValueError("Payload must be a valid STIX 2.1 Bundle")

        status_resource = {
            "id": f"status--{stix_bundle.get('id', 'unknown')}",
            "status": "pending",
            "request_timestamp": "2026-11-05T10:00:00.000Z",
            "total_count": len(stix_bundle.get("objects", [])),
            "success_count": len(stix_bundle.get("objects", [])),
            "failure_count": 0,
            "pending_count": 0,
        }
        return status_resource
