"""NETDEFY — Health and Readiness Probes (Phase 6)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from netdefy.api.dependencies import get_broker, get_db_session, get_hybrid_pipeline
from netdefy.api.schemas import HealthResponse, ReadinessResponse
from netdefy.streaming.broker_interface import MessageBroker

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness probe indicating whether the API process is alive."""
    return HealthResponse(status="ok", version="0.1.0", timestamp=datetime.now(UTC))


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check(
    broker: MessageBroker = Depends(get_broker),
    db: Session = Depends(get_db_session),
) -> ReadinessResponse:
    """Readiness probe verifying database connectivity, broker health, and model availability."""
    broker_ok = broker.is_connected()

    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    pipeline = get_hybrid_pipeline()
    models_ok = pipeline is not None

    all_ready = broker_ok and db_ok and models_ok
    status_val: Literal["ready", "not_ready"] = "ready" if all_ready else "not_ready"

    return ReadinessResponse(
        status=status_val,
        broker_connected=broker_ok,
        database_connected=db_ok,
        models_loaded=models_ok,
        timestamp=datetime.now(UTC),
        details={
            "broker_type": type(broker).__name__,
            "database_dialect": db.bind.dialect.name if db.bind else "unknown",
            "feature_count": len(pipeline.feature_names) if pipeline else 0,
        },
    )
