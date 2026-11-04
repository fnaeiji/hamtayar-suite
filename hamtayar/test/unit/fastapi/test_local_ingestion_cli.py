"""TASK-06: direct local ingestion with real contracts and fake Executor.

No Padeen, Queue, workers, network, or real Graph services required.
"""

import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest
from fastapi.testclient import TestClient

from apps.bootstrap import BootstrapRegistry
from apps.core.config import Settings
from apps.document_ingestion.api.schemas.jobs import (
    DocumentExecutionRequest,
    DocumentExecutionResult,
)
from apps.document_ingestion.cli import (
    EXIT_INVALID_FILE,
    EXIT_NOT_CONFIGURED,
    EXIT_OK,
    EXIT_PROCESSING_FAILED,
    EXIT_TIMEOUT,
    build_local_request,
    main,
)
from apps.orchestration.execution import (
    LangGraphDocumentExecutor,
    get_runtime_registry,
    resolve_document_ingestion_executor,
    run_document_ingestion,
)


def local_path(uri: str) -> Path:
    parsed = urlsplit(uri)
    assert parsed.scheme == "file"
    return Path(url2pathname(parsed.path))


class FakeExecutor:
    def __init__(self, *, mode: str = "success"):
        self.mode = mode
        self.calls: list[DocumentExecutionRequest] = []

    async def execute(self, request: DocumentExecutionRequest) -> DocumentExecutionResult:
        self.calls.append(request)
        assert local_path(request.local_file_ref).exists()
        if self.mode == "fail":
            raise RuntimeError("sensitive backend information")
        if self.mode == "timeout":
            import asyncio
            await asyncio.sleep(0.3)
        if self.mode == "invalid":
            return {"not": "a DocumentExecutionResult"}  # type: ignore[return-value]
        return DocumentExecutionResult(chunks_indexed=3)


def registry_for(executor: FakeExecutor) -> BootstrapRegistry:
    return BootstrapRegistry(services={"document_ingestion_executor": lambda settings, resources: executor})


def config(tmp_path: Path, **kwargs) -> Settings:
    return Settings(_env_file=None, environment="test", temp_dir=tmp_path / "temp", **kwargs)


def write_sample(tmp_path: Path, filename: str = "sample.txt", content: bytes = b"Hello Hamtayar\n") -> Path:
    path = tmp_path / filename
    path.write_bytes(content)
    return path


def test_cli_success_uses_task04_execution_contract(tmp_path, capsys):
    source = write_sample(tmp_path)
    fake = FakeExecutor()
    code = main(
        [str(source), "--source-id", "doc-101", "--knowledge-space-id", "engineering",
         "--version", "v2", "--processing-profile", "standard"],
        settings=config(tmp_path), registry=registry_for(fake),
    )
    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert not captured.err
    output = json.loads(captured.out)
    assert output["status"] == "completed"
    assert output["source_id"] == "doc-101"
    assert output["version"] == "v2"
    assert output["chunks_indexed"] == 3
    assert len(fake.calls) == 1
    sent = fake.calls[0]
    assert isinstance(sent, DocumentExecutionRequest)
    assert sent.document.source.source.knowledge_space_id == "engineering"
    assert sent.document.source.source.source_type == "document"
    assert sent.document.content.uri == source.resolve().as_uri()
    assert sent.processing_profile == "standard"
    assert sent.size_bytes == source.stat().st_size
    assert source.exists(), "CLI must never delete the user's original file"


def test_cli_default_source_id_is_stable(tmp_path, capsys):
    source = write_sample(tmp_path)
    fake = FakeExecutor()
    first = main([str(source)], settings=config(tmp_path), registry=registry_for(fake))
    out1 = json.loads(capsys.readouterr().out)
    second = main([str(source)], settings=config(tmp_path), registry=registry_for(fake))
    out2 = json.loads(capsys.readouterr().out)
    assert (first, second) == (0, 0)
    assert out1["source_id"] == out2["source_id"]
    assert out1["source_id"].startswith("local-")
    assert fake.calls[0].document.source.source.knowledge_space_id == "local"


@pytest.mark.parametrize("name,contents", [
    ("script.exe", b"something"),
    ("empty.txt", b""),
    ("malformed.pdf", b"not a pdf"),
    ("binary.txt", b"hello\x00world"),
    ("invalid.md", b"\xff\xff"),
    ("bad.docx", b"not a docx"),
])
def test_invalid_local_files_fail_before_graph(tmp_path, capsys, name, contents):
    source = write_sample(tmp_path, name, contents)
    fake = FakeExecutor()
    code = main([str(source)], settings=config(tmp_path), registry=registry_for(fake))
    stderr = json.loads(capsys.readouterr().err)
    assert code == EXIT_INVALID_FILE
    assert stderr["status"] == "failed"
    assert stderr["error"]["code"] == "invalid_input"
    assert fake.calls == []


