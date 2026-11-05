"""NETDEFY — Micro-Batch Stream Aggregator (Phase 6).

Buffers streaming network events into micro-batches for vectorized model inference
and bulk database persistence.
"""

from __future__ import annotations

import logging
import time

from netdefy.streaming.broker_interface import StreamMessage

logger = logging.getLogger(__name__)


class MicroBatchAggregator:
    """Aggregates individual stream messages into bounded micro-batches."""

    def __init__(self, max_batch_size: int = 64, max_wait_ms: int = 50) -> None:
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self._buffer: list[StreamMessage] = []
        self._first_arrival_t: float = 0.0

    def add(self, msg: StreamMessage) -> bool:
        """Add message to buffer. Returns True if batch is ready to flush."""
        if not self._buffer:
            self._first_arrival_t = time.time()

        self._buffer.append(msg)
        return len(self._buffer) >= self.max_batch_size

    def is_expired(self) -> bool:
        """Returns True if the current batch has waited past max_wait_ms."""
        if not self._buffer:
            return False
        elapsed_ms = (time.time() - self._first_arrival_t) * 1000.0
        return elapsed_ms >= self.max_wait_ms

    def flush(self) -> list[StreamMessage]:
        """Drain and return buffered messages."""
        batch = self._buffer
        self._buffer = []
        self._first_arrival_t = 0.0
        return batch

    @property
    def size(self) -> int:
        return len(self._buffer)
