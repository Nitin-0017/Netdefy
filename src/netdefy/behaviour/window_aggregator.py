"""NETDEFY — Multi-Flow Sliding Window Aggregator.

Maintains memory-bounded, time-indexed sliding windows of network events to calculate
rolling connection rates, destination diversity, and inter-flow temporal dynamics.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

from netdefy.behaviour.schema import MultiFlowContext, NetworkEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowAggregatorConfig:
    """Configuration for sliding window aggregation."""

    window_duration_seconds: float = 30.0
    max_events_capacity: int = 10000
    allow_out_of_order: bool = True
    max_out_of_order_seconds: float = 5.0


class WindowAggregator:
    """Memory-bounded, streaming-compatible sliding window aggregator for sequential traffic events."""

    def __init__(self, config: WindowAggregatorConfig | None = None) -> None:
        self.config = config or WindowAggregatorConfig()
        self.events: deque[NetworkEvent] = deque(maxlen=self.config.max_events_capacity)
        self.latest_timestamp: float | None = None

    def add_event(self, event: NetworkEvent) -> None:
        """Add a network traffic event into the sliding window and prune expired records."""
        if event.timestamp is None:
            # Events without timestamp are appended with index-based eviction
            self.events.append(event)
            return

        ts = event.timestamp
        if self.latest_timestamp is not None and ts < self.latest_timestamp:
            delta = self.latest_timestamp - ts
            if delta > self.config.max_out_of_order_seconds and not self.config.allow_out_of_order:
                raise ValueError(
                    f"Out-of-order event rejected: event ts {ts} is {delta:.2f}s older than latest {self.latest_timestamp}"
                )
            logger.debug("Received slightly out-of-order event (delta=%.3fs)", delta)
        else:
            self.latest_timestamp = ts

        self.events.append(event)
        self._prune_expired(ts)

    def _prune_expired(self, current_ts: float) -> None:
        cutoff = current_ts - self.config.window_duration_seconds
        while (
            self.events
            and self.events[0].timestamp is not None
            and self.events[0].timestamp < cutoff
        ):
            self.events.popleft()

    def get_context(self, current_timestamp: float | None = None) -> MultiFlowContext:
        """Compute multi-flow aggregation metrics over the active sliding window."""
        ts = current_timestamp or self.latest_timestamp
        if ts is not None:
            self._prune_expired(ts)

        n_events = len(self.events)
        if n_events == 0:
            return MultiFlowContext(
                window_duration_seconds=self.config.window_duration_seconds,
                connection_count=0,
                unique_destinations=0,
                unique_destination_ports=0,
                destination_diversity_ratio=0.0,
                port_diversity_ratio=0.0,
                connection_rate=0.0,
                burst_z_score=0.0,
            )

        dest_ips: set[str] = set()
        dest_ports: set[int] = set()

        for ev in self.events:
            if ev.destination_ip is not None:
                dest_ips.add(ev.destination_ip)
            if ev.destination_port is not None:
                dest_ports.add(ev.destination_port)

        u_dest = len(dest_ips)
        u_ports = len(dest_ports)
        dest_div = float(u_dest / n_events) if n_events > 0 else 0.0
        port_div = float(u_ports / n_events) if n_events > 0 else 0.0
        conn_rate = float(n_events / max(1.0, self.config.window_duration_seconds))

        return MultiFlowContext(
            window_duration_seconds=self.config.window_duration_seconds,
            connection_count=n_events,
            unique_destinations=u_dest,
            unique_destination_ports=u_ports,
            destination_diversity_ratio=dest_div,
            port_diversity_ratio=port_div,
            connection_rate=conn_rate,
            burst_z_score=0.0,
        )

    def reset(self) -> None:
        """Clear all events and reset aggregator state."""
        self.events.clear()
        self.latest_timestamp = None

    def __len__(self) -> int:
        return len(self.events)
