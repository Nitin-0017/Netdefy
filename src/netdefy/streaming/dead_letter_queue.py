"""NETDEFY — Dead-Letter Queue (DLQ) Manager (Phase 6).

Routes permanently unprocessable, poisoned, or schema-invalid events to a durable
dead-letter stream with structured diagnostics and failure context.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from netdefy.streaming.broker_interface import MessageBroker

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Manages routing and quarantine of unprocessable messages."""

    def __init__(
        self,
        broker: MessageBroker,
        dlq_stream: str = "netdefy:dlq:stream",
        max_len: int = 10000,
    ) -> None:
        self.broker = broker
        self.dlq_stream = dlq_stream
        self.max_len = max_len

    def route_to_dlq(
        self,
        original_payload: dict[str, Any],
        error_code: str,
        error_message: str,
        message_id: str | None = None,
        attempt_count: int = 1,
    ) -> str:
        """Quarantine a message by appending it to the DLQ stream."""
        dlq_entry = {
            "quarantine_timestamp": datetime.now(UTC).isoformat(),
            "original_message_id": message_id,
            "error_code": error_code,
            "error_message": error_message,
            "attempt_count": attempt_count,
            "original_payload": original_payload,
        }

        try:
            dlq_id = self.broker.publish(self.dlq_stream, dlq_entry, max_len=self.max_len)
            logger.warning(
                "Quarantined message %s to DLQ stream '%s' (ID: %s, Error: %s)",
                message_id,
                self.dlq_stream,
                dlq_id,
                error_code,
            )
            return dlq_id
        except Exception as e:
            logger.error("Failed to publish to DLQ stream '%s': %s", self.dlq_stream, e)
            return ""
