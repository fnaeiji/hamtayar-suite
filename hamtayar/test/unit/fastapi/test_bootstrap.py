"""Acceptance checks for TASK-02, with no external services required."""

from contextlib import asynccontextmanager

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.bootstrap import BootstrapRegistry, get_container
from apps.core.config import Settings
from apps.core.lifespan import create_lifespan


def test_environment_settings_override_defaults(monkeypatch):
    monkeypatch.setenv("HAMTAYAR_ENVIRONMENT", "test")
    monkeypatch.setenv("HAMTAYAR_REQUEST_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("HAMTAYAR_MAX_UPLOAD_SIZE_BYTES", "2048")
    cfg = Settings(_env_file=None)
    assert cfg.environment == "test"
    assert cfg.request_timeout_seconds == 2.5
    assert cfg.max_upload_size_bytes == 2048


def test_invalid_settings_are_rejected(monkeypatch):
    monkeypatch.setenv("HAMTAYAR_REQUEST_TIMEOUT_SECONDS", "-4")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_app_starts_without_any_external_service():
    app = FastAPI(lifespan=create_lifespan(Settings(_env_file=None)))

    @app.get("/probe")
    def probe(container=Depends(get_container)):
        return {"environment": container.settings.environment, "resources": len(container.resources)}

    with TestClient(app) as client:
        assert client.get("/probe").json()["resources"] == 0

    assert not hasattr(app.state, "container")


def test_shared_resource_is_created_once_and_closed_once():
    events = []
    instance = object()

    @asynccontextmanager
    async def fake_resource(settings):
        events.append("open")
        try:
            yield instance
        finally:
            events.append("close")

    def fake_service(settings, resources):
        events.append("service")
        return {"resource": resources["db"]}

    def fake_graph(settings, resources, services):
        events.append("graph")
        assert services["answer"]["resource"] is resources["db"]
        return object()

    registry = BootstrapRegistry(
        resources={"db": fake_resource},
        services={"answer": fake_service},
        graphs={"answer": fake_graph},
    )
    app = FastAPI(lifespan=create_lifespan(Settings(_env_file=None), registry))

    @app.get("/resource")
    def resource(container=Depends(get_container)):
        return {"id": id(container.resources["db"]), "graphs": list(container.graphs)}

    with TestClient(app) as client:
        first = client.get("/resource").json()
        second = client.get("/resource").json()
        assert first == second
        assert first["id"] == id(instance)
        assert first["graphs"] == ["answer"]
        assert events == ["open", "service", "graph"]

    assert events == ["open", "service", "graph", "close"]
    assert not hasattr(app.state, "container")


def test_partial_startup_failure_closes_opened_resources():
    events = []

    @asynccontextmanager
    async def first(settings):
        events.append("open")
        try:
            yield object()
        finally:
            events.append("close")

    @asynccontextmanager
    async def failing(settings):
        raise RuntimeError("cannot connect")
        yield  # mark as an async generator

    app = FastAPI(lifespan=create_lifespan(
        Settings(_env_file=None),
        BootstrapRegistry(resources={"first": first, "failing": failing}),
    ))
    with pytest.raises(RuntimeError, match="cannot connect"):
        with TestClient(app):
            pass
    assert events == ["open", "close"]
