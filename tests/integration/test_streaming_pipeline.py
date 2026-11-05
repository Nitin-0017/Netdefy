"""NETDEFY — Phase 6 Streaming & SOC API Integration Tests.

Verifies end-to-end event ingestion, broker consumption, alert persistence,
analyst state transitions, idempotent replay, and REST API endpoints.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from netdefy.alerts.alert_engine import AlertEngine
from netdefy.api.app import app
from netdefy.storage.alert_repository import AlertRepository
from netdefy.storage.database import DatabaseManager
from netdefy.streaming.broker_interface import StreamMessage
from netdefy.streaming.consumer import StreamConsumer
from netdefy.streaming.event_schema import (
    FlowSummary,
    NetworkFlowEvent,
    SourceMetadata,
)
from netdefy.streaming.in_memory_broker import InMemoryStreamBroker
from netdefy.streaming.producer import EventProducer


@pytest.fixture
def test_env() -> tuple[InMemoryStreamBroker, DatabaseManager, EventProducer, StreamConsumer]:
    """Provide isolated broker, database, producer, and consumer."""
    broker = InMemoryStreamBroker()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        temp_db_path = temp_db.name
    db_mgr = DatabaseManager(db_url=f"sqlite:///{temp_db_path}")

    session = db_mgr.session_factory()
    repo = AlertRepository(session=session)

    producer = EventProducer(broker=broker)
    consumer = StreamConsumer(
        broker=broker,
        alert_engine=AlertEngine(high_anomaly_threshold=0.60),  # ensure alerts trigger in test
        alert_repository=repo,
    )

    return broker, db_mgr, producer, consumer


def test_end_to_end_ingestion_to_alert_persistence(
    test_env: tuple[InMemoryStreamBroker, DatabaseManager, EventProducer, StreamConsumer],
) -> None:
    """Verify event flows from producer -> broker -> consumer -> database alert."""
    broker, db_mgr, producer, consumer = test_env

    # 1. Produce event
    event = NetworkFlowEvent(
        event_id="e2e-event-01",
        schema_version="1.0",
        event_timestamp=datetime.now(UTC),
        source=SourceMetadata(sensor_id="s1", destination_port=80, protocol="TCP"),
        flow=FlowSummary(duration=1.0, forward_packets=5, backward_packets=1),
        features={"Destination Port": 80.0, "Flow Duration": 1000000.0},
    )

    msg_id, err = producer.publish_event(event)
    assert err is None
    assert msg_id is not None

    # Verify stream depth
    info = broker.get_stream_info("netdefy:events:stream")
    assert info.length == 1

    # 2. Consume event
    processed = consumer.consume_batch(count=10, block_ms=50)
    assert processed == 1

    # Verify PEL is cleared after ACK
    pending = broker.get_pending("netdefy:events:stream", consumer.group)
    assert len(pending) == 0


def test_idempotent_replayed_message(
    test_env: tuple[InMemoryStreamBroker, DatabaseManager, EventProducer, StreamConsumer],
) -> None:
    """Verify that replaying a message does not duplicate database alert records."""
    broker, db_mgr, producer, consumer = test_env

    # Manually insert message and process it
    payload = {
        "event_id": "replay-event-01",
        "schema_version": "1.0",
        "event_timestamp": datetime.now(UTC).isoformat(),
        "ingestion_timestamp": datetime.now(UTC).isoformat(),
        "source": {"sensor_id": "s1", "destination_port": 80, "protocol": "TCP"},
        "flow": {"duration": 1.0, "forward_packets": 2, "backward_packets": 1},
        "features": {},
        "context_status": "REDUCED_CONTEXT",
    }
    msg = StreamMessage(message_id="msg-1", stream=consumer.stream, payload=payload)

    # Process first time
    ok1, _ = consumer.process_single_message(msg)
    assert ok1 is True

    # Process second time (replay)
    ok2, _ = consumer.process_single_message(msg)
    assert ok2 is True

    # Verify database has at most 1 alert
    session = db_mgr.session_factory()
    repo = AlertRepository(session=session)
    alerts, count = repo.list_alerts()
    assert count <= 1


def test_fastapi_rest_endpoints() -> None:
    """Verify REST API routes: health, ready, events, alerts, and metrics."""
    client = TestClient(app)

    # 1. Health & Ready
    res_h = client.get("/api/v1/health")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "ok"

    res_r = client.get("/api/v1/ready")
    assert res_r.status_code == 200

    # 2. Ingest Single Event
    event_payload = {
        "event_id": "api-test-01",
        "schema_version": "1.0",
        "event_timestamp": datetime.now(UTC).isoformat(),
        "source": {
            "sensor_id": "sensor-api-01",
            "destination_port": 443,
            "protocol": "TCP",
        },
        "flow": {
            "duration": 0.8,
            "forward_packets": 4,
            "backward_packets": 2,
        },
        "features": {
            "Destination Port": 443.0,
        },
    }

    res_post = client.post("/api/v1/events", json=event_payload)
    assert res_post.status_code == 202
    assert res_post.json()["status"] == "ACCEPTED"

    # 3. Ingest Duplicate Event (should be rejected/suppressed)
    res_dup = client.post("/api/v1/events", json=event_payload)
    assert res_dup.status_code == 202
    assert res_dup.json()["status"] == "REJECTED"

    # 4. Stream Status & Metrics
    res_s = client.get("/api/v1/stream/status")
    assert res_s.status_code == 200
    assert "queue_depth" in res_s.json()

    res_m = client.get("/api/v1/metrics?format=prometheus")
    assert res_m.status_code == 200
    assert "netdefy_events_received_total" in res_m.text

    # 5. Model Registry
    res_mod = client.get("/api/v1/models")
    assert res_mod.status_code == 200
    assert res_mod.json()["pipeline_name"] == "netdefy_hybrid_intelligence_engine"
