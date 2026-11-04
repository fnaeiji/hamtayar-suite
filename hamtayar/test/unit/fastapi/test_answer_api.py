"""TASK-05 acceptance tests; no Padin, Qdrant or real LLM needed."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from apps.bootstrap import BootstrapRegistry
from apps.core.config import Settings
from apps.main import create_app
from apps.retrieval.api.dependencies import get_auth_context
from apps.retrieval.api.schemas.answers import MAX_QUESTION_LENGTH, AnswerExecutionRequest
from packages.contracts.access import TrustedAccessContext
from packages.contracts.answering import AnswerResponse as DomainAnswerResponse, Citation
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion

URL = "/api/v1/answers"


def valid_auth():
    return TrustedAccessContext(
        subject_id="user-1", tenant_id="tenant-1", principals=["user-1", "team-ai"],
    )


def citation():
    return Citation(
        evidence_id="chunk-123",
        source=SourceVersion(
            source=SourceRef(source_id="doc-123", knowledge_space_id="engineering", source_type="document"),
            version="v2",
        ),
        location=SourceLocation(page=3, section="intro"),
    )


class FakeExecutor:
    def __init__(self, mode="ok"):
        self.mode = mode
        self.calls: list[AnswerExecutionRequest] = []

    async def execute(self, request):
        self.calls.append(request)
        if self.mode == "raise":
            raise RuntimeError("secret-token=DO-NOT-SHOW")
        if self.mode == "timeout":
            await asyncio.sleep(0.5)
        if self.mode == "failed":
            return DomainAnswerResponse(answer="Internal provider text", citations=[], status="failed")
        if self.mode == "invalid":
            return {"answer": "untrusted"}
        if self.mode == "uncited":
            return DomainAnswerResponse(answer="Unsupported claim", citations=[], status="completed")
        if self.mode == "no_evidence":
            return DomainAnswerResponse(answer="", citations=[], status="no_evidence")
        return DomainAnswerResponse(
            answer="The system uses citations.", citations=[citation()], status="completed",
        )


def app_for_test(executor=None, authenticated=False, **settings_overrides):
    registry = BootstrapRegistry(services={
        "answer_executor": lambda settings, resources: executor,
    }) if executor is not None else BootstrapRegistry()
    settings = Settings(environment="test", _env_file=None, **settings_overrides)
    app = create_app(settings=settings, registry=registry)
    if authenticated:
        app.dependency_overrides[get_auth_context] = valid_auth
    return app


def test_success_returns_answer_citations_request_id_and_trusted_scope():
    fake = FakeExecutor()
    app = app_for_test(fake, authenticated=True)
    with TestClient(app) as client:
        response = client.post(URL, json={"question": "  What is Hamtayar?  "})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "completed"
    assert data["answer"] == "The system uses citations."
    assert data["request_id"] == response.headers["x-request-id"]
    assert data["citations"] == [{
        "evidence_id": "chunk-123", "source_id": "doc-123", "knowledge_space_id": "engineering",
        "version": "v2",
        "location": {"page": 3, "section": "intro", "sheet": None, "cell_range": None,
                     "file_path": None, "start_line": None, "end_line": None},
    }]
    assert len(fake.calls) == 1
    task = fake.calls[0]
    assert task.question == "What is Hamtayar?"
    assert task.access_scope.tenant_id == "tenant-1"
    assert task.access_scope.principals == ["user-1", "team-ai"]
    assert task.access_scope.source_ids is None
    assert task.auth_context.subject_id == "user-1"
    assert task.request_id == data["request_id"]


def test_unauthenticated_is_401_even_when_executor_available():
    fake = FakeExecutor()
    with TestClient(app_for_test(fake)) as client:
        response = client.post(URL, json={"question": "Hello"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert not fake.calls


def test_spoofed_headers_and_claims_cannot_authenticate():
    fake = FakeExecutor()
    with TestClient(app_for_test(fake)) as client:
        response = client.post(URL, json={"question": "Hello"}, headers={
            "Authorization": "Bearer fake-token", "X-User-ID": "admin",
            "X-Tenant-ID": "tenant-1", "X-Auth-Principals": "admin",
        })
    assert response.status_code == 401
    assert not fake.calls


def test_unauthenticated_rejected_before_missing_executor():
    with TestClient(app_for_test()) as client:
        response = client.post(URL, json={"question": "Hello"})
    assert response.status_code == 401


def test_malformed_fake_auth_context_fails_closed():
    fake = FakeExecutor()
    app = app_for_test(fake)
    app.dependency_overrides[get_auth_context] = lambda: {"subject_id": "admin"}
    with TestClient(app) as client:
        response = client.post(URL, json={"question": "Hello"})
    assert response.status_code == 401
    assert not fake.calls


def test_authorized_but_executor_missing_is_503():
    with TestClient(app_for_test(authenticated=True)) as client:
        response = client.post(URL, json={"question": "Hello"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_error"


@pytest.mark.parametrize("payload", [
    {}, {"question": ""}, {"question": "  \n  "},
    {"question": "x" * (MAX_QUESTION_LENGTH + 1)},
    {"question": "x\x00y"},
    {"question": 123},
    {"question": "Hello", "tenant_id": "other-company"},
    {"question": "Hello", "access_scope": {"tenant_id": "other"}},
    {"question": "Hello", "evidence": [{"evidence_id": "spoof"}]},
])
def test_invalid_query_is_422_and_never_reaches_executor(payload):
    fake = FakeExecutor()
    with TestClient(app_for_test(fake, authenticated=True)) as client:
        response = client.post(URL, json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert not fake.calls


def test_no_evidence_has_consistent_response():
    fake = FakeExecutor("no_evidence")
    with TestClient(app_for_test(fake, authenticated=True)) as client:
        response = client.post(URL, json={"question": "Unknown"})
    assert response.status_code == 200
    assert response.json()["status"] == "no_evidence"
    assert response.json()["answer"] == ""
    assert response.json()["citations"] == []


@pytest.mark.parametrize("mode,status", [
    ("raise", 502), ("failed", 502), ("invalid", 502), ("uncited", 502),
])
def test_executor_failures_do_not_leak_internal_details(mode, status):
    with TestClient(app_for_test(FakeExecutor(mode), authenticated=True), raise_server_exceptions=True) as client:
        response = client.post(URL, json={"question": "Hello"})
    assert response.status_code == status
    assert response.json()["error"]["code"] == "provider_error"
    assert "secret-token" not in response.text
    assert "Internal provider text" not in response.text
    assert "Unsupported claim" not in response.text


def test_executor_timeout_is_504():
    with TestClient(app_for_test(FakeExecutor("timeout"), authenticated=True,
                                 request_timeout_seconds=0.01)) as client:
        response = client.post(URL, json={"question": "Hello"})
    assert response.status_code == 504
    assert response.json()["error"]["retryable"] is True


def test_openapi_schemas_and_previous_routes_still_registered():
    app = app_for_test(FakeExecutor(), authenticated=True)
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
    assert URL in spec["paths"]
    assert "post" in spec["paths"][URL]
    op = spec["paths"][URL]["post"]
    assert op["requestBody"]["content"]["application/json"]
    assert "200" in op["responses"]
    assert "AnswerRequest" in spec["components"]["schemas"]
    assert "AnswerResponse" in spec["components"]["schemas"]
    assert "CitationDTO" in spec["components"]["schemas"]
    assert "/api/v1/document-ingestion/jobs" in spec["paths"]
