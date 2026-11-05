"""NETDEFY — Event Producer & Ingestion Gateway (Phase 6).

Admit, validate, deduplicate, and publish network flow telemetry to the message broker.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any, Literal

from netdefy.streaming.backpressure import BackpressureController
from netdefy.streaming.broker_interface import MessageBroker
from netdefy.streaming.event_deduplicator import EventDeduplicator
from netdefy.streaming.event_schema import (
    IngestionErrorDetail,
    IngestionResponse,
    NetworkFlowEvent,
)
from netdefy.streaming.event_validator import EventValidator
from netdefy.streaming.metrics import StreamMetrics

logger = logging.getLogger(__name__)


class EventProducer:
    """Gateway service publishing validated network events into the broker stream."""

    def __init__(
        self,
        broker: MessageBroker,
        stream: str = "netdefy:events:stream",
        validator: EventValidator | None = None,
        deduplicator: EventDeduplicator | None = None,
        backpressure: BackpressureController | None = None,
        metrics: StreamMetrics | None = None,
    ) -> None:
        self.broker = broker
        self.stream = stream
        self.validator = validator or EventValidator()
        self.deduplicator = deduplicator or EventDeduplicator()
        self.backpressure = backpressure or BackpressureController(broker, stream=stream)
        self.metrics = metrics or StreamMetrics()

    def publish_event(
        self, raw_data: dict[str, Any] | NetworkFlowEvent
    ) -> tuple[str | None, IngestionErrorDetail | None]:
        """Validate, deduplicate, and publish a single flow event."""
        start_t = time.time()

        # Check backpressure saturation
        if self.backpressure.should_reject():
            self.metrics.record_ingestion(accepted=False)
            return None, IngestionErrorDetail(
                error_code="BACKPRESSURE_REJECTED",
                message="Broker stream is saturated; please back off and retry later",
            )

        # Apply throttle delay if approaching high watermark
        throttle_delay = self.backpressure.get_throttle_delay_seconds()
        if throttle_delay > 0:
            time.sleep(throttle_delay)

        # Validate event
        if isinstance(raw_data, NetworkFlowEvent):
            event, err = self.validator.validate_event(raw_data)
        else:
            event, err = self.validator.validate_dict(raw_data)

        if err is not None or event is None:
            self.metrics.record_ingestion(accepted=False)
            return None, err

        # Deduplicate
        if self.deduplicator.check_and_record(event.event_id):
            self.metrics.record_ingestion(accepted=False, is_duplicate=True)
            return None, IngestionErrorDetail(
                event_id=event.event_id,
                error_code="DUPLICATE_EVENT",
                message=f"Event {event.event_id} already ingested within deduplication window",
            )

        # Publish to broker
        try:
            msg_id = self.broker.publish(self.stream, event.to_stream_payload())
            latency_ms = (time.time() - start_t) * 1000.0
            self.metrics.record_ingestion(accepted=True, latency_ms=latency_ms)
            return msg_id, None
        except Exception as e:
            logger.error("Failed to publish to stream '%s': %s", self.stream, e)
            self.metrics.record_ingestion(accepted=False)
            return None, IngestionErrorDetail(
                event_id=event.event_id,
                error_code="BROKER_PUBLISH_FAILED",
                message=f"Broker error: {e}",
            )

    def publish_batch(
        self, events: Sequence[dict[str, Any] | NetworkFlowEvent]
    ) -> IngestionResponse:
        """Validate, deduplicate, and publish a batch of network flow events."""
        accepted_ids: list[str] = []
        errors: list[IngestionErrorDetail] = []

        valid_payloads: list[dict[str, Any]] = []

        for idx, item in enumerate(events):
            if isinstance(item, NetworkFlowEvent):
                ev, err = self.validator.validate_event(item)
            else:
                ev, err = self.validator.validate_dict(item)

            if err:
                err.event_index = idx
                errors.append(err)
                self.metrics.record_ingestion(accepted=False)
                continue

            assert ev is not None
            if self.deduplicator.check_and_record(ev.event_id):
                errors.append(
                    IngestionErrorDetail(
                        event_index=idx,
                        event_id=ev.event_id,
                        error_code="DUPLICATE_EVENT",
                        message="Duplicate event in batch or seen recently",
                    )
                )
                self.metrics.record_ingestion(accepted=False, is_duplicate=True)
                continue

            valid_payloads.append(ev.to_stream_payload())

        if valid_payloads:
            try:
                msg_ids = self.broker.publish_batch(self.stream, valid_payloads)
                accepted_ids.extend(msg_ids)
                for _ in msg_ids:
                    self.metrics.record_ingestion(accepted=True)
            except Exception as e:
                logger.error("Failed batch publish to stream '%s': %s", self.stream, e)
                for _ in range(len(valid_payloads)):
                    errors.append(
                        IngestionErrorDetail(
                            error_code="BROKER_BATCH_FAILED",
                            message=f"Batch publish failure: {e}",
                        )
                    )

        status_val: Literal["ACCEPTED", "PARTIALLY_ACCEPTED", "REJECTED"] = (
            "ACCEPTED" if not errors else ("PARTIALLY_ACCEPTED" if accepted_ids else "REJECTED")
        )
        return IngestionResponse(
            status=status_val,
            accepted_count=len(accepted_ids),
            rejected_count=len(errors),
            event_ids=accepted_ids,
            errors=errors,
        )
