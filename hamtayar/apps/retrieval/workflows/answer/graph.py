"""Permissioned document retrieval, with optional grounded answer generation."""

from itertools import pairwise

from langgraph.graph import END, START, StateGraph

from .nodes.build_context import make_build_context_node
from .nodes.generate_answer import make_generate_answer_node
from .nodes.normalize_query import make_normalize_query_node
from .nodes.prefilter import make_prefilter_node
from .nodes.reauthorize import make_reauthorize_node
from .nodes.rerank import make_rerank_node
from .nodes.retrieve import make_retrieve_node
from .routing import after_context
from .state import STAGES, AnswerState, RetrievalRuntimeContext


def build_answer_graph(
    *,
    service,
    count_tokens,
    max_context_tokens=6000,
    generator=None,
    reranker=None,
    checkpointer=None,
    interrupt_after=(),
):
    if max_context_tokens < 1:
        raise ValueError("Positive context token budget required")
    if set(interrupt_after) - set(STAGES) or (interrupt_after and checkpointer is None):
        raise ValueError("Valid breakpoint nodes and a checkpointer are required")
    graph = StateGraph(AnswerState, context_schema=RetrievalRuntimeContext)
    factories = [
        make_prefilter_node(service),
        make_normalize_query_node(service),
        make_retrieve_node(service),
        make_rerank_node(reranker),
        make_reauthorize_node(service),
        make_build_context_node(
            count_tokens=count_tokens, max_tokens=max_context_tokens
        ),
        make_generate_answer_node(generator),
    ]
    for name, node in zip(STAGES, factories, strict=True):
        graph.add_node(name, node)
    graph.add_edge(START, STAGES[0])
    for before, after in pairwise(STAGES[:6]):
        graph.add_edge(before, after)
    graph.add_conditional_edges(
        "build_context", after_context, {"generate": "generate_answer", "done": END}
    )
    graph.add_edge("generate_answer", END)
    return graph.compile(
        checkpointer=checkpointer, interrupt_after=list(interrupt_after) or None
    )
