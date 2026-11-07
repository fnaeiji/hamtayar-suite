"""LangGraph chunk node; packages resolves normalized data and handles ACL."""

from langgraph.runtime import Runtime
from packages.contracts.document_ingestion import DocumentWorkflowPorts

from ..state import DocumentIngestionState, IngestionRuntimeContext, source_from_state
from ._shared import artifact_update, denied, ref_from_state, trusted_access


def make_chunk_node(ports: DocumentWorkflowPorts):
    async def chunk(
        state: DocumentIngestionState, runtime: Runtime[IngestionRuntimeContext]
    ):
        access = trusted_access(runtime)
        if access is None:
            return denied("chunk")
        result = await ports.chunk(
            source=source_from_state(state),
            normalized=ref_from_state(state, "normalized_ref"),
            access=access,
            profile=state["processing_profile"],
        )
        return artifact_update("chunk", result, "chunks_ref")

    return chunk
