"""NETDEFY — Phase 6 Streaming Component Unit Tests.

Verifies schemas, validation invariants, deduplication, in-memory broker,
backpressure, retry logic, dead-letter routing, adaptive baseline safeguards,
and SIEM serializers (CEF, STIX, TAXII).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from netdefy.integrations.cef import CEFSerializer
from netdefy.integrations.stix import STIXSerializer
from netdefy.integrations.taxii import TAXIIClientInterface
from netdefy.streaming.adaptive_baseline import AdaptiveBaselinePolicy
from netdefy.streaming.backpressure import BackpressureController
from netdefy.streaming.dead_letter_queue import DeadLetterQueue
from netdefy.streaming.event_deduplicator import EventDeduplicator
from netdefy.streaming.event_schema import (
    FlowSummary,
    NetworkFlowEvent,
    SourceMetadata,
)
from netdefy.streaming.event_validator import EventValidator
from netdefy.streaming.in_memory_broker import InMemoryStreamBroker
from netdefy.streaming.retry_manager import RetryPolicy


@pytest.fixture
def sample_valid_event() -> NetworkFlowEvent:
    """Fixture providing a standard valid NetworkFlowEvent."""
    return NetworkFlowEvent(
        event_id="test-event-001",
        schema_version="1.0",
        event_timestamp=datetime.now(UTC) - timedelta(seconds=2),
        source=SourceMetadata(
            sensor_id="sensor-test-01",
            source_ip="192.168.1.10",
            destination_ip="10.0.0.5",
            source_port=45120,
            destination_port=443,
            protocol="TCP",
        ),
        flow=FlowSummary(
            duration=1.5,
            forward_packets=5,
            backward_packets=4,
            forward_bytes=320,
            backward_bytes=840,
        ),
        features={"Destination Port": 443.0, "Flow Duration": 1500000.0},
    )


def test_event_schema_reduced_context_detection() -> None:
    """Verify that omitting IP addresses automatically sets context_status to REDUCED_CONTEXT."""
    event = NetworkFlowEvent(
        event_timestamp=datetime.now(UTC),
        source=SourceMetadata(sensor_id="sensor-masked", destination_port=80),
    )
    assert event.context_status == "REDUCED_CONTEXT"
    assert event.source.source_ip is None
    assert event.source.destination_ip is None
    assert len(event.event_id) == 32  # deterministically generated


def test_event_schema_rejects_non_finite_features() -> None:
    """Verify that features containing NaN or Inf raise validation errors."""
    with pytest.raises(ValueError, match="non-finite"):
        NetworkFlowEvent(
            event_timestamp=datetime.now(UTC),
            source=SourceMetadata(sensor_id="sensor-01", destination_port=80),
            features={"BadFeature": float("nan")},
        )

    with pytest.raises(ValueError, match="non-finite"):
        NetworkFlowEvent(
            event_timestamp=datetime.now(UTC),
            source=SourceMetadata(sensor_id="sensor-01", destination_port=80),
            features={"BadFeature": float("inf")},
        )


def test_event_validator_temporal_boundaries(sample_valid_event: NetworkFlowEvent) -> None:
    """Verify that future timestamps exceeding clock skew are rejected."""
    validator = EventValidator(max_future_seconds=5.0)

    # Valid event
    ev, err = validator.validate_event(sample_valid_event)
    assert err is None
    assert ev is not None

    # Future event (1 minute ahead)
    future_ev = sample_valid_event.model_copy(deep=True)
    future_ev.event_timestamp = datetime.now(UTC) + timedelta(seconds=60)
    ev_bad, err_bad = validator.validate_event(future_ev)
    assert ev_bad is None
    assert err_bad is not None
    assert err_bad.error_code == "FUTURE_TIMESTAMP"


def test_event_deduplicator_lru_and_ttl() -> None:
    """Verify deduplication detects identical IDs and respects LRU bounds."""
    dedup = EventDeduplicator(capacity=3, ttl_seconds=10.0)

    assert not dedup.is_duplicate("ev1")
    assert not dedup.check_and_record("ev1")
    assert dedup.is_duplicate("ev1")
    assert dedup.check_and_record("ev1")  # duplicate

    dedup.check_and_record("ev2")
    dedup.check_and_record("ev3")
    assert dedup.size == 3

    # Adding ev4 evicts ev1
    dedup.check_and_record("ev4")
    assert dedup.size == 3
    assert not dedup.is_duplicate("ev1")  # evicted


def test_in_memory_broker_consumer_group_semantics() -> None:
    """Verify consumer groups, pending entry lists (PEL), and acknowledgements."""
    broker = InMemoryStreamBroker()
    stream = "test:stream"
    group = "test-group"

    # Publish 3 messages
    broker.publish(stream, {"data": 1})
    broker.publish(stream, {"data": 2})
    broker.publish(stream, {"data": 3})

    broker.create_consumer_group(stream, group, start_id="0")

    # Read 2 messages
    msgs = broker.read_group(stream, group, consumer="c1", count=2)
    assert len(msgs) == 2
    assert msgs[0].payload["data"] == 1
    assert msgs[1].payload["data"] == 2

    # Verify Pending Entry List has 2 entries
    pending = broker.get_pending(stream, group)
    assert len(pending) == 2
    assert pending[0].consumer == "c1"

    # Acknowledge first message
    acked = broker.ack(stream, group, [msgs[0].message_id])
    assert acked == 1

    # Verify PEL now has 1 entry
    pending_after = broker.get_pending(stream, group)
    assert len(pending_after) == 1
    assert pending_after[0].message_id == msgs[1].message_id


def test_backpressure_controller_throttling_and_rejection() -> None:
    """Verify backpressure watermarks trigger throttling and rejection."""
    broker = InMemoryStreamBroker()
    stream = "test:bp:stream"
    bp = BackpressureController(
        broker, stream=stream, low_watermark=2, high_watermark=5, max_depth=8
    )

    assert not bp.should_throttle()
    assert not bp.should_reject()

    # Fill up to 6 entries
    for i in range(6):
        broker.publish(stream, {"idx": i})

    assert bp.should_throttle()
    assert bp.get_throttle_delay_seconds() > 0.0
    assert not bp.should_reject()

    # Fill up to 9 entries
    for i in range(6, 9):
        broker.publish(stream, {"idx": i})

    assert bp.should_reject()


def test_dead_letter_queue_routing() -> None:
    """Verify failed messages are routed to DLQ stream with structured diagnostics."""
    broker = InMemoryStreamBroker()
    dlq = DeadLetterQueue(broker, dlq_stream="test:dlq")

    dlq_id = dlq.route_to_dlq(
        original_payload={"bad": "payload"},
        error_code="INVALID_PAYLOAD",
        error_message="Missing destination port",
        message_id="msg-123",
        attempt_count=3,
    )

    assert dlq_id != ""
    info = broker.get_stream_info("test:dlq")
    assert info.length == 1


def test_retry_policy_exponential_backoff() -> None:
    """Verify RetryPolicy executes attempts and fails after max retries."""
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.01, jitter=False)

    attempts = 0

    def failing_op() -> None:
        nonlocal attempts
        attempts += 1
        raise ConnectionError("Broker unreachable")

    with pytest.raises(ConnectionError):
        policy.execute_with_retry(failing_op, retryable_exceptions=(ConnectionError,))

    assert attempts == 3


def test_adaptive_baseline_anti_poisoning_gate() -> None:
    """CRITICAL: Verify suspicious traffic is blocked from updating adaptive baseline."""
    policy = AdaptiveBaselinePolicy(frozen_mean=0.50, frozen_p95=0.95)

    # 1. Suspicious known attack (must be rejected)
    assert not policy.is_eligible_for_update(
        decision="SUSPICIOUS_KNOWN",
        anomaly_score=0.98,
        supervised_label="PortScan",
    )
    assert not policy.update(
        anomaly_score=0.98, decision="SUSPICIOUS_KNOWN", supervised_label="PortScan"
    )
    assert policy.active_baseline.observations_count == 0

    # 2. Unknown anomaly (must be rejected)
    assert not policy.is_eligible_for_update(
        decision="SUSPICIOUS_UNKNOWN",
        anomaly_score=0.97,
        supervised_label="BENIGN",
    )

    # 3. Behavioral flag (must be rejected)
    assert not policy.is_eligible_for_update(
        decision="NORMAL",
        anomaly_score=0.40,
        supervised_label="BENIGN",
        has_behavioral_flag=True,
    )

    # 4. Verified normal benign flow (must be accepted)
    ok = policy.update(
        anomaly_score=0.45,
        decision="NORMAL",
        supervised_label="BENIGN",
        has_behavioral_flag=False,
    )
    assert ok is True
    assert policy.active_baseline.observations_count == 1


def test_cef_serializer_escaping_and_structure() -> None:
    """Verify ArcSight CEF syslog encoding and character escaping."""
    alert = {
        "alert_id": "alert-test-99",
        "severity": "CRITICAL",
        "decision": "SUSPICIOUS_KNOWN",
        "threat_category": "PortScan",
        "anomaly_score": 0.995,
        "source_sensor": "sensor|core=01",  # pipe in sensor
        "destination_port": 443,
        "protocol": "TCP",
        "decision_reason": "Equal sign=test, backslash\\test, newline\ntest",
        "context_status": "FULL_CONTEXT",
        "source_ip": "10.0.0.2",
        "destination_ip": "10.0.0.1",
    }

    cef = CEFSerializer.serialize_alert(alert)
    assert cef.startswith("CEF:0|NETDEFY|Network Defense Intelligence|0.1.0|")
    assert "dpt=443" in cef
    assert "cat=PortScan" in cef
    assert "Equal sign\\=test" in cef  # escaped =
    assert "backslash\\\\test" in cef  # escaped \


def test_stix_and_taxii_serialization() -> None:
    """Verify STIX 2.1 Bundle construction and TAXII envelope status."""
    alert = {
        "alert_id": "alert-stix-101",
        "severity": "HIGH",
        "decision": "SUSPICIOUS_KNOWN",
        "threat_category": "PortScan",
        "anomaly_score": 0.985,
        "destination_port": 80,
        "protocol": "TCP",
        "context_status": "FULL_CONTEXT",
    }

    bundle = STIXSerializer.serialize_alert_to_bundle(alert)
    assert bundle["type"] == "bundle"
    assert len(bundle["objects"]) >= 3

    # Check TAXII preparation
    taxii = TAXIIClientInterface()
    status = taxii.publish_bundle_to_collection("collection-alerts", bundle)
    assert status["status"] == "pending"
    assert status["total_count"] == len(bundle["objects"])
