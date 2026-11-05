"""NETDEFY — Stream Status & Operational Metrics Endpoints (Phase 6)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from netdefy.api.dependencies import get_broker, get_metrics, get_producer
from netdefy.api.schemas import StreamStatusResponse
from netdefy.streaming.broker_interface import MessageBroker
from netdefy.streaming.metrics import StreamMetrics
from netdefy.streaming.producer import EventProducer

router = APIRouter(tags=["Streaming & Observability"])


@router.get("/stream/status", response_model=StreamStatusResponse)
def get_stream_status(
    broker: MessageBroker = Depends(get_broker),
    producer: EventProducer = Depends(get_producer),
    metrics: StreamMetrics = Depends(get_metrics),
) -> StreamStatusResponse:
    """Expose queue depth, consumer groups, backpressure status, and counters."""
    stream_info = broker.get_stream_info("netdefy:events:stream")
    bp_status = producer.backpressure.get_status()
    summary = metrics.get_summary()
    c = summary["counters"]

    return StreamStatusResponse(
        stream="netdefy:events:stream",
        queue_depth=stream_info.length,
        groups_count=stream_info.groups_count,
        backpressure_active=bp_status["throttling"],
        rejection_active=bp_status["rejecting"],
        uptime_seconds=summary["uptime_seconds"],
        rss_memory_mb=summary["rss_memory_mb"],
        events_received=c["events_received"],
        events_accepted=c["events_accepted"],
        events_processed=c["events_processed"],
        alerts_generated=c["alerts_generated"],
        alerts_persisted=c["alerts_persisted"],
    )


@router.get("/metrics", response_model=None)
def get_metrics_endpoint(
    format_type: str = Query(default="json", alias="format"),
    metrics: StreamMetrics = Depends(get_metrics),
) -> Response | dict[str, Any]:
    """Expose operational latency and throughput metrics in JSON or Prometheus format."""
    if format_type.lower() == "prometheus":
        prom_text = metrics.to_prometheus_format()
        return Response(content=prom_text, media_type="text/plain; version=0.0.4")

    return metrics.get_summary()
