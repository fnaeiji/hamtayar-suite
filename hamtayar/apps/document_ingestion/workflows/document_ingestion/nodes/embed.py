"""LangGraph embed node; packages owns embedding provider calls and vectors."""

from langgraph.runtime import Runtime
from packages.contracts.document_ingestion import DocumentWorkflowPorts

from ..state import DocumentIngestionState, IngestionRuntimeContext, source_from_state
from ._shared import artifact_update, ref_from_state


def make_embed_node(ports: DocumentWorkflowPorts):
    async def embed(
        state: DocumentIngestionState, runtime: Runtime[IngestionRuntimeContext]
    ):
        result = await ports.embed(
            source=source_from_state(state),
            chunks=ref_from_state(state, "chunks_ref"),
        )
        return artifact_update("embed", result, "embeddings_ref")

    return embed
