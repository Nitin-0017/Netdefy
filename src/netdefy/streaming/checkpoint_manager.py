"""NETDEFY — Consumer Checkpoint Manager (Phase 6).

Tracks consumer group offsets, pending entries, and durable checkpoint records.
"""

from __future__ import annotations

import logging
from typing import Any

from netdefy.streaming.broker_interface import MessageBroker, PendingMessageInfo

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages offset checkpoints and unacknowledged message recovery."""

    def __init__(
        self,
        broker: MessageBroker,
        stream: str = "netdefy:events:stream",
        group: str = "netdefy-engine-cg",
        consumer_name: str = "consumer-worker-01",
    ) -> None:
        self.broker = broker
        self.stream = stream
        self.group = group
        self.consumer_name = consumer_name

    def get_pending_messages(self, count: int = 50) -> list[PendingMessageInfo]:
        """Fetch unacknowledged messages currently in consumer group PEL."""
        return self.broker.get_pending(self.stream, self.group, count=count)

    def reclaim_stale_pending(
        self,
        min_idle_time_ms: int = 30000,
        max_claim_count: int = 50,
    ) -> list[Any]:
        """Claim ownership of messages abandoned by crashed consumer workers."""
        pending = self.get_pending_messages(count=max_claim_count)
        stale_ids = [
            p.message_id
            for p in pending
            if p.idle_time_ms >= min_idle_time_ms and p.consumer != self.consumer_name
        ]
        if not stale_ids:
            return []

        logger.info(
            "Reclaiming %d abandoned messages from PEL (idle > %d ms)",
            len(stale_ids),
            min_idle_time_ms,
        )
        return self.broker.claim_pending(
            self.stream,
            self.group,
            self.consumer_name,
            min_idle_time_ms,
            stale_ids,
        )
