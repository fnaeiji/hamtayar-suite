"""LangGraph normalize node; packages already supplies PersianNormalizer."""

from langgraph.runtime import Runtime
from packages.contracts.document_ingestion import DocumentWorkflowPorts

from ..state import DocumentIngestionState, IngestionRuntimeContext, source_from_state
from ._shared import artifact_update, ref_from_state


def make_normalize_node(ports: DocumentWorkflowPorts):
    async def normalize(
        state: DocumentIngestionState, runtime: Runtime[IngestionRuntimeContext]
    ):
        result = await ports.normalize(
            source=source_from_state(state),
            parsed=ref_from_state(state, "parsed_ref"),
            profile=state["processing_profile"],
        )
        return artifact_update("normalize", result, "normalized_ref")

    return normalize
