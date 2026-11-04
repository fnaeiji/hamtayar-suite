"""Local JSON logging, request correlation and no-op telemetry hooks.

This module deliberately does not require an external telemetry service or SDK.
"""

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter
from typing import Protocol
from uuid import UUID, uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send


_request_id: ContextVar[str | None] = ContextVar("hamtayar_request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Only serialize a controlled whitelist of fields (never request bodies)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }
        for key in ("method", "route", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Initialize Hamtayar's logger once without altering the root logger."""
    logger = logging.getLogger("hamtayar")
    if not any(getattr(handler, "_hamtayar_json_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._hamtayar_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class TelemetryHooks(Protocol):
    """Application-facing integration points; future OTel adapters implement these."""

    def on_request_start(self, *, request_id: str, method: str) -> None: ...

    def on_request_end(self, *, request_id: str, status_code: int, duration_ms: float) -> None: ...


class NoOpTelemetryHooks:
    def on_request_start(self, *, request_id: str, method: str) -> None:
        pass

    def on_request_end(self, *, request_id: str, status_code: int, duration_ms: float) -> None:
        pass


class RequestContextMiddleware:
    """Pure ASGI middleware to retain ContextVar propagation across awaits."""

    def __init__(self, app: ASGIApp, hooks: TelemetryHooks | None = None) -> None:
        self.app = app
        self.hooks = hooks if hooks is not None else NoOpTelemetryHooks()
        self.logger = logging.getLogger("hamtayar.http")

    @staticmethod
    def _new_request_id(scope: Scope) -> str:
        for key, value in scope.get("headers", []):
            if key.lower() == b"x-request-id":
                try:
                    return str(UUID(value.decode("ascii")))
                except (ValueError, UnicodeDecodeError):
                    break
        return str(uuid4())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = self._new_request_id(scope)
        scope.setdefault("state", {})["request_id"] = rid
        token = _request_id.set(rid)
        start = perf_counter()
        method = scope.get("method", "UNKNOWN")
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"]
                headers.append((b"x-request-id", rid.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            self._run_hook(self.hooks.on_request_start, request_id=rid, method=method)
            await self.app(scope, receive, send_with_id)
        except Exception:
            status_code = 500
            # One entry with a request ID; never log the raw exception message.
            self.logger.error("unhandled_request_exception", extra={"request_id": rid})
            raise
        finally:
            duration_ms = round((perf_counter() - start) * 1000, 3)
            route = scope.get("route")
            route_template = getattr(route, "path", "<unmatched>")
            self.logger.info(
                "request_completed",
                extra={
                    "request_id": rid, "method": method,
                    "route": route_template, "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            self._run_hook(
                self.hooks.on_request_end,
                request_id=rid, status_code=status_code, duration_ms=duration_ms,
            )
            _request_id.reset(token)

    def _run_hook(self, fn, **kwargs) -> None:
        try:
            fn(**kwargs)
        except Exception:
            # Instrumentation must not alter the application response.
            self.logger.warning("telemetry_hook_failed")
