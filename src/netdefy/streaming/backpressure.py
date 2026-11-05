"""NETDEFY — Backpressure & Dynamic Flow Controller (Phase 6).

Monitors broker stream depth and consumer processing lag to prevent queue
exhaustion, memory ballooning, and downstream model overload.
"""

from __future__ import annotations

import logging
from typing import Any

from netdefy.streaming.broker_interface import MessageBroker

logger = logging.getLogger(__name__)


class BackpressureController:
    """Dynamic admission controller monitoring stream depth and lag."""

    def __init__(
        self,
        broker: MessageBroker,
        stream: str = "netdefy:events:stream",
        low_watermark: int = 5000,
        high_watermark: int = 20000,
        max_depth: int = 50000,
    ) -> None:
        self.broker = broker
        self.stream = stream
        self.low_watermark = low_watermark
        self.high_watermark = high_watermark
        self.max_depth = max_depth

    def get_queue_depth(self) -> int:
        """Fetch current event count in the broker stream."""
        info = self.broker.get_stream_info(self.stream)
        return info.length

    def should_reject(self) -> bool:
        """Returns True if the stream is saturated beyond absolute max depth."""
        depth = self.get_queue_depth()
        return depth >= self.max_depth

    def should_throttle(self) -> bool:
        """Returns True if the stream exceeds the high watermark."""
        depth = self.get_queue_depth()
        return depth >= self.high_watermark

    def get_throttle_delay_seconds(self) -> float:
        """Compute recommended producer backoff sleep duration in seconds."""
        depth = self.get_queue_depth()
        if depth < self.low_watermark:
            return 0.0

        if depth >= self.max_depth:
            return 0.5

        # Linear ramp between low and high watermarks
        fraction = (depth - self.low_watermark) / max(1, self.high_watermark - self.low_watermark)
        return min(0.2, fraction * 0.1)

    def get_status(self) -> dict[str, Any]:
        """Return operational backpressure metrics."""
        depth = self.get_queue_depth()
        return {
            "stream": self.stream,
            "current_depth": depth,
            "low_watermark": self.low_watermark,
            "high_watermark": self.high_watermark,
            "max_depth": self.max_depth,
            "throttling": depth >= self.high_watermark,
            "rejecting": depth >= self.max_depth,
        }
