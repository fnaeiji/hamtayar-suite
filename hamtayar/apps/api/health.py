"""Application liveness and readiness endpoints."""

import inspect
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apps.bootstrap import AppContainer

router = APIRouter(tags=["health"])
ReadinessCheck = Callable[[AppContainer], bool | Awaitable[bool]]
logger = logging.getLogger("hamtayar.health")


@router.get("/health/live")
async def live() -> dict[str, str]:
    """Is the ASGI app capable of responding? No external network calls."""
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request):
    """Is startup complete and are registered readiness checks passing?"""
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, AppContainer):
        return JSONResponse({"status": "not_ready"}, status_code=503)

    for check in getattr(request.app.state, "readiness_checks", ()):
        try:
            result = check(container)
            if inspect.isawaitable(result):
                result = await result
            if result is not True:
                return JSONResponse({"status": "not_ready"}, status_code=503)
        except Exception:
            logger.warning("readiness_check_failed")
            return JSONResponse({"status": "not_ready"}, status_code=503)

    return {"status": "ready"}
