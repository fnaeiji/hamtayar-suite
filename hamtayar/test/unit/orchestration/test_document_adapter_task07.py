"""TASK-07 protects backward compatibility with TASK-06's document runner."""

import asyncio

import pytest

from apps.document_ingestion.api.schemas.jobs import (
    DocumentExecutionRequest,
    DocumentExecutionResult,
)
from apps.orchestration.execution import (
    LangGraphDocumentExecutor,
    DocumentExecutionTimedOut,
    document_run_options,
    run_document_ingestion,
)
from packages.contracts.common import ContentRef, SourceRef, SourceVersion
from packages.contracts.document import DocumentInput


def example_request(content_uri="file:///C:/docs/sample.txt"):
    return DocumentExecutionRequest(
        document=DocumentInput(
            source=SourceVersion(
                source=SourceRef(
                    source_id="doc-001", knowledge_space_id="engineering", source_type="document",
                ),
                version="v1",
            ),
            content=ContentRef(uri=content_uri),
        ),
        filename="sample.txt",
        content_type="text/plain",
        size_bytes=10,
        processing_profile="default",
    )


class LegacyFakeGraph:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, input):
        self.calls.append(input)
        return {"indexed": 2}


class CheckpointFakeGraph:
    def __init__(self, delay=0):
        self.calls = []
        self.delay = delay

    async def ainvoke(self, input, config=None, **kwargs):
        self.calls.append((input, config, kwargs))
        if self.delay:
            await asyncio.sleep(self.delay)
        return {"indexed": 4}


@pytest.mark.asyncio
async def test_task06_legacy_fake_graph_still_works_without_kwargs():
    graph = LegacyFakeGraph()
    executor = LangGraphDocumentExecutor(
        graph=graph,
        to_state=lambda req: {"content": req.local_file_ref},
        from_state=lambda result: DocumentExecutionResult(chunks_indexed=result["indexed"]),
    )
    result = await run_document_ingestion(executor, example_request(), timeout_seconds=0.5)
    assert result.chunks_indexed == 2
    assert graph.calls == [{"content": "file:///C:/docs/sample.txt"}]


@pytest.mark.asyncio
async def test_checkpointed_document_executor_passes_stable_thread_id():
    graph = CheckpointFakeGraph()
    executor = LangGraphDocumentExecutor(
        graph=graph,
        to_state=lambda request: {"content_ref": request.local_file_ref},
        from_state=lambda state: DocumentExecutionResult(chunks_indexed=state["indexed"]),
        run_options_factory=lambda request: document_run_options(request, timeout_seconds=0.5),
    )
    a = example_request("file:///C:/docs/sample.txt")
    b = example_request("file:///D:/upload/temp/payload")
    await run_document_ingestion(executor, a, timeout_seconds=0.5)
    await run_document_ingestion(executor, b, timeout_seconds=0.5)
    assert graph.calls[0][1]["configurable"]["thread_id"] == graph.calls[1][1]["configurable"]["thread_id"]
    assert graph.calls[0][2]["durability"] == "sync"
    assert graph.calls[0][0]["content_ref"] != graph.calls[1][0]["content_ref"]


@pytest.mark.asyncio
async def test_graph_timeout_keeps_task06_timeout_error_type():
    graph = CheckpointFakeGraph(delay=0.05)
    executor = LangGraphDocumentExecutor(
        graph=graph,
        to_state=lambda request: {"content_ref": request.local_file_ref},
        from_state=lambda state: DocumentExecutionResult(chunks_indexed=state["indexed"]),
        run_options_factory=lambda request: document_run_options(request, timeout_seconds=0.001),
    )
    with pytest.raises(DocumentExecutionTimedOut):
        await run_document_ingestion(executor, example_request(), timeout_seconds=0.5)
