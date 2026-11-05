"""NETDEFY — High-Fidelity In-Memory Stream Broker (Phase 6).

Provides a thread-safe, zero-dependency stream broker emulating Redis Streams
consumer groups, Pending Entry Lists (PEL), acknowledgements, and trimming.
Used for deterministic unit testing, local execution, and CI pipelines.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any

from netdefy.streaming.broker_interface import (
    MessageBroker,
    PendingMessageInfo,
    StreamInfo,
    StreamMessage,
)

logger = logging.getLogger(__name__)


class _ConsumerGroupState:
    """Internal state of a consumer group on an in-memory stream."""

    def __init__(self, name: str, start_index: int) -> None:
        self.name = name
        self.last_delivered_index = start_index
        # message_id -> dict(consumer, timestamp_ms, delivery_count, message)
        self.pel: dict[str, dict[str, Any]] = {}


class InMemoryStreamBroker(MessageBroker):
    """Thread-safe in-memory stream broker with full Redis Streams semantic parity."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._streams: dict[str, list[StreamMessage]] = {}
        self._groups: dict[str, dict[str, _ConsumerGroupState]] = {}
        self._sequence_counter: int = 0
        self._connected: bool = True

    def publish(
        self,
        stream: str,
        payload: dict[str, Any],
        max_len: int | None = None,
    ) -> str:
        """Publish an event to the stream with a monotonically increasing ID."""
        with self._lock:
            if stream not in self._streams:
                self._streams[stream] = []

            now_ms = int(time.time() * 1000)
            self._sequence_counter += 1
            msg_id = f"{now_ms}-{self._sequence_counter}"

            msg = StreamMessage(
                message_id=msg_id,
                stream=stream,
                payload=copy.deepcopy(payload),
                timestamp_ms=now_ms,
                delivery_count=0,
            )
            self._streams[stream].append(msg)

            if max_len is not None and len(self._streams[stream]) > max_len:
                excess = len(self._streams[stream]) - max_len
                del self._streams[stream][:excess]

            return msg_id

    def publish_batch(
        self,
        stream: str,
        payloads: list[dict[str, Any]],
        max_len: int | None = None,
    ) -> list[str]:
        """Publish a batch of events sequentially under lock."""
        with self._lock:
            return [self.publish(stream, p, max_len=max_len) for p in payloads]

    def create_consumer_group(
        self,
        stream: str,
        group: str,
        start_id: str = "$",
        make_stream: bool = True,
    ) -> None:
        """Create a consumer group on a stream."""
        with self._lock:
            if stream not in self._streams:
                if make_stream:
                    self._streams[stream] = []
                else:
                    raise KeyError(f"Stream '{stream}' does not exist")

            if stream not in self._groups:
                self._groups[stream] = {}

            stream_len = len(self._streams[stream])
            if start_id == "$":
                start_idx = stream_len
            elif start_id == "0":
                start_idx = 0
            else:
                # Find matching ID index
                start_idx = 0
                for idx, m in enumerate(self._streams[stream]):
                    if m.message_id == start_id:
                        start_idx = idx + 1
                        break

            self._groups[stream][group] = _ConsumerGroupState(group, start_idx)

    def read_group(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 0,
    ) -> list[StreamMessage]:
        """Read up to `count` unread messages for a consumer in a group."""
        start_time = time.time()
        while True:
            with self._lock:
                if (
                    stream not in self._streams
                    or stream not in self._groups
                    or group not in self._groups[stream]
                ):
                    return []

                grp = self._groups[stream][group]
                stream_list = self._streams[stream]
                delivered: list[StreamMessage] = []

                curr_idx = grp.last_delivered_index
                while curr_idx < len(stream_list) and len(delivered) < count:
                    msg = copy.deepcopy(stream_list[curr_idx])
                    msg.delivery_count += 1
                    delivered.append(msg)

                    now_ms = int(time.time() * 1000)
                    grp.pel[msg.message_id] = {
                        "consumer": consumer,
                        "timestamp_ms": now_ms,
                        "delivery_count": msg.delivery_count,
                        "message": copy.deepcopy(msg),
                    }
                    curr_idx += 1

                grp.last_delivered_index = curr_idx
                if delivered or block_ms <= 0:
                    return delivered

            # Sleep briefly if blocking
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= block_ms:
                return []
            time.sleep(min(0.01, (block_ms - elapsed) / 1000.0))

    def ack(self, stream: str, group: str, message_ids: list[str]) -> int:
        """Acknowledge message IDs, removing them from group's PEL."""
        with self._lock:
            if stream not in self._groups or group not in self._groups[stream]:
                return 0

            grp = self._groups[stream][group]
            acked = 0
            for mid in message_ids:
                if mid in grp.pel:
                    del grp.pel[mid]
                    acked += 1
            return acked

    def get_pending(
        self,
        stream: str,
        group: str,
        count: int = 50,
    ) -> list[PendingMessageInfo]:
        """Inspect unacknowledged messages currently in group PEL."""
        with self._lock:
            if stream not in self._groups or group not in self._groups[stream]:
                return []

            grp = self._groups[stream][group]
            now_ms = int(time.time() * 1000)
            pending: list[PendingMessageInfo] = []

            for mid, entry in list(grp.pel.items())[:count]:
                idle = max(0, now_ms - entry["timestamp_ms"])
                pending.append(
                    PendingMessageInfo(
                        message_id=mid,
                        consumer=entry["consumer"],
                        idle_time_ms=idle,
                        delivery_count=entry["delivery_count"],
                    )
                )
            return pending

    def claim_pending(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_time_ms: int,
        message_ids: list[str],
    ) -> list[StreamMessage]:
        """Claim ownership of idle unacknowledged messages."""
        with self._lock:
            if stream not in self._groups or group not in self._groups[stream]:
                return []

            grp = self._groups[stream][group]
            now_ms = int(time.time() * 1000)
            claimed: list[StreamMessage] = []

            for mid in message_ids:
                if mid in grp.pel:
                    entry = grp.pel[mid]
                    idle = now_ms - entry["timestamp_ms"]
                    if idle >= min_idle_time_ms:
                        entry["consumer"] = consumer
                        entry["timestamp_ms"] = now_ms
                        entry["delivery_count"] += 1
                        msg = copy.deepcopy(entry["message"])
                        msg.delivery_count = entry["delivery_count"]
                        claimed.append(msg)

            return claimed

    def get_stream_info(self, stream: str) -> StreamInfo:
        """Return stream depth and consumer group count."""
        with self._lock:
            if stream not in self._streams or not self._streams[stream]:
                return StreamInfo(
                    stream=stream, length=0, groups_count=len(self._groups.get(stream, {}))
                )

            s = self._streams[stream]
            return StreamInfo(
                stream=stream,
                length=len(s),
                first_id=s[0].message_id,
                last_id=s[-1].message_id,
                groups_count=len(self._groups.get(stream, {})),
            )

    def trim(self, stream: str, max_len: int) -> int:
        """Trim oldest messages from stream."""
        with self._lock:
            if stream not in self._streams:
                return 0
            cur_len = len(self._streams[stream])
            if cur_len > max_len:
                evicted = cur_len - max_len
                del self._streams[stream][:evicted]
                return evicted
            return 0

    def is_connected(self) -> bool:
        """Always True for in-memory broker."""
        return self._connected

    def reset(self) -> None:
        """Clear all streams and groups (used in test teardown)."""
        with self._lock:
            self._streams.clear()
            self._groups.clear()
            self._sequence_counter = 0