def test_missing_file_fails_without_executor(tmp_path, capsys):
    fake = FakeExecutor()
    code = main([str(tmp_path / "missing.txt")], settings=config(tmp_path), registry=registry_for(fake))
    assert code == EXIT_INVALID_FILE
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_input"
    assert not fake.calls


def test_file_size_limit_applies_to_cli(tmp_path, capsys):
    source = write_sample(tmp_path)
    fake = FakeExecutor()
    code = main([str(source)], settings=config(tmp_path, max_upload_size_bytes=5), registry=registry_for(fake))
    assert code == EXIT_INVALID_FILE
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_input"
    assert not fake.calls


@pytest.mark.parametrize("args", [
    ["--source-id", "unsafe/a"],
    ["--knowledge-space-id", "invalid space"],
    ["--version", "bad version"],
    ["--processing-profile", "bad profile"],
])
def test_invalid_metadata_is_rejected(tmp_path, capsys, args):
    source = write_sample(tmp_path)
    fake = FakeExecutor()
    status = main([str(source), *args], settings=config(tmp_path), registry=registry_for(fake))
    assert status == EXIT_INVALID_FILE
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_input"
    assert not fake.calls


def test_missing_executor_is_explicit_nonzero(tmp_path, capsys):
    source = write_sample(tmp_path)
    code = main([str(source)], settings=config(tmp_path), registry=get_runtime_registry())
    err = json.loads(capsys.readouterr().err)
    assert code == EXIT_NOT_CONFIGURED
    assert err["error"]["code"] == "executor_unavailable"
    assert source.exists()


@pytest.mark.parametrize("mode,expected_code,expected_name", [
    ("fail", EXIT_PROCESSING_FAILED, "processing_failed"),
    ("invalid", EXIT_PROCESSING_FAILED, "processing_failed"),
    ("timeout", EXIT_TIMEOUT, "processing_timeout"),
])
def test_execution_failure_timeout_and_sanitized_output(tmp_path, capsys, mode, expected_code, expected_name):
    source = write_sample(tmp_path)
    fake = FakeExecutor(mode=mode)
    opts = {"request_timeout_seconds": 0.01} if mode == "timeout" else {}
    code = main([str(source)], settings=config(tmp_path, **opts), registry=registry_for(fake))
    capture = capsys.readouterr()
    assert code == expected_code
    obj = json.loads(capture.err)
    assert obj["error"]["code"] == expected_name
    assert "sensitive backend" not in capture.err
    assert "Traceback" not in capture.err
    assert source.exists()


def test_graph_adapter_calls_ainvoke_and_maps_result(tmp_path):
    from asyncio import run

    class FakeCompiledGraph:
        async def ainvoke(self, input):
            assert input["path"] == expected_path
            return {"status": "completed", "indexed": 7}

    path = write_sample(tmp_path)
    expected_path = path.as_uri()
    request = build_local_request(
        path, max_upload_size_bytes=1024, source_id="doc-1",
        knowledge_space_id="team", version="v1", processing_profile="default",
    )
    executor = LangGraphDocumentExecutor(
        graph=FakeCompiledGraph(),
        to_state=lambda execution: {"path": execution.local_file_ref},
        from_state=lambda state: DocumentExecutionResult(chunks_indexed=state["indexed"]),
    )
    result = run(run_document_ingestion(executor, request, timeout_seconds=1))
    assert result.chunks_indexed == 7


def test_http_and_cli_share_same_bootstrap_executor_and_document_contract(tmp_path, capsys):
    # Use the actual Task-04 HTTP router, plus the same executor factory.
    from apps.main import create_app

    source = write_sample(tmp_path)
    fake = FakeExecutor()
    registry = registry_for(fake)
    settings = config(tmp_path)

    app = create_app(settings=settings, registry=registry)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/document-ingestion/jobs",
            data={"source_id": "doc-101", "knowledge_space_id": "engineering", "version": "v2"},
            files={"file": (source.name, source.read_bytes(), "text/plain")},
        )
    assert response.status_code == 200, response.text

    cli_status = main(
        [str(source), "--source-id", "doc-101", "--knowledge-space-id", "engineering", "--version", "v2"],
        settings=settings, registry=registry,
    )
    capsys.readouterr()
    assert cli_status == EXIT_OK
    assert len(fake.calls) == 2
    first, second = fake.calls
    assert type(first.document) is type(second.document)
    assert first.document.source == second.document.source
    assert first.content_type == second.content_type
    assert first.document.content.uri != second.document.content.uri
    assert not local_path(first.local_file_ref).exists(), "HTTP request-scoped staging must be cleaned"
    assert local_path(second.local_file_ref).exists(), "CLI must preserve local input"
