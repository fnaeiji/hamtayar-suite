"""LangGraph index node; only packages can validate stored index generation."""

from langgraph.runtime import Runtime
from packages.contracts.document_ingestion import DocumentWorkflowPorts
from packages.contracts.indexing import IndexingResult

from ..state import DocumentIngestionState, IngestionRuntimeContext, source_from_state
from ._shared import denied, ref_from_state, trusted_access


def make_index_node(ports: DocumentWorkflowPorts):
    async def index(
        state: DocumentIngestionState, runtime: Runtime[IngestionRuntimeContext]
    ):
        access = trusted_access(runtime)
        if access is None:
            return denied("index")
        result = await ports.index(
            source=source_from_state(state),
            chunks=ref_from_state(state, "chunks_ref"),
            embeddings=ref_from_state(state, "embeddings_ref"),
            access=access,
        )
        if not isinstance(result, IndexingResult):
            raise TypeError("index returned the wrong package contract")
        count = state.get("chunk_count")
        if (
            not result.validated
            or not result.generation_id
            or result.indexed_count != count
        ):
            return {
                "status": "failed",
                "error_code": "validation_error",
                "error_step": "index",
                "last_step": "index",
                "index_validated": False,
            }
        return {
            "status": "running",
            "last_step": "index",
            "generation_id": result.generation_id,
            "indexed_count": result.indexed_count,
            "index_validated": True,
        }

    return index
