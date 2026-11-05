"""NETDEFY — Abstract Message Broker Interface (Phase 6).

Defines the broker-agnostic contract for streaming message transport,
consumer groups, delivery acknowledgements, and dead-letter handling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamMessage:
    """Standardized message consumed from an event stream."""

    message_id: str
    stream: str
    payload: dict[str, Any]
    timestamp_ms: int = 0
    delivery_count: int = 1


@dataclass
class PendingMessageInfo:
    """Details of a message in a consumer group's Pending Entry List (PEL)."""

    message_id: str
    consumer: str
    idle_time_ms: int
    delivery_count: int


@dataclass
class StreamInfo:
    """Metadata regarding a stream's current depth and boundaries."""

    stream: str
    length: int
    first_id: str | None = None
    last_id: str | None = None
    groups_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageBroker(ABC):
    """Abstract interface defining required streaming capabilities."""

    @abstractmethod
    def publish(
        self,
        stream: str,
        payload: dict[str, Any],
        max_len: int | None = None,
    ) -> str:
        """Publish an event to the specified stream, returning the assigned message ID."""

    @abstractmethod
    def publish_batch(
        self,
        stream: str,
        payloads: list[dict[str, Any]],
        max_len: int | None = None,
    ) -> list[str]:
        """Publish a batch of events atomically or sequentially to the stream."""

    @abstractmethod
    def create_consumer_group(
        self,
        stream: str,
        group: str,
        start_id: str = "$",
        make_stream: bool = True,
    ) -> None:
        """Create a consumer group on the specified stream."""

    @abstractmethod
    def read_group(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 0,
    ) -> list[StreamMessage]:
        """Read pending or new messages for a specific consumer within a consumer group."""

    @abstractmethod
    def ack(self, stream: str, group: str, message_ids: list[str]) -> int:
        """Acknowledge one or more message IDs, removing them from the Pending Entry List."""

    @abstractmethod
    def get_pending(
        self,
        stream: str,
        group: str,
        count: int = 50,
    ) -> list[PendingMessageInfo]:
        """Inspect unacknowledged messages currently in the group's Pending Entry List."""

    @abstractmethod
    def claim_pending(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_time_ms: int,
        message_ids: list[str],
    ) -> list[StreamMessage]:
        """Claim ownership of unacknowledged messages that have been idle past threshold."""

    @abstractmethod
    def get_stream_info(self, stream: str) -> StreamInfo:
        """Obtain depth, length, and metadata for a stream."""

    @abstractmethod
    def trim(self, stream: str, max_len: int) -> int:
        """Evict oldest entries to bound stream storage length."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if broker connection is alive and healthy."""
