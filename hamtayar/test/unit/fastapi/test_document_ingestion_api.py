"""TASK-04 acceptance tests: no Padeen, queue, DB or real Graph required."""
import asyncio
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from apps.bootstrap import BootstrapRegistry
from apps.core.config import Settings
from apps.document_ingestion.api.schemas.jobs import DocumentExecutionResult
from apps.main import create_app

URL = "/api/v1/document-ingestion/jobs"
FIELDS = {
    "source_id": "doc-101",
    "knowledge_space_id": "engineering",
    "version": "v1",
    "processing_profile": "default",
}


class FakeExecutor:
    def __init__(self, *, mode="ok"):
        self.mode = mode
        self.requests = []
        self.staged_paths = []

    async def execute(self, request):
        self.requests.append(request)
        path = Path(url2pathname(urlsplit(request.local_file_ref).path))
        assert path.exists()
        assert path.name == "payload"
        assert path.read_bytes() == b"%PDF-1.7\nexample document"
        self.staged_paths.append(path)
        if self.mode == "fail":
            raise RuntimeError("secret internal endpoint/token")
        if self.mode == "timeout":
            await asyncio.sleep(1)
        return DocumentExecutionResult(chunks_indexed=4)


@pytest.fixture
def fake():
    return FakeExecutor()


def _client(tmp_path, executor=None, **settings_overrides):
    settings = Settings(
        _env_file=None,
        environment="test",
        temp_dir=tmp_path / "uploads",
        **settings_overrides,
    )
    registry = BootstrapRegistry(services={
        "document_ingestion_executor": (lambda config, resources: executor)
    }) if executor is not None else BootstrapRegistry()
    return TestClient(create_app(settings=settings, registry=registry), raise_server_exceptions=False)


def _upload(client, *, filename="doc.pdf", data=b"%PDF-1.7\nexample document", mime="application/pdf", fields=None):
    return client.post(URL, data=FIELDS if fields is None else fields, files={"file": (filename, data, mime)})


def test_success_was_processed_and_temp_file_removed(tmp_path, fake):
    with _client(tmp_path, fake) as client:
        response = _upload(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["source_id"] == "doc-101"
    assert body["version"] == "v1"
    assert body["chunks_indexed"] == 4
    assert len(fake.requests) == 1
    assert fake.requests[0].document.source.source.knowledge_space_id == "engineering"
    assert fake.requests[0].processing_profile == "default"
    assert fake.requests[0].size_bytes > 0
    assert body["request_id"] == response.headers["x-request-id"]
    assert all(not p.exists() for p in fake.staged_paths)
    assert not list((tmp_path / "uploads").glob("hamtayar-ingest-*"))


def test_existing_health_routes_are_preserved(tmp_path, fake):
    with _client(tmp_path, fake) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


def test_missing_executor_is_an_explicit_503(tmp_path):
    with _client(tmp_path) as client:
        response = _upload(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_error"
    assert response.headers["x-request-id"]
    assert not (tmp_path / "uploads").exists()


@pytest.mark.parametrize("name,mime,code", [
    ("script.exe", "application/octet-stream", 415),
    ("../../malicious.pdf", "application/pdf", 422),
    ("..\\malicious.pdf", "application/pdf", 422),
    ("doc.pdf", "text/plain", 415),
])
def test_rejects_bad_filename_or_mime(tmp_path, fake, name, mime, code):
    with _client(tmp_path, fake) as client:
        response = _upload(client, filename=name, mime=mime)
    assert response.status_code == code, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert not fake.requests


def test_rejects_oversized_upload(tmp_path, fake):
    with _client(tmp_path, fake, max_upload_size_bytes=8) as client:
        response = _upload(client)
    assert response.status_code == 413
    assert not fake.requests


def test_rejects_zero_length_file(tmp_path, fake):
    with _client(tmp_path, fake) as client:
        response = _upload(client, data=b"")
    assert response.status_code == 422
    assert not fake.requests
    assert not list((tmp_path / "uploads").glob("hamtayar-ingest-*"))


def test_rejects_spoofed_pdf(tmp_path, fake):
    with _client(tmp_path, fake) as client:
        response = _upload(client, data=b"Hello this is not a PDF")
    assert response.status_code == 422
    assert not fake.requests
    assert not list((tmp_path / "uploads").glob("hamtayar-ingest-*"))


def test_rejects_invalid_form_data(tmp_path, fake):
    with _client(tmp_path, fake) as client:
        response = _upload(client, fields={**FIELDS, "source_id": "not allowed / path"})
    assert response.status_code == 422
    assert not fake.requests
    assert response.headers["x-request-id"]


def test_rejects_missing_file(tmp_path, fake):
    with _client(tmp_path, fake) as client:
        response = client.post(URL, data=FIELDS)
    assert response.status_code == 422
    assert not fake.requests


def test_executor_failure_is_safe_and_cleanup_happens(tmp_path):
    fake = FakeExecutor(mode="fail")
    with _client(tmp_path, fake) as client:
        response = _upload(client)
    assert response.status_code == 500, response.text
    assert response.json()["error"] == {
        "code": "processing_failed",
        "message": "Document processing failed",
        "retryable": False,
    }
    assert "secret" not in response.text
    assert all(not p.exists() for p in fake.staged_paths)


def test_executor_timeout_is_504_and_cleans_up(tmp_path):
    fake = FakeExecutor(mode="timeout")
    with _client(tmp_path, fake, request_timeout_seconds=0.005) as client:
        response = _upload(client)
    assert response.status_code == 504
    assert response.json()["error"]["retryable"] is True
    assert all(not p.exists() for p in fake.staged_paths)


def test_openapi_registers_multipart_endpoint(tmp_path, fake):
    with _client(tmp_path, fake) as client:
        spec = client.get("/openapi.json").json()
    endpoint = spec["paths"][URL]["post"]
    assert "multipart/form-data" in endpoint["requestBody"]["content"]


def test_docx_header_is_checked_without_unpacking(tmp_path, fake):
    with BytesIO() as stream:
        with ZipFile(stream, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<document/>")
        docx_bytes = stream.getvalue()
    class DocxExecutor:
        async def execute(self, request):
            assert Path(url2pathname(urlsplit(request.local_file_ref).path)).exists()
            return DocumentExecutionResult()
    with _client(tmp_path, DocxExecutor()) as client:
        r = _upload(client, filename="document.docx", data=docx_bytes,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert r.status_code == 200, r.text


def test_text_file_accepts_utf8_and_rejects_binary(tmp_path):
    class TextExecutor:
        async def execute(self, request):
            assert Path(url2pathname(urlsplit(request.local_file_ref).path)).read_text() == "hello\n"
            return DocumentExecutionResult()
    with _client(tmp_path, TextExecutor()) as client:
        ok = _upload(client, filename="readme.md", data=b"hello\n", mime="text/markdown")
        bad = _upload(client, filename="readme.md", data=b"\xff\xff", mime="text/markdown")
    assert ok.status_code == 200, ok.text
    assert bad.status_code == 422, bad.text
