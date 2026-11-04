"""Real LangGraph integration tests. Run in Hamtayar's uv env (LangGraph installed).

This module intentionally skips when LangGraph isn't installed. Fake tests in
`test_graph_runtime.py` still validate transport/runtime logic without it.
"""

import pytest

pytest.importorskip("langgraph")

from typing import TypedDict

from langgraph.graph import END, START, StateGraph  # noqa: E402

from apps.orchestration.checkpointer import CheckpointerFactory  # noqa: E402
from apps.orchestration.graph_runtime import (  # noqa: E402
    GraphExecutionLayer,
    GraphExecutionFailed,
    GraphRunOptions,
    make_node_retry_policy,
)


class CounterState(TypedDict):
    counter: int


@pytest.mark.asyncio
async def test_checkpoint_after_node_then_resume_same_thread_without_replaying_first_node():
    calls = {"first": 0, "second": 0}

    def first(state: CounterState) -> dict:
        calls["first"] += 1
        return {"counter": state["counter"] + 1}

    def second(state: CounterState) -> dict:
        calls["second"] += 1
        return {"counter": state["counter"] * 2}

    builder = StateGraph(CounterState)
    builder.add_node("first", first)
    builder.add_node("second", second)
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)

    factory = CheckpointerFactory()
    async with factory.open() as saver:
        compiled = builder.compile(checkpointer=saver, interrupt_after=["first"])
        layer = GraphExecutionLayer()
        options = GraphRunOptions(thread_id="test-checkpoint-resume")
        first_output = await layer.execute(compiled, {"counter": 1}, options=options)
        assert first_output["counter"] == 2
        checkpoint = await layer.get_state(compiled, thread_id=options.thread_id)
        assert checkpoint.values["counter"] == 2
        assert tuple(checkpoint.next) == ("second",)
        result = await layer.execute(compiled, None, options=GraphRunOptions(
            thread_id=options.thread_id, resume=True,
        ))
        assert result["counter"] == 4
        assert calls == {"first": 1, "second": 1}
        assert (await layer.get_state(compiled, thread_id=options.thread_id)).next == ()


@pytest.mark.asyncio
async def test_failed_node_can_be_resumed_from_checkpoint_after_fix():
    calls = {"first": 0, "second": 0}

    def first(state: CounterState) -> dict:
        calls["first"] += 1
        return {"counter": state["counter"] + 10}

    def second(state: CounterState) -> dict:
        calls["second"] += 1
        if calls["second"] == 1:
            raise RuntimeError("temporary failure")
        return {"counter": state["counter"] + 1}

    builder = StateGraph(CounterState)
    builder.add_node("first", first)
    builder.add_node("second", second)
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)

    async with CheckpointerFactory().open() as saver:
        compiled = builder.compile(checkpointer=saver)
        layer = GraphExecutionLayer()
        opts = GraphRunOptions(thread_id="failed-thread")
        with pytest.raises(GraphExecutionFailed):
            await layer.execute(compiled, {"counter": 1}, options=opts)
        checkpoint = await layer.get_state(compiled, thread_id=opts.thread_id)
        assert checkpoint.values["counter"] == 11
        resumed = await layer.execute(compiled, None, options=GraphRunOptions(
            thread_id=opts.thread_id, resume=True,
        ))
        assert resumed["counter"] == 12
        assert calls == {"first": 1, "second": 2}


@pytest.mark.asyncio
async def test_retry_policy_applies_only_to_designated_transient_node():
    class TemporaryProviderError(Exception):
        pass

    calls = 0

    def flaky(state: CounterState) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TemporaryProviderError("simulated temporary error")
        return {"counter": state["counter"] + 1}

    builder = StateGraph(CounterState)
    builder.add_node("flaky", flaky, retry_policy=make_node_retry_policy(
        retry_on=(TemporaryProviderError,), max_attempts=2, initial_interval=0.01,
    ))
    builder.add_edge(START, "flaky")
    builder.add_edge("flaky", END)

    async with CheckpointerFactory().open() as saver:
        compiled = builder.compile(checkpointer=saver)
        result = await GraphExecutionLayer().execute(
            compiled, {"counter": 2}, options=GraphRunOptions(thread_id="retry-thread")
        )
    assert result["counter"] == 3
    assert calls == 2


@pytest.mark.asyncio
async def test_run_scoped_context_reaches_node_runtime():
    from langgraph.runtime import Runtime

    class Context(TypedDict):
        factor: int

    def scaled(state: CounterState, runtime: Runtime[Context]) -> dict:
        return {"counter": state["counter"] * runtime.context["factor"]}

    builder = StateGraph(CounterState, context_schema=Context)
    builder.add_node("scaled", scaled)
    builder.add_edge(START, "scaled")
    builder.add_edge("scaled", END)
    async with CheckpointerFactory().open() as saver:
        graph = builder.compile(checkpointer=saver)
        output = await GraphExecutionLayer().execute(
            graph, {"counter": 2},
            options=GraphRunOptions(thread_id="context-thread", context={"factor": 3}),
        )
    assert output["counter"] == 6
