"""TASK-03 acceptance tests: app factory, health, errors and observability."""

import io
import json
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.bootstrap import BootstrapRegistry
from apps.core.config import Settings
from apps.core.exceptions import ApplicationError
from apps.core.observability import JsonFormatter, get_request_id
from apps.main import create_app
from packages.contracts.errors import ErrorCode


def test_app_starts_and_health_endpoints_are_correct():
    app = create_app(settings=Settings(environment="test", _env_file=None))
    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
    assert live.status_code == 200 and live.json() == {"status": "alive"}
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}
    assert UUID(live.headers["x-request-id"])
    assert UUID(ready.headers["x-request-id"])
    assert "container" not in vars(app.state).get("_state", {})


def test_readiness_returns_503_on_failed_or_raising_check():
    cfg = Settings(environment="test", _env_file=None)
    app = create_app(settings=cfg, readiness_checks=[lambda container: False])
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}
        assert client.get("/health/live").status_code == 200

    def broken(container):
        raise OSError("secret backend address")

    app = create_app(settings=cfg, readiness_checks=[broken])
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "secret" not in response.text


def test_uninitialized_application_is_not_ready():
    app = create_app(settings=Settings(environment="test", _env_file=None))
    # TestClient without a `with` context has not entered the lifespan.
    client = TestClient(app)
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    client.close()


def test_error_envelope_status_and_no_secret_leakage():
    app = create_app(settings=Settings(environment="test", _env_file=None))

    @app.get("/sample/{number}")
    def sample(number: int):
        return {"number": number}

    @app.get("/protected")
    def protected():
        raise ApplicationError(code=ErrorCode.ACCESS_DENIED, message="Access denied", status_code=403)

    @app.get("/broken")
    def broken():
        raise RuntimeError("PRIVATE_SECRET_DO_NOT_RETURN")

    @app.get("/forbidden-http")
    def forbidden_http():
        raise HTTPException(status_code=403, detail="PRIVATE_SECRET_DO_NOT_RETURN")

    with TestClient(app, raise_server_exceptions=False) as client:
        for path, expected_status, expected_code in [
            ("/missing-route", 404, "http_error"),
            ("/sample/not-an-int", 422, "validation_error"),
            ("/protected", 403, "access_denied"),
            ("/broken", 500, "processing_failed"),
            ("/forbidden-http", 403, "http_error"),
        ]:
            response = client.get(path)
            assert response.status_code == expected_status
            data = response.json()
            assert data["error"]["code"] == expected_code
            assert data["request_id"] == response.headers["x-request-id"]
            assert "PRIVATE_SECRET" not in response.text
            assert "Traceback" not in response.text


def test_safe_incoming_request_id_is_preserved_and_invalid_one_replaced():
    app = create_app(settings=Settings(environment="test", _env_file=None))

    @app.get("/request-id")
    def check():
        return {"request_id": get_request_id()}

    from uuid import uuid4
    expected = str(uuid4())
    with TestClient(app) as client:
        ok = client.get("/request-id", headers={"X-Request-ID": expected})
        assert ok.json()["request_id"] == expected
        assert ok.headers["x-request-id"] == expected
        invalid = client.get("/request-id", headers={"X-Request-ID": "untrusted-value"})
        assert invalid.headers["x-request-id"] != "untrusted-value"
        assert UUID(invalid.headers["x-request-id"])


def test_json_logging_contains_correlation_id_without_query_string():
    app = create_app(settings=Settings(environment="test", _env_file=None))
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("hamtayar.http")
    logger.addHandler(handler)
    try:
        with TestClient(app) as client:
            response = client.get("/health/live?access_token=sensitive")
    finally:
        logger.removeHandler(handler)
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    matched = [record for record in records if record["event"] == "request_completed"]
    assert matched
    assert matched[-1]["request_id"] == response.headers["x-request-id"]
    assert matched[-1]["status_code"] == 200
    assert matched[-1]["route"] == "/health/live"
    assert "sensitive" not in stream.getvalue()


def test_telemetry_hooks_fire_and_do_not_break_requests():
    events = []

    class Hooks:
        def on_request_start(self, *, request_id, method):
            events.append(("start", request_id, method))

        def on_request_end(self, *, request_id, status_code, duration_ms):
            events.append(("end", request_id, status_code, duration_ms))

    app = create_app(settings=Settings(environment="test", _env_file=None), telemetry_hooks=Hooks())
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert events[0] == ("start", response.headers["x-request-id"], "GET")
    assert events[1][0:3] == ("end", response.headers["x-request-id"], 200)
    assert events[1][-1] >= 0

    class BrokenHooks:
        def on_request_start(self, **kwargs):
            raise ValueError("telemetry is down")

        def on_request_end(self, **kwargs):
            raise ValueError("telemetry is down")

    app = create_app(settings=Settings(environment="test", _env_file=None), telemetry_hooks=BrokenHooks())
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200


def test_resources_are_closed_at_shutdown():
    events = []

    @asynccontextmanager
    async def fake_resource(settings):
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    app = create_app(
        settings=Settings(environment="test", _env_file=None),
        registry=BootstrapRegistry(resources={"fake": fake_resource}),
        readiness_checks=[lambda container: "fake" in container.resources],
    )
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
        assert events == ["open"]
    assert events == ["open", "close"]
