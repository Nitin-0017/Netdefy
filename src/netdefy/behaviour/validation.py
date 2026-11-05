"""NETDEFY — Temporal Validation & Leakage Prevention.

Enforces strict chronological discipline, verifies sequence monotonicity, bounds
out-of-order jitter, and guarantees zero temporal leakage between train and test windows.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np

from netdefy.behaviour.schema import NetworkEvent

logger = logging.getLogger(__name__)


class TemporalValidationError(ValueError):
    """Raised when temporal constraints or leakage checks are violated."""


class TemporalValidator:
    """Rigorous validator ensuring temporal integrity and causality in network traffic streams."""

    @staticmethod
    def validate_monotonicity(
        timestamps: Sequence[float],
        max_allowed_backward_seconds: float = 0.0,
    ) -> bool:
        """Validate whether a timestamp sequence is monotonic or within out-of-order tolerance.

        Args:
            timestamps: Sequence of Unix timestamps in seconds.
            max_allowed_backward_seconds: Maximum tolerable backwards jump due to network jitter.

        Returns:
            True if valid.

        Raises:
            TemporalValidationError: If any timestamp jumps backward beyond tolerance.
        """
        if len(timestamps) < 2:
            return True

        arr = np.asarray(timestamps, dtype=np.float64)
        deltas = np.diff(arr)
        min_delta = float(np.min(deltas))

        if min_delta < -max_allowed_backward_seconds:
            idx = int(np.argmin(deltas))
            raise TemporalValidationError(
                f"Temporal monotonicity violation at index {idx + 1}: "
                f"timestamp {arr[idx + 1]} is {abs(deltas[idx]):.3f}s earlier than previous {arr[idx]} "
                f"(tolerance: {max_allowed_backward_seconds}s)"
            )
        return True

    @staticmethod
    def check_temporal_leakage(
        train_timestamps: Sequence[float],
        test_timestamps: Sequence[float],
    ) -> bool:
        """Verify that training timestamps strictly precede evaluation timestamps.

        Args:
            train_timestamps: Timestamps from training set.
            test_timestamps: Timestamps from evaluation/test set.

        Returns:
            True if chronological separation is strictly preserved.

        Raises:
            TemporalValidationError: If temporal leakage is detected.
        """
        if len(train_timestamps) == 0 or len(test_timestamps) == 0:
            return True

        max_train = float(np.max(train_timestamps))
        min_test = float(np.min(test_timestamps))

        if max_train > min_test:
            overlap = max_train - min_test
            raise TemporalValidationError(
                f"Temporal leakage detected: max train timestamp ({max_train}) "
                f"exceeds min test timestamp ({min_test}) by {overlap:.3f} seconds. "
                "Causal temporal separation is violated."
            )
        return True

    @staticmethod
    def inspect_temporal_distribution(timestamps: Sequence[float]) -> dict[str, Any]:
        """Compute statistical diagnostics of temporal intervals."""
        if len(timestamps) < 2:
            return {
                "count": len(timestamps),
                "duration_seconds": 0.0,
                "negative_deltas_count": 0,
                "zero_deltas_count": 0,
                "mean_delta": 0.0,
                "min_delta": 0.0,
                "max_delta": 0.0,
            }

        arr = np.asarray(timestamps, dtype=np.float64)
        deltas = np.diff(arr)
        neg_count = int(np.sum(deltas < 0))
        zero_count = int(np.sum(deltas == 0))

        return {
            "count": len(timestamps),
            "duration_seconds": float(arr[-1] - arr[0]),
            "negative_deltas_count": neg_count,
            "zero_deltas_count": zero_count,
            "mean_delta": float(np.mean(deltas)),
            "std_delta": float(np.std(deltas)),
            "min_delta": float(np.min(deltas)),
            "max_delta": float(np.max(deltas)),
        }

    @staticmethod
    def validate_event_window(
        events: Sequence[NetworkEvent], max_window_span_seconds: float
    ) -> bool:
        """Verify that all events within a window span at most the configured window duration."""
        valid_ts = [ev.timestamp for ev in events if ev.timestamp is not None]
        if len(valid_ts) < 2:
            return True

        span = max(valid_ts) - min(valid_ts)
        if span > max_window_span_seconds + 1e-4:
            raise TemporalValidationError(
                f"Event window span ({span:.3f}s) exceeds max allowed span ({max_window_span_seconds}s)"
            )
        return True
