"""TASK-08 graph wiring; computational operations are injected from packages.

No fake defaults. This module contains only LangGraph wiring and routing.
"""

from langgraph.graph import END, START, StateGraph
from packages.contracts.document_ingestion import DocumentWorkflowPorts

from .nodes.activate import make_activate_node
from .nodes.chunk import make_chunk_node
from .nodes.embed import make_embed_node
from .nodes.failure import failed
from .nodes.index import make_index_node
from .nodes.load_document import make_load_node
from .nodes.normalize import make_normalize_node
from .nodes.parse import make_parse_node
from .routing import (
    after_activate,
    after_chunk,
    after_embed,
    after_index,
    after_load,
    after_normalize,
    after_parse,
)
from .state import DocumentIngestionState, IngestionRuntimeContext


def build_document_ingestion_graph(
    ports: DocumentWorkflowPorts,
    *,
    checkpointer=None,
    interrupt_after: tuple[str, ...] = (),
):
    """Compile an actual StateGraph using injected real or fake package ports.

    For TASK-07 checkpoints pass its shared saver. Absence of a saver keeps
    compilation possible for local smoke tests; production needs persistence.
    """
    if ports is None:
        raise ValueError("DocumentWorkflowPorts must be explicitly supplied")

    graph = StateGraph(DocumentIngestionState, context_schema=IngestionRuntimeContext)
    graph.add_node("load_document", make_load_node(ports))
    graph.add_node("parse", make_parse_node(ports))
    graph.add_node("normalize", make_normalize_node(ports))
    graph.add_node("chunk", make_chunk_node(ports))
    graph.add_node("embed", make_embed_node(ports))
    graph.add_node("index", make_index_node(ports))
    graph.add_node("activate", make_activate_node(ports))
    graph.add_node("failure", failed)

    graph.add_edge(START, "load_document")
    for stage, router, next_stage in (
        ("load_document", after_load, "parse"),
        ("parse", after_parse, "normalize"),
        ("normalize", after_normalize, "chunk"),
        ("chunk", after_chunk, "embed"),
        ("embed", after_embed, "index"),
        ("index", after_index, "activate"),
    ):
        graph.add_conditional_edges(
            stage, router, {"next": next_stage, "failure": "failure"}
        )
    graph.add_conditional_edges(
        "activate", after_activate, {"next": END, "failure": "failure"}
    )
    graph.add_edge("failure", END)
    if interrupt_after:
        supported = {
            "load_document",
            "parse",
            "normalize",
            "chunk",
            "embed",
            "index",
            "activate",
        }
        if not set(interrupt_after).issubset(supported):
            raise ValueError("interrupt_after contains an unknown workflow node")
        if checkpointer is None:
            raise ValueError("interrupt_after requires a checkpointer")
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_after=list(interrupt_after) if interrupt_after else None,
    )
