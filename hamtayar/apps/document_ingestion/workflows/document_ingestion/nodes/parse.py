"""LangGraph parse node. Parser selection/format handling remain in packages."""

from langgraph.runtime import Runtime
from packages.contracts.document_ingestion import DocumentWorkflowPorts

from ..state import DocumentIngestionState, IngestionRuntimeContext, source_from_state
from ._shared import artifact_update, ref_from_state


def make_parse_node(ports: DocumentWorkflowPorts):
    async def parse(
        state: DocumentIngestionState, runtime: Runtime[IngestionRuntimeContext]
    ):
        result = await ports.parse(
            source=source_from_state(state),
            loaded=ref_from_state(state, "loaded_ref"),
            filename=state["filename"],
            content_type=state["content_type"],
        )
        return artifact_update("parse", result, "parsed_ref")

    return parse
