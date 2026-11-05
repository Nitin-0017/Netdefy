"""NETDEFY — Event Validation & Quality Enforcement Engine (Phase 6).

Enforces schema contracts, temporal bounds, numeric ranges, and model feature
integrity before network events are admitted to the message broker.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from netdefy.streaming.event_schema import (
    IngestionErrorDetail,
    NetworkFlowEvent,
)

logger = logging.getLogger(__name__)


class EventValidationError(Exception):
    """Custom exception raised when event validation fails."""

    def __init__(self, error_code: str, message: str, event_id: str | None = None) -> None:
        self.error_code = error_code
        self.message = message
        self.event_id = event_id
        super().__init__(f"[{error_code}] {message}")


class EventValidator:
    """Validates raw dictionaries or Pydantic instances for ingestion admission."""

    def __init__(
        self,
        required_features: list[str] | None = None,
        max_future_seconds: float = 10.0,
        max_age_days: float = 365.0,
        allow_historical: bool = True,
        enforce_feature_completeness: bool = False,
    ) -> None:
        self.required_features = set(required_features) if required_features else set()
        self.max_future_seconds = max_future_seconds
        self.max_age_days = max_age_days
        self.allow_historical = allow_historical
        self.enforce_feature_completeness = enforce_feature_completeness

    def validate_dict(
        self, data: dict[str, Any]
    ) -> tuple[NetworkFlowEvent | None, IngestionErrorDetail | None]:
        """Validate an unparsed JSON/dictionary payload against schema and bounds."""
        try:
            event = NetworkFlowEvent.model_validate(data)
        except ValidationError as e:
            msg = "; ".join(f"{err['loc']}: {err['msg']}" for err in e.errors()[:3])
            return None, IngestionErrorDetail(
                event_id=data.get("event_id"),
                error_code="INVALID_SCHEMA",
                message=f"Schema validation failed: {msg}",
            )
        except Exception as e:
            return None, IngestionErrorDetail(
                event_id=data.get("event_id"),
                error_code="INVALID_PAYLOAD",
                message=f"Malformed event dictionary: {e}",
            )

        return self.validate_event(event)

    def validate_event(
        self, event: NetworkFlowEvent
    ) -> tuple[NetworkFlowEvent | None, IngestionErrorDetail | None]:
        """Verify temporal, feature, and boundary invariants on a parsed NetworkFlowEvent."""
        now = datetime.now(UTC)

        # Ensure event_timestamp is timezone-aware
        ts = event.event_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        # 1. Temporal bounds check: Future timestamp
        if (ts - now).total_seconds() > self.max_future_seconds:
            return None, IngestionErrorDetail(
                event_id=event.event_id,
                error_code="FUTURE_TIMESTAMP",
                message=(
                    f"Event timestamp {ts.isoformat()} is {(ts - now).total_seconds():.1f}s "
                    f"in the future (max allowed clock skew: {self.max_future_seconds}s)"
                ),
            )

        # 2. Temporal bounds check: Stale timestamp
        if not self.allow_historical and (now - ts) > timedelta(days=self.max_age_days):
            return None, IngestionErrorDetail(
                event_id=event.event_id,
                error_code="STALE_TIMESTAMP",
                message=f"Event timestamp {ts.isoformat()} exceeds maximum age of {self.max_age_days} days",
            )

        # 3. Numeric bounds validation
        if not (0 <= event.source.destination_port <= 65535):
            return None, IngestionErrorDetail(
                event_id=event.event_id,
                error_code="INVALID_PORT",
                message=f"Destination port {event.source.destination_port} out of range [0, 65535]",
            )

        if event.flow.duration < 0.0:
            return None, IngestionErrorDetail(
                event_id=event.event_id,
                error_code="INVALID_DURATION",
                message=f"Negative flow duration: {event.flow.duration}",
            )

        # 4. Feature completeness validation
        if self.enforce_feature_completeness and self.required_features:
            missing = self.required_features - set(event.features.keys())
            if missing:
                return None, IngestionErrorDetail(
                    event_id=event.event_id,
                    error_code="MISSING_FEATURES",
                    message=f"Missing {len(missing)} required model features (e.g. {sorted(missing)[:3]})",
                )

        # 5. Non-finite values check
        for fname, fval in event.features.items():
            if not math.isfinite(fval):
                return None, IngestionErrorDetail(
                    event_id=event.event_id,
                    error_code="INVALID_FEATURE_VALUES",
                    message=f"Feature '{fname}' contains non-finite value: {fval}",
                )

        return event, None
