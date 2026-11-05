"""NETDEFY — API Dependency Injection Container (Phase 6).

Provides singleton instances of the message broker, database manager,
producer gateway, hybrid inference pipeline, and operational metrics.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from pathlib import Path

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from netdefy.behaviour.feature_builder import BehavioralFeatureBuilder
from netdefy.behaviour.pipeline_adapter import BehavioralHybridPipeline
from netdefy.hybrid.inference_pipeline import HybridInferencePipeline
from netdefy.storage.alert_repository import AlertRepository
from netdefy.storage.database import DatabaseManager
from netdefy.streaming.broker_interface import MessageBroker
from netdefy.streaming.consumer import StreamConsumer
from netdefy.streaming.in_memory_broker import InMemoryStreamBroker
from netdefy.streaming.metrics import StreamMetrics
from netdefy.streaming.producer import EventProducer
from netdefy.streaming.redis_streams import REDIS_AVAILABLE, RedisStreamsBroker

logger = logging.getLogger(__name__)

# Global singletons
_BROKER: MessageBroker | None = None
_DB_MANAGER: DatabaseManager | None = None
_PRODUCER: EventProducer | None = None
_METRICS: StreamMetrics | None = None
_HYBRID_PIPELINE: BehavioralHybridPipeline | None = None
_CONSUMER: StreamConsumer | None = None


def get_metrics() -> StreamMetrics:
    """Return shared StreamMetrics singleton."""
    global _METRICS
    if _METRICS is None:
        _METRICS = StreamMetrics()
    return _METRICS


def get_broker() -> MessageBroker:
    """Return shared message broker instance (Redis if connected, else In-Memory)."""
    global _BROKER
    if _BROKER is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        use_redis = os.environ.get("NETDEFY_USE_REDIS", "false").lower() in ("true", "1")
        if use_redis and REDIS_AVAILABLE:
            try:
                rb = RedisStreamsBroker(redis_url=redis_url)
                if rb.is_connected():
                    logger.info("Connected to Redis Streams broker at %s", redis_url)
                    _BROKER = rb
                else:
                    logger.warning("Redis ping failed, falling back to InMemoryStreamBroker")
                    _BROKER = InMemoryStreamBroker()
            except Exception as e:
                logger.warning(
                    "Could not initialize RedisStreamsBroker (%s), falling back to InMemoryStreamBroker",
                    e,
                )
                _BROKER = InMemoryStreamBroker()
        else:
            _BROKER = InMemoryStreamBroker()
    return _BROKER


def get_db_manager() -> DatabaseManager:
    """Return shared DatabaseManager singleton."""
    global _DB_MANAGER
    if _DB_MANAGER is None:
        db_url = os.environ.get("DATABASE_URL")
        _DB_MANAGER = DatabaseManager(db_url=db_url)
    return _DB_MANAGER


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional database session."""
    db_mgr = get_db_manager()
    yield from db_mgr.get_session()


def get_producer() -> EventProducer:
    """Return shared EventProducer singleton."""
    global _PRODUCER
    if _PRODUCER is None:
        broker = get_broker()
        metrics = get_metrics()
        _PRODUCER = EventProducer(broker=broker, metrics=metrics)
    return _PRODUCER


def get_hybrid_pipeline() -> BehavioralHybridPipeline | None:
    """Load and return BehavioralHybridPipeline if configuration and models are present."""
    global _HYBRID_PIPELINE
    if _HYBRID_PIPELINE is None:
        config_path = Path("configs") / "hybrid.yaml"
        if config_path.exists():
            try:
                hybrid_pipe = HybridInferencePipeline.from_config(config_path)
                scaler_path = Path("artifacts") / "preprocessing" / "standard_scaler.joblib"
                builder = BehavioralFeatureBuilder(
                    scaler_path=scaler_path if scaler_path.exists() else None,
                    feature_names=hybrid_pipe.feature_names,
                )
                _HYBRID_PIPELINE = BehavioralHybridPipeline(
                    hybrid_pipeline=hybrid_pipe, feature_builder=builder
                )
                logger.info("Loaded BehavioralHybridPipeline successfully.")
            except Exception as e:
                logger.warning("Could not load full hybrid pipeline: %s", e)
                _HYBRID_PIPELINE = None
    return _HYBRID_PIPELINE


def get_raw_hybrid_pipeline() -> HybridInferencePipeline | None:
    """Return the underlying HybridInferencePipeline directly for raw feature prediction."""
    beh = get_hybrid_pipeline()
    if beh is not None:
        return beh.hybrid
    config_path = Path("configs") / "hybrid.yaml"
    if config_path.exists():
        try:
            return HybridInferencePipeline.from_config(config_path)
        except Exception as e:
            logger.warning("Could not load HybridInferencePipeline: %s", e)
    return None


def get_consumer() -> StreamConsumer:
    """Return shared StreamConsumer instance."""
    global _CONSUMER
    if _CONSUMER is None:
        broker = get_broker()
        metrics = get_metrics()
        pipeline = get_hybrid_pipeline()
        db_mgr = get_db_manager()
        session = db_mgr.session_factory()
        repo = AlertRepository(session=session)
        _CONSUMER = StreamConsumer(
            broker=broker,
            pipeline=pipeline,
            alert_repository=repo,
            metrics=metrics,
        )
    return _CONSUMER


def verify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Validate API key for protected analyst endpoints."""
    required_key = os.environ.get("NETDEFY_API_KEY")
    if not required_key:
        return "anonymous_analyst"  # Auth disabled in local dev mode

    if x_api_key != required_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (X-API-Key header required)",
        )
    return "authorized_analyst"
