"""Run a real checkpoint/resume demo: uv run python -m apps.orchestration.checkpoint_demo.

No external services required; uses an InMemorySaver scoped to this command.
"""

import asyncio
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from apps.orchestration.checkpointer import CheckpointerFactory
from apps.orchestration.graph_runtime import GraphExecutionLayer, GraphRunOptions


class DemoState(TypedDict):
    value: int


def build_demo_graph(checkpointer):
    builder = StateGraph(DemoState)
    builder.add_node("prepare", lambda state: {"value": state["value"] + 1})
    builder.add_node("process", lambda state: {"value": state["value"] * 2})
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "process")
    builder.add_edge("process", END)
    return builder.compile(checkpointer=checkpointer, interrupt_after=["prepare"])


async def main() -> None:
    async with CheckpointerFactory().open() as checkpointer:
        graph = build_demo_graph(checkpointer)
        runner = GraphExecutionLayer()
        opts = GraphRunOptions(thread_id="task07-demo-001")
        first = await runner.execute(graph, {"value": 2}, options=opts)
        checkpoint = await runner.get_state(graph, thread_id=opts.thread_id)
        finished = await runner.execute(
            graph, None,
            options=GraphRunOptions(thread_id=opts.thread_id, resume=True),
        )
        print(json.dumps({
            "thread_id": opts.thread_id,
            "after_first_node": first["value"],
            "checkpoint_value": checkpoint.values["value"],
            "pending_nodes_at_checkpoint": list(checkpoint.next),
            "after_resume": finished["value"],
        }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
