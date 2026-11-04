"""Hamtayar FastAPI composition entry point.

Run: uv run uvicorn apps.main:app --host 127.0.0.1 --port 8000
"""

from collections.abc import Sequence

from fastapi import FastAPI

from apps.api.health import ReadinessCheck, router as health_router
from apps.document_ingestion.api.v1.jobs import router as ingestion_router
from apps.retrieval.api.v1.answers import router as answer_router
from apps.bootstrap import BootstrapRegistry
from apps.core.config import Settings
from apps.core.exceptions import register_exception_handlers
from apps.core.lifespan import create_lifespan
from apps.core.observability import (
    RequestContextMiddleware,
    TelemetryHooks,
    configure_logging,
)
from apps.orchestration.execution import get_runtime_registry


def create_app(
    *,
    settings: Settings | None = None,
    registry: BootstrapRegistry | None = None,
    readiness_checks: Sequence[ReadinessCheck] = (),
    telemetry_hooks: TelemetryHooks | None = None,
) -> FastAPI:
    """Build an isolated app, with swappable resources and checks for tests."""
    configure_logging()

    effective_registry = registry if registry is not None else get_runtime_registry()
    app = FastAPI(
        title="Hamtayar", 
        lifespan=create_lifespan(
            settings=settings, 
            registry=effective_registry
        )
    )
    app.state.readiness_checks = tuple(readiness_checks)

    app.include_router(health_router)
    app.include_router(ingestion_router)
    app.include_router(answer_router)
    # Future ingestion/retrieval routers must be registered here as they mature.
    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware, hooks=telemetry_hooks)
    return app


app = create_app()
