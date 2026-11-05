"""NETDEFY — Operational Stream Observability & Metrics (Phase 6).

Collects throughput counters, microsecond latency distributions, queue depth,
and memory gauges with Prometheus exposition format support.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from typing import Any

import numpy as np
import psutil

logger = logging.getLogger(__name__)


class StreamMetrics:
    """Thread-safe collector for stream processing, inference, and alert metrics."""

    def __init__(self, latency_window: int = 1000) -> None:
        self._lock = threading.Lock()
        self.latency_window = latency_window

        # Counters
        self.events_received: int = 0
        self.events_accepted: int = 0
        self.events_rejected: int = 0
        self.events_deduplicated: int = 0
        self.events_processed: int = 0
        self.events_quarantined_dlq: int = 0
        self.alerts_generated: int = 0
        self.alerts_persisted: int = 0
        self.alerts_deduplicated: int = 0

        # Latency windows (milliseconds)
        self._ingestion_latencies: deque[float] = deque(maxlen=latency_window)
        self._inference_latencies: deque[float] = deque(maxlen=latency_window)
        self._behaviour_latencies: deque[float] = deque(maxlen=latency_window)
        self._persistence_latencies: deque[float] = deque(maxlen=latency_window)
        self._e2e_latencies: deque[float] = deque(maxlen=latency_window)

        # Process handle for RSS memory tracking
        self._process = psutil.Process(os.getpid())
        self._start_time = time.time()

    def record_ingestion(
        self, accepted: bool, latency_ms: float = 0.0, is_duplicate: bool = False
    ) -> None:
        """Record an ingestion event outcome."""
        with self._lock:
            self.events_received += 1
            if is_duplicate:
                self.events_deduplicated += 1
            elif accepted:
                self.events_accepted += 1
            else:
                self.events_rejected += 1

            if latency_ms > 0:
                self._ingestion_latencies.append(latency_ms)

    def record_processed(
        self,
        count: int = 1,
        inference_ms: float = 0.0,
        behaviour_ms: float = 0.0,
        persistence_ms: float = 0.0,
        e2e_ms: float = 0.0,
    ) -> None:
        """Record batch or single flow processing latencies."""
        with self._lock:
            self.events_processed += count
            if inference_ms > 0:
                self._inference_latencies.append(inference_ms)
            if behaviour_ms > 0:
                self._behaviour_latencies.append(behaviour_ms)
            if persistence_ms > 0:
                self._persistence_latencies.append(persistence_ms)
            if e2e_ms > 0:
                self._e2e_latencies.append(e2e_ms)

    def record_alert(
        self, generated: bool = True, persisted: bool = True, is_duplicate: bool = False
    ) -> None:
        """Record an alert generation outcome."""
        with self._lock:
            if generated:
                self.alerts_generated += 1
            if is_duplicate:
                self.alerts_deduplicated += 1
            elif persisted:
                self.alerts_persisted += 1

    def record_dlq(self, count: int = 1) -> None:
        """Record messages routed to Dead-Letter Queue."""
        with self._lock:
            self.events_quarantined_dlq += count

    def get_summary(self) -> dict[str, Any]:
        """Compute statistical summary of latencies, counters, and resource usage."""
        with self._lock:
            mem_info = self._process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            cpu_pct = self._process.cpu_percent(interval=None)
            uptime_sec = time.time() - self._start_time

            def _percentiles(d: deque[float]) -> dict[str, float]:
                if not d:
                    return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0}
                arr = np.array(d)
                return {
                    "p50": float(np.percentile(arr, 50)),
                    "p95": float(np.percentile(arr, 95)),
                    "p99": float(np.percentile(arr, 99)),
                    "mean": float(np.mean(arr)),
                }

            return {
                "uptime_seconds": round(uptime_sec, 2),
                "rss_memory_mb": round(rss_mb, 2),
                "cpu_percent": round(cpu_pct, 2),
                "counters": {
                    "events_received": self.events_received,
                    "events_accepted": self.events_accepted,
                    "events_rejected": self.events_rejected,
                    "events_deduplicated": self.events_deduplicated,
                    "events_processed": self.events_processed,
                    "events_quarantined_dlq": self.events_quarantined_dlq,
                    "alerts_generated": self.alerts_generated,
                    "alerts_persisted": self.alerts_persisted,
                    "alerts_deduplicated": self.alerts_deduplicated,
                },
                "latencies_ms": {
                    "ingestion": _percentiles(self._ingestion_latencies),
                    "inference": _percentiles(self._inference_latencies),
                    "behaviour": _percentiles(self._behaviour_latencies),
                    "persistence": _percentiles(self._persistence_latencies),
                    "end_to_end": _percentiles(self._e2e_latencies),
                },
            }

    def to_prometheus_format(self) -> str:
        """Format metrics into standard Prometheus exposition format."""
        summary = self.get_summary()
        c = summary["counters"]
        lat = summary["latencies_ms"]

        lines = [
            "# HELP netdefy_events_received_total Total network flow events received",
            "# TYPE netdefy_events_received_total counter",
            f"netdefy_events_received_total {c['events_received']}",
            "# HELP netdefy_events_accepted_total Total network flow events accepted into broker",
            "# TYPE netdefy_events_accepted_total counter",
            f"netdefy_events_accepted_total {c['events_accepted']}",
            "# HELP netdefy_events_processed_total Total network flow events processed by hybrid engine",
            "# TYPE netdefy_events_processed_total counter",
            f"netdefy_events_processed_total {c['events_processed']}",
            "# HELP netdefy_alerts_generated_total Total security alerts generated",
            "# TYPE netdefy_alerts_generated_total counter",
            f"netdefy_alerts_generated_total {c['alerts_generated']}",
            "# HELP netdefy_alerts_persisted_total Total security alerts persisted in database",
            "# TYPE netdefy_alerts_persisted_total counter",
            f"netdefy_alerts_persisted_total {c['alerts_persisted']}",
            "# HELP netdefy_process_rss_mb Process resident set size in megabytes",
            "# TYPE netdefy_process_rss_mb gauge",
            f"netdefy_process_rss_mb {summary['rss_memory_mb']}",
            "# HELP netdefy_e2e_latency_p95_ms End-to-end processing latency 95th percentile in milliseconds",
            "# TYPE netdefy_e2e_latency_p95_ms gauge",
            f"netdefy_e2e_latency_p95_ms {lat['end_to_end']['p95']}",
        ]
        return "\n".join(lines) + "\n"
