"""NETDEFY — Phase 6 Stream Reliability & Crash Scenario Tests.

Verifies poison pill quarantine to DLQ, consumer crash before ACK,
PEL reclamation, queue saturation rejection, and large batch handling.
"""

from __future__ import annotations

from datetime import UTC, datetime

from netdefy.streaming.backpressure import BackpressureController
from netdefy.streaming.checkpoint_manager import CheckpointManager
from netdefy.streaming.consumer import StreamConsumer
from netdefy.streaming.dead_letter_queue import DeadLetterQueue
from netdefy.streaming.event_schema import (
    NetworkFlowEvent,
    SourceMetadata,
)
from netdefy.streaming.in_memory_broker import InMemoryStreamBroker
from netdefy.streaming.producer import EventProducer


def test_poison_pill_quarantine_to_dlq() -> None:
    """Verify malformed payload is quarantined to DLQ and acknowledged from main stream."""
    broker = InMemoryStreamBroker()
    stream = "netdefy:events:stream"
    dlq_stream = "netdefy:dlq:stream"

    dlq = DeadLetterQueue(broker, dlq_stream=dlq_stream)
    consumer = StreamConsumer(broker=broker, stream=stream, dlq=dlq)

    # Publish poison pill payload (violates schema: string instead of dict)
    broker.publish(stream, {"corrupt": "not_an_event_schema"})

    processed = consumer.consume_batch(count=10, block_ms=50)
    assert processed == 0  # failed, not counted as success

    # Verify message was removed from PEL (ACKed to allow progress)
    pending = broker.get_pending(stream, consumer.group)
    assert len(pending) == 0

    # Verify DLQ received the quarantined message
    dlq_info = broker.get_stream_info(dlq_stream)
    assert dlq_info.length == 1


def test_consumer_crash_and_pel_recovery() -> None:
    """Verify unacknowledged messages left in PEL by a crashed consumer are reclaimed."""
    broker = InMemoryStreamBroker()
    stream = "netdefy:events:stream"
    group = "netdefy-engine-cg"

    # Worker 1 consumes but crashes before ACK
    broker.publish(
        stream,
        {
            "event_id": "crash-ev-01",
            "schema_version": "1.0",
            "event_timestamp": datetime.now(UTC).isoformat(),
            "source": {"sensor_id": "s1", "destination_port": 80},
        },
    )
    broker.create_consumer_group(stream, group, start_id="0")

    # Read as worker 1
    msgs = broker.read_group(stream, group, consumer="crashed-worker", count=1)
    assert len(msgs) == 1

    # Simulate worker crash (message remains in PEL unacknowledged)
    pending = broker.get_pending(stream, group)
    assert len(pending) == 1
    assert pending[0].consumer == "crashed-worker"

    # Worker 2 starts up and reclaims stale messages (min_idle_time_ms=0 for test)
    chk = CheckpointManager(broker, stream=stream, group=group, consumer_name="worker-2")
    assert len(chk.get_pending_messages()) == 1
    claimed = broker.claim_pending(
        stream, group, consumer="worker-2", min_idle_time_ms=0, message_ids=[msgs[0].message_id]
    )
    assert len(claimed) == 1
    assert claimed[0].delivery_count == 2

    # Worker 2 processes and ACKs
    broker.ack(stream, group, [msgs[0].message_id])
    pending_after = broker.get_pending(stream, group)
    assert len(pending_after) == 0


def test_queue_saturation_backpressure_rejection() -> None:
    """Verify producer strictly rejects new events when stream hits max_depth."""
    broker = InMemoryStreamBroker()
    stream = "netdefy:bp:test"
    bp = BackpressureController(
        broker, stream=stream, low_watermark=2, high_watermark=4, max_depth=5
    )
    producer = EventProducer(broker=broker, stream=stream, backpressure=bp)

    event = NetworkFlowEvent(
        event_timestamp=datetime.now(UTC),
        source=SourceMetadata(sensor_id="s1", destination_port=80),
    )

    # Fill up to max depth 5
    for i in range(5):
        broker.publish(stream, {"idx": i})

    # Next attempt should be rejected
    msg_id, err = producer.publish_event(event)
    assert msg_id is None
    assert err is not None
    assert err.error_code == "BACKPRESSURE_REJECTED"


def test_large_batch_consumption() -> None:
    """Verify consumer processes large batches without dropping telemetry."""
    broker = InMemoryStreamBroker()
    consumer = StreamConsumer(broker=broker)

    batch_size = 50
    for i in range(batch_size):
        broker.publish(
            "netdefy:events:stream",
            {
                "event_id": f"batch-test-{i:03d}",
                "schema_version": "1.0",
                "event_timestamp": datetime.now(UTC).isoformat(),
                "source": {"sensor_id": "s1", "destination_port": 80 + (i % 10)},
                "flow": {"duration": 0.5, "forward_packets": 2, "backward_packets": 1},
                "features": {},
            },
        )

    processed = consumer.consume_batch(count=batch_size, block_ms=50)
    assert processed == batch_size

    # Verify queue is drained
    pending = broker.get_pending("netdefy:events:stream", consumer.group)
    assert len(pending) == 0
