"""Local JSON logging, request correlation and no-op telemetry hooks.

This module deliberately does not require an external telemetry service or SDK.
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
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
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
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
        except Exception:  # noqa: BLE001 - telemetry must not affect requests
            # Instrumentation must not alter the application response.
            self.logger.warning("telemetry_hook_failed")


class PipelineTrace:
    """Local, content-free JSONL events plus a self-contained HTML timeline."""

    def __init__(self, path, *, run_id: str, workflow: str, echo=False):
        from pathlib import Path
        self.path = Path(path)
        self.error = None
        self.run_id, self.workflow, self.echo = run_id, workflow, echo
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._unavailable()

    def record(self, event: str, **fields):
        from datetime import datetime
        allowed = {'node', 'task_id', 'checkpoint_id', 'step', 'next', 'status',
                   'duration_ms', 'error_code', 'retryable', 'chunk_count', 'indexed_count',
                   'result_count', 'evidence_count', 'published'}
        entry = {'time': datetime.now(UTC).isoformat(), 'run_id': self.run_id,
                 'workflow': self.workflow, 'event': event,
                 **{key: value for key, value in fields.items() if key in allowed}}
        line = json.dumps(entry, ensure_ascii=False)
        if self.error is not None:
            return
        try:
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(line + '\n')
            if self.echo:
                print(line, flush=True)
        except OSError:
            self._unavailable()

    def _unavailable(self):
        if self.error is None:
            logging.getLogger("hamtayar.pipeline_trace").warning("local_trace_unavailable")
        self.error = "local_trace_unavailable"

    def render(self):
        try:
            return self._render()
        except (OSError, ValueError):
            self._unavailable()
            return None

    def _render(self):
        from html import escape
        entries = [json.loads(line) for line in self.path.read_text(encoding='utf-8').splitlines() if line.strip()]
        rows = []
        for item in entries:
            details = {k: v for k, v in item.items() if k not in ('time', 'run_id', 'workflow', 'event', 'node')}
            cells = [item['time'], item['event'], item.get('node', ''), json.dumps(details, ensure_ascii=False)]
            rows.append('<tr>' + ''.join('<td>' + escape(str(cell)) + '</td>' for cell in cells) + '</tr>')
        page = '<!doctype html><meta charset="utf-8"><title>Hamtayar pipeline trace</title>'
        page += '<style>body{font:15px system-ui;margin:32px;background:#f5f7fb;color:#172235}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #ddd;text-align:left}td:last-child{font:13px monospace}tr:hover{background:#eef4ff}</style>'
        page += '<h1>Hamtayar · ' + escape(self.workflow) + '</h1><p>Run: ' + escape(self.run_id) + '</p>'
        page += '<p>Search this timeline with Ctrl+F. Document text, questions, vectors and credentials are excluded.</p>'
        page += '<table><tr><th>UTC time</th><th>Event</th><th>Node</th><th>Details</th></tr>' + ''.join(rows) + '</table>'
        output = self.path.with_suffix('.html')
        output.write_text(page, encoding='utf-8')
        return output


def state_summary(values):
    """Allowlist operational metadata; never serialize document/query payloads."""
    summary = {key: values[key] for key in ('status', 'chunk_count', 'indexed_count', 'published') if key in values}
    for key, label in (('results', 'result_count'), ('evidence', 'evidence_count')):
        if isinstance(values.get(key), list):
            summary[label] = len(values[key])
    return summary
