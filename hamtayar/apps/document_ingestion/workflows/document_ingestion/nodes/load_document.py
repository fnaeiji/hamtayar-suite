"""LangGraph load node. All file access lives in the injected packages port."""

from langgraph.runtime import Runtime
from packages.contracts.document import DocumentInput
from packages.contracts.document_ingestion import DocumentWorkflowPorts

from ..state import DocumentIngestionState, IngestionRuntimeContext, source_from_state
from ._shared import artifact_update, denied, ref_from_state, trusted_access


def make_load_node(ports: DocumentWorkflowPorts):
    async def load_document(
        state: DocumentIngestionState, runtime: Runtime[IngestionRuntimeContext]
    ):
        access = trusted_access(runtime)
        if access is None:
            return denied("load_document")
        result = await ports.load_document(
            document=DocumentInput(
                source=source_from_state(state),
                content=ref_from_state(state, "content_ref"),
            ),
            access=access,
        )
        return artifact_update("load_document", result, "loaded_ref")

    return load_document
