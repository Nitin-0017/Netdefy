"""NETDEFY — Network Event Ingestion Endpoints (Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from netdefy.api.dependencies import get_producer
from netdefy.streaming.event_schema import (
    EventBatch,
    IngestionResponse,
    NetworkFlowEvent,
)
from netdefy.streaming.producer import EventProducer

router = APIRouter(prefix="/events", tags=["Ingestion"])


@router.post("", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_single_event(
    event: NetworkFlowEvent,
    producer: EventProducer = Depends(get_producer),
) -> IngestionResponse:
    """Ingest a single network flow event into the real-time processing stream."""
    msg_id, err = producer.publish_event(event)
    if err is not None:
        if err.error_code == "DUPLICATE_EVENT":
            return IngestionResponse(
                status="REJECTED",
                accepted_count=0,
                rejected_count=1,
                errors=[err],
            )
        if err.error_code == "BACKPRESSURE_REJECTED":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=err.message,
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err.message,
        )

    assert msg_id is not None
    return IngestionResponse(
        status="ACCEPTED",
        accepted_count=1,
        rejected_count=0,
        event_ids=[event.event_id],
    )


@router.post("/batch", response_model=IngestionResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_event_batch(
    batch: EventBatch,
    producer: EventProducer = Depends(get_producer),
) -> IngestionResponse:
    """Ingest a micro-batch of network flow events atomically."""
    resp = producer.publish_batch(batch.events)
    return resp
