"""NETDEFY — Production FastAPI Application (Phase 6).

Assembles the real-time event ingestion gateway, SOC alert management API,
model provenance registry, and operational observability routers.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from netdefy.api.dependencies import get_db_manager
from netdefy.api.routes import (
    alerts,
    detection,
    events,
    health,
    models,
    playground,
    research,
    stream,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle orchestration."""
    logger.info("Initializing NETDEFY API and database connections...")
    # Initialize database tables
    db_mgr = get_db_manager()
    logger.info("Database schema verified on %s", db_mgr.engine.url)
    yield
    logger.info("Shutting down NETDEFY API services...")


def create_app() -> FastAPI:
    """Application factory for NETDEFY REST API."""
    app = FastAPI(
        title="NETDEFY Network Defense Intelligence API",
        description="Production SOC Threat Detection, Stream Ingestion & Observability Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Timing and Request ID Middleware
    @app.middleware("http")
    async def add_process_time_and_request_id(
        request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.time()
        response: Response = await call_next(request)
        process_time_ms = (time.time() - start_time) * 1000.0
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
        return response

    # 3. Include API v1 Routers
    api_v1_prefix = "/api/v1"
    app.include_router(health.router, prefix=api_v1_prefix)
    app.include_router(events.router, prefix=api_v1_prefix)
    app.include_router(alerts.router, prefix=api_v1_prefix)
    app.include_router(models.router, prefix=api_v1_prefix)
    app.include_router(stream.router, prefix=api_v1_prefix)
    app.include_router(research.router, prefix=api_v1_prefix)
    app.include_router(playground.router, prefix=api_v1_prefix)
    app.include_router(detection.router, prefix=api_v1_prefix)

    # 4. Mount Frontend Static Files if built
    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount(
            "/workbench", StaticFiles(directory=str(frontend_dist), html=True), name="workbench"
        )

    # Top-level root probe
    @app.get("/", tags=["Root"])
    def root() -> dict[str, str]:
        return {
            "name": "NETDEFY",
            "tagline": "Detect Anomalies. Understand Network Behaviour.",
            "version": "0.1.0",
            "docs": "/docs",
            "workbench": "/workbench" if frontend_dist.exists() else "not built",
        }

    return app


app = create_app()
