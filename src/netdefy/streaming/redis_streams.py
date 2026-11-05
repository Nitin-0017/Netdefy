"""NETDEFY — Redis Streams Broker Adapter (Phase 6).

Implements the MessageBroker interface using Redis Streams for high-throughput,
low-latency production and container deployments.
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

from netdefy.streaming.broker_interface import (
    MessageBroker,
    PendingMessageInfo,
    StreamInfo,
    StreamMessage,
)

logger = logging.getLogger(__name__)

try:
    import redis
    from redis.exceptions import ResponseError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None  # type: ignore[assignment]
    ResponseError = Exception  # type: ignore[misc, assignment]


class RedisStreamsBroker(MessageBroker):
    """Production message broker backed by Redis Streams."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        client: Any = None,
        decode_responses: bool = True,
    ) -> None:
        if not REDIS_AVAILABLE:
            raise ImportError(
                "The 'redis' package is required for RedisStreamsBroker. Install it via 'uv add redis'."
            )

        if client is not None:
            self.client = client
        else:
            self.client = redis.Redis.from_url(redis_url, decode_responses=decode_responses)

    def publish(
        self,
        stream: str,
        payload: dict[str, Any],
        max_len: int | None = None,
    ) -> str:
        """Publish event dictionary serialized as JSON string into stream."""
        entry = {"payload": json.dumps(payload)}
        kwargs: dict[str, Any] = {}
        if max_len is not None:
            kwargs["maxlen"] = max_len
            kwargs["approximate"] = True

        msg_id: str = self.client.xadd(stream, entry, **kwargs)
        return msg_id

    def publish_batch(
        self,
        stream: str,
        payloads: list[dict[str, Any]],
        max_len: int | None = None,
    ) -> list[str]:
        """Publish batch of events using a Redis pipeline."""
        pipe = self.client.pipeline(transaction=False)
        kwargs: dict[str, Any] = {}
        if max_len is not None:
            kwargs["maxlen"] = max_len
            kwargs["approximate"] = True

        for p in payloads:
            pipe.xadd(stream, {"payload": json.dumps(p)}, **kwargs)

        res = pipe.execute()
        return [str(mid) for mid in res]

    def create_consumer_group(
        self,
        stream: str,
        group: str,
        start_id: str = "$",
        make_stream: bool = True,
    ) -> None:
        """Create consumer group, creating stream if needed."""
        try:
            self.client.xgroup_create(stream, group, id=start_id, mkstream=make_stream)
        except ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug("Consumer group '%s' already exists on stream '%s'", group, stream)
            else:
                raise

    def read_group(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 0,
    ) -> list[StreamMessage]:
        """Read new messages (ID '>') for consumer group."""
        streams = {stream: ">"}
        raw_res = self.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams=streams,
            count=count,
            block=block_ms if block_ms > 0 else None,
        )

        messages: list[StreamMessage] = []
        if not raw_res:
            return messages

        for stream_name, entries in raw_res:
            s_name = stream_name if isinstance(stream_name, str) else stream_name.decode("utf-8")
            for entry_id, field_dict in entries:
                mid = entry_id if isinstance(entry_id, str) else entry_id.decode("utf-8")
                raw_payload = field_dict.get("payload", "{}")
                if isinstance(raw_payload, bytes):
                    raw_payload = raw_payload.decode("utf-8")
                try:
                    payload = json.loads(raw_payload)
                except Exception:
                    payload = {"raw": raw_payload}

                ts_ms = 0
                if "-" in mid:
                    with contextlib.suppress(ValueError):
                        ts_ms = int(mid.split("-")[0])

                messages.append(
                    StreamMessage(
                        message_id=mid,
                        stream=s_name,
                        payload=payload,
                        timestamp_ms=ts_ms,
                        delivery_count=1,
                    )
                )

        return messages

    def ack(self, stream: str, group: str, message_ids: list[str]) -> int:
        """Acknowledge messages in consumer group."""
        if not message_ids:
            return 0
        return int(self.client.xack(stream, group, *message_ids))

    def get_pending(
        self,
        stream: str,
        group: str,
        count: int = 50,
    ) -> list[PendingMessageInfo]:
        """Fetch pending message details from PEL."""
        try:
            raw_pending = self.client.xpending_range(stream, group, min="-", max="+", count=count)
        except Exception as e:
            logger.warning("Error fetching pending entries: %s", e)
            return []

        pending: list[PendingMessageInfo] = []
        for item in raw_pending:
            mid = (
                item["message_id"]
                if isinstance(item["message_id"], str)
                else item["message_id"].decode("utf-8")
            )
            c_name = (
                item["consumer"]
                if isinstance(item["consumer"], str)
                else item["consumer"].decode("utf-8")
            )
            idle = int(item["idle"])
            del_count = int(item["delivered"])
            pending.append(
                PendingMessageInfo(
                    message_id=mid,
                    consumer=c_name,
                    idle_time_ms=idle,
                    delivery_count=del_count,
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
        """Claim idle pending messages from PEL."""
        if not message_ids:
            return []

        raw_claimed = self.client.xclaim(stream, group, consumer, min_idle_time_ms, message_ids)
        claimed: list[StreamMessage] = []
        for entry_id, field_dict in raw_claimed:
            mid = entry_id if isinstance(entry_id, str) else entry_id.decode("utf-8")
            raw_payload = field_dict.get("payload", "{}")
            if isinstance(raw_payload, bytes):
                raw_payload = raw_payload.decode("utf-8")
            try:
                payload = json.loads(raw_payload)
            except Exception:
                payload = {"raw": raw_payload}

            claimed.append(
                StreamMessage(
                    message_id=mid,
                    stream=stream,
                    payload=payload,
                    delivery_count=2,
                )
            )
        return claimed

    def get_stream_info(self, stream: str) -> StreamInfo:
        """Fetch stream depth and boundary IDs."""
        try:
            info = self.client.xinfo_stream(stream)
            first_id = info.get("first-entry", [None])[0] if info.get("first-entry") else None
            last_id = info.get("last-entry", [None])[0] if info.get("last-entry") else None
            return StreamInfo(
                stream=stream,
                length=int(info.get("length", 0)),
                first_id=str(first_id) if first_id else None,
                last_id=str(last_id) if last_id else None,
                groups_count=int(info.get("groups", 0)),
            )
        except Exception:
            return StreamInfo(stream=stream, length=0)

    def trim(self, stream: str, max_len: int) -> int:
        """Trim stream entries."""
        return int(self.client.xtrim(stream, maxlen=max_len, approximate=True))

    def is_connected(self) -> bool:
        """Check Redis connectivity via PING."""
        try:
            return bool(self.client.ping())
        except Exception:
            return False
