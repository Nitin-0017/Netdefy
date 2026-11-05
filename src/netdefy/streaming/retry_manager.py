"""NETDEFY — Retry Manager & Transient Fault Handling (Phase 6).

Implements bounded exponential backoff with jitter for transient broker,
database, and network failures.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryPolicy:
    """Configurable exponential backoff policy."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.1,
        max_delay_seconds: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter = jitter

    def compute_delay(self, attempt: int) -> float:
        """Compute delay for a given attempt index (0-indexed)."""
        delay = float(self.base_delay_seconds * (2**attempt))
        if self.jitter:
            delay += float(random.uniform(0.0, self.base_delay_seconds))
        return float(min(delay, self.max_delay_seconds))

    def execute_with_retry(
        self,
        operation: Callable[[], T],
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
        operation_name: str = "operation",
    ) -> T:
        """Execute callable with bounded exponential backoff."""
        last_exception: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                return operation()
            except retryable_exceptions as e:
                last_exception = e
                if attempt == self.max_attempts - 1:
                    logger.error(
                        "Exhausted %d retry attempts for %s: %s",
                        self.max_attempts,
                        operation_name,
                        e,
                    )
                    raise

                delay = self.compute_delay(attempt)
                logger.warning(
                    "Retry %d/%d for %s after %.3fs: %s",
                    attempt + 1,
                    self.max_attempts,
                    operation_name,
                    delay,
                    e,
                )
                time.sleep(delay)

        assert last_exception is not None
        raise last_exception
