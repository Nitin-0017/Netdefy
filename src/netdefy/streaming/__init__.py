"""NETDEFY — Streaming & Real-Time Ingestion Engine (Phase 6)."""

from netdefy.streaming.adaptive_baseline import (
    AdaptiveBaselinePolicy,
    BaselineSnapshot,
)
from netdefy.streaming.backpressure import BackpressureController
from netdefy.streaming.batch_processor import MicroBatchAggregator
from netdefy.streaming.broker_interface import (
    MessageBroker,
    PendingMessageInfo,
    StreamInfo,
    StreamMessage,
)
from netdefy.streaming.checkpoint_manager import CheckpointManager
from netdefy.streaming.consumer import StreamConsumer
from netdefy.streaming.dead_letter_queue import DeadLetterQueue
from netdefy.streaming.event_deduplicator import EventDeduplicator
from netdefy.streaming.event_schema import (
    EventBatch,
    FlowSummary,
    IngestionErrorDetail,
    IngestionResponse,
    NetworkFlowEvent,
    SourceMetadata,
)
from netdefy.streaming.event_validator import EventValidationError, EventValidator
from netdefy.streaming.in_memory_broker import InMemoryStreamBroker
from netdefy.streaming.metrics import StreamMetrics
from netdefy.streaming.producer import EventProducer
from netdefy.streaming.redis_streams import RedisStreamsBroker
from netdefy.streaming.retry_manager import RetryPolicy

__all__ = [
    "AdaptiveBaselinePolicy",
    "BackpressureController",
    "BaselineSnapshot",
    "CheckpointManager",
    "DeadLetterQueue",
    "EventBatch",
    "EventDeduplicator",
    "EventProducer",
    "EventValidationError",
    "EventValidator",
    "FlowSummary",
    "InMemoryStreamBroker",
    "IngestionErrorDetail",
    "IngestionResponse",
    "MessageBroker",
    "MicroBatchAggregator",
    "NetworkFlowEvent",
    "PendingMessageInfo",
    "RedisStreamsBroker",
    "RetryPolicy",
    "SourceMetadata",
    "StreamConsumer",
    "StreamInfo",
    "StreamMessage",
    "StreamMetrics",
]
