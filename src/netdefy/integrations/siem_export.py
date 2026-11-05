"""NETDEFY — Unified SIEM & SOAR Export Router (Phase 6).

Routes security alerts to ArcSight CEF, STIX 2.1 bundles, local log sinks,
and forwarders.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from netdefy.integrations.cef import CEFSerializer
from netdefy.integrations.stix import STIXSerializer

logger = logging.getLogger(__name__)


class SIEMExportRouter:
    """Manages dispatching alerts to multiple security operational formats."""

    def __init__(self, export_dir: Path | str = "reports/siem_exports") -> None:
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.cef_log_path = self.export_dir / "alerts.cef"
        self.stix_dir = self.export_dir / "stix_bundles"
        self.stix_dir.mkdir(parents=True, exist_ok=True)

    def export_alert(
        self,
        alert: dict[str, Any],
        format: Literal["CEF", "STIX", "JSON", "ALL"] = "ALL",
    ) -> dict[str, Any]:
        """Format and append alert to configured SIEM destinations."""
        results: dict[str, Any] = {}

        # 1. CEF Export
        if format in ("CEF", "ALL"):
            cef_string = CEFSerializer.serialize_alert(alert)
            with open(self.cef_log_path, "a", encoding="utf-8") as f:
                f.write(cef_string + "\n")
            results["cef"] = cef_string

        # 2. STIX 2.1 Export
        if format in ("STIX", "ALL"):
            bundle = STIXSerializer.serialize_alert_to_bundle(alert)
            bundle_filename = f"{alert.get('alert_id', 'unknown')}.json"
            bundle_path = self.stix_dir / bundle_filename
            with open(bundle_path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2)
            results["stix_bundle_id"] = bundle["id"]
            results["stix_path"] = str(bundle_path)

        # 3. JSON Export
        if format in ("JSON", "ALL"):
            results["json"] = alert

        return results
