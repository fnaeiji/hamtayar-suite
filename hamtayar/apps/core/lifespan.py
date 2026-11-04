"""FastAPI startup/shutdown glue around the application composition root."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import AsyncContextManager

from fastapi import FastAPI

from apps.bootstrap import BootstrapRegistry, bootstrap
from apps.core.config import Settings, get_settings


def create_lifespan(
    settings: Settings | None = None,
    registry: BootstrapRegistry | None = None,
) -> Callable[[FastAPI], AsyncContextManager[None]]:
    """Allow tests to inject Settings and fake factories before app startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        current_settings = settings if settings is not None else get_settings()
        async with bootstrap(current_settings, registry) as container:
            app.state.container = container
            try:
                yield
            finally:
                del app.state.container

    return lifespan
