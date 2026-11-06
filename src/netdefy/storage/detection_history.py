"""NETDEFY — Detection History Persistence Store.

Thread-safe, lightweight persistent storage for user-facing network traffic
analysis sessions (both manual single-flow evaluations and CSV batch runs).
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HISTORY_FILE = Path("reports") / "detection_history.json"


class DetectionHistoryStore:
    """Manages persistent analysis records for the Detection Console."""

    def __init__(self, file_path: Path | str = HISTORY_FILE) -> None:
        self.file_path = Path(file_path)
        self._lock = threading.Lock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._save([])

    def _load(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            logger.warning("Could not read detection history file (%s): %s", self.file_path, e)
            return []

    def _save(self, records: list[dict[str, Any]]) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.error("Failed to write detection history to %s: %s", self.file_path, e)

    def add_session(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """Record a completed analysis session."""
        with self._lock:
            records = self._load()
            if "timestamp" not in session_data:
                session_data["timestamp"] = datetime.now(UTC).isoformat()
            records.insert(0, session_data)  # newest first
            # Keep at most 200 sessions to bound disk usage
            records = records[:200]
            self._save(records)
            return session_data

    def list_sessions(self, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Return paginated list of session metadata (excluding heavy flow prediction arrays)."""
        with self._lock:
            records = self._load()
            total = len(records)
            sliced = records[offset : offset + limit]
            # Strip detailed predictions in list view for fast network payload
            lightweight = []
            for r in sliced:
                copy_r = dict(r)
                if "predictions" in copy_r:
                    copy_r["flow_count"] = copy_r.get("flow_count", len(copy_r["predictions"]))
                    # Keep count only
                    del copy_r["predictions"]
                lightweight.append(copy_r)
            return lightweight, total

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve full details of a specific analysis session by ID."""
        with self._lock:
            records = self._load()
            for r in records:
                if r.get("id") == session_id:
                    return r
            return None

    def get_aggregate_stats(self) -> dict[str, Any]:
        """Compute summary statistics across all analyzed flows."""
        with self._lock:
            records = self._load()
            total_sessions = len(records)
            total_flows = sum(r.get("flow_count", 0) for r in records)
            normal_flows = sum(r.get("normal_count", 0) for r in records)
            suspicious_known = sum(r.get("suspicious_known_count", 0) for r in records)
            suspicious_unknown = sum(r.get("suspicious_unknown_count", 0) for r in records)
            review_required = sum(r.get("review_required_count", 0) for r in records)
            suspicious_total = suspicious_known + suspicious_unknown

            recent_events = []
            for r in records[:5]:
                recent_events.append(
                    {
                        "id": r.get("id"),
                        "timestamp": r.get("timestamp"),
                        "source": r.get("source"),
                        "flow_count": r.get("flow_count", 0),
                        "normal_count": r.get("normal_count", 0),
                        "suspicious_count": r.get("suspicious_known_count", 0)
                        + r.get("suspicious_unknown_count", 0),
                        "review_required_count": r.get("review_required_count", 0),
                    }
                )

            return {
                "total_sessions": total_sessions,
                "total_flows_analyzed": total_flows,
                "normal_flows": normal_flows,
                "suspicious_flows": suspicious_total,
                "suspicious_known_flows": suspicious_known,
                "suspicious_unknown_flows": suspicious_unknown,
                "review_required_flows": review_required,
                "recent_sessions": recent_events,
            }

    def clear(self) -> None:
        """Clear all stored sessions."""
        with self._lock:
            self._save([])


# Shared singleton instance
_HISTORY_STORE: DetectionHistoryStore | None = None


def get_history_store() -> DetectionHistoryStore:
    """Return shared DetectionHistoryStore singleton."""
    global _HISTORY_STORE
    if _HISTORY_STORE is None:
        _HISTORY_STORE = DetectionHistoryStore()
    return _HISTORY_STORE
