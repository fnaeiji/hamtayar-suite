"""TASK-07 pure runner tests; no real LangGraph dependency required."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest

from apps.orchestration.checkpointer import CheckpointSettings, CheckpointerFactory, checkpoint_resource_factory
from apps.orchestration.graph_runtime import (
    GraphExecutionFailed,
    GraphExecutionLayer,
    GraphExecutionTimedOut,
    GraphRunOptions,
    GraphStateUnavailable,
    document_thread_id,
    stable_idempotency_key,
)


class CapturingGraph:
    def __init__(self, *, fail=False, delay=0):
        self.calls = []
        self.fail = fail
        self.delay = delay

    async def ainvoke(self, input, config=None, *, context=None, durability=None):
        self.calls.append((input, config, context, durability))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise ConnectionError("private provider secret")
        return {"updated": True}

    async def aget_state(self, config):
        return {"checkpoint_for": config["configurable"]["thread_id"]}


@pytest.mark.asyncio
async def test_invoke_passes_thread_id_context_limit_durability_and_output():
    graph = CapturingGraph()
    options = GraphRunOptions(
        thread_id="task-1", timeout_seconds=0.5, recursion_limit=20,
        context={"tenant": "t-1"}, durability="sync",
    )
    response = await GraphExecutionLayer().execute(graph, {"count": 0}, options=options)
    assert response == {"updated": True}
    assert graph.calls == [
        ({"count": 0}, {"configurable": {"thread_id": "task-1"}, "recursion_limit": 20},
         {"tenant": "t-1"}, "sync")
    ]


@pytest.mark.asyncio
async def test_resume_sends_none_with_same_thread_id():
    layer = GraphExecutionLayer()
    graph = CapturingGraph()
    options = GraphRunOptions(thread_id="thread-stable")
    await layer.execute(graph, {"initial": True}, options=options)
    await layer.execute(graph, None, options=replace(options, resume=True))
    assert graph.calls[0][1]["configurable"]["thread_id"] == "thread-stable"
    assert graph.calls[1][1]["configurable"]["thread_id"] == "thread-stable"
    assert graph.calls[1][0] is None


@pytest.mark.asyncio
async def test_wrong_resume_usage_fails_before_graph_call():
    graph = CapturingGraph()
    with pytest.raises(ValueError, match="Resume requires"):
        await GraphExecutionLayer().execute(graph, {"new": 1}, options=GraphRunOptions("x", resume=True))
    with pytest.raises(ValueError, match="initial_state"):
        await GraphExecutionLayer().execute(graph, None, options=GraphRunOptions("x"))
    assert not graph.calls


@pytest.mark.asyncio
async def test_timeout_is_explicit_and_execution_cancelled():
    graph = CapturingGraph(delay=0.05)
    with pytest.raises(GraphExecutionTimedOut, match="timed out"):
        await GraphExecutionLayer().execute(
            graph, {"x": 1}, options=GraphRunOptions("timeout", timeout_seconds=0.001)
        )


@pytest.mark.asyncio
async def test_unexpected_failure_propagates_safely_with_cause():
    graph = CapturingGraph(fail=True)
    with pytest.raises(GraphExecutionFailed, match="Graph execution failed") as err:
        await GraphExecutionLayer().execute(graph, {"x": 1}, options=GraphRunOptions("thread"))
    assert isinstance(err.value.__cause__, ConnectionError)
    assert "secret" not in str(err.value)


@pytest.mark.asyncio
async def test_checkpoint_snapshot_uses_same_thread_id():
    graph = CapturingGraph()
    snapshot = await GraphExecutionLayer().get_state(graph, thread_id="t42")
    assert snapshot == {"checkpoint_for": "t42"}
    with pytest.raises(GraphStateUnavailable):
        await GraphExecutionLayer().get_state(object(), thread_id="t42")


@pytest.mark.parametrize("value", ["", " ", "x" * 256, " padding ", None, 23])
def test_bad_thread_ids_rejected(value):
    with pytest.raises(ValueError):
        GraphRunOptions(thread_id=value)


@pytest.mark.parametrize("settings", [
    {"timeout_seconds": 0}, {"timeout_seconds": -5},
    {"recursion_limit": 1}, {"durability": "invalid"},
])
def test_invalid_runtime_config_rejected(settings):
    with pytest.raises(ValueError):
        GraphRunOptions(thread_id="test", **settings)


def test_stable_idempotency_key_is_deterministic_namespaced_and_nonempty():
    kwargs = {"workflow": "document_ingestion", "source_id": "doc-1", "version": "v2", "step": "index"}
    first = stable_idempotency_key(namespace="tenant-1", **kwargs)
    second = stable_idempotency_key(namespace="tenant-1", **kwargs)
    other = stable_idempotency_key(namespace="tenant-2", **kwargs)
    assert first == second and first != other
    assert len(first) == 64
    with pytest.raises(ValueError):
        stable_idempotency_key(namespace="", **kwargs)


def test_document_thread_identity_is_stable_across_transport_references():
    a = document_thread_id(knowledge_space_id="space1", source_id="doc", version="v1", processing_profile="default")
    b = document_thread_id(knowledge_space_id="space1", source_id="doc", version="v1", processing_profile="default")
    other = document_thread_id(knowledge_space_id="space1", source_id="doc", version="v2", processing_profile="default")
    assert a == b and a != other and a.startswith("document-")
    assert len(a) <= 255


def test_factory_validates_backend_configuration():
    with pytest.raises(ValueError):
        CheckpointSettings(backend="sqlite")
    with pytest.raises(ValueError):
        CheckpointSettings(backend="memory", sqlite_path="/somewhere")
    with pytest.raises(ValueError):
        CheckpointerFactory(CheckpointSettings(backend="custom"))
    with pytest.raises(ValueError):
        CheckpointerFactory(provider=lambda: object())


@pytest.mark.asyncio
async def test_custom_backend_is_injected_and_closed_by_lifespan():
    events = []
    backend = object()

    @asynccontextmanager
    async def custom_saver():
        events.append("open")
        try:
            yield backend
        finally:
            events.append("close")

    factory = CheckpointerFactory(CheckpointSettings(backend="custom"), provider=custom_saver)
    resource_factory = checkpoint_resource_factory(factory)
    async with resource_factory(object()) as saver:
        assert saver is backend
        assert events == ["open"]
    assert events == ["open", "close"]
