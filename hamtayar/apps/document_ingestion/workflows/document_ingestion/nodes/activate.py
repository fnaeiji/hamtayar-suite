"""LangGraph activation node; packages owns publishing/atomic idempotent write."""

from langgraph.runtime import Runtime
from packages.contracts.document_ingestion import DocumentWorkflowPorts
from packages.contracts.indexing import PublicationRequest, PublicationResult

from ..state import DocumentIngestionState, IngestionRuntimeContext, source_from_state
from ._shared import denied, trusted_access


def make_activate_node(ports: DocumentWorkflowPorts):
    async def activate(
        state: DocumentIngestionState, runtime: Runtime[IngestionRuntimeContext]
    ):
        access = trusted_access(runtime)
        if access is None:
            return denied("activate")
        if state.get("index_validated") is not True or not state.get("generation_id"):
            return {
                "status": "failed",
                "error_code": "validation_error",
                "error_step": "activate",
                "last_step": "activate",
                "published": False,
            }
        result = await ports.activate(
            request=PublicationRequest(
                source=source_from_state(state), generation_id=state["generation_id"]
            ),
            access=access,
        )
        if not isinstance(result, PublicationResult):
            raise TypeError("activate returned the wrong package contract")
        if not result.published or result.generation_id != state["generation_id"]:
            return {
                "status": "failed",
                "error_code": "processing_failed",
                "error_step": "activate",
                "last_step": "activate",
                "published": False,
            }
        return {"status": "completed", "last_step": "activate", "published": True}

    return activate
