from langgraph.runtime import Runtime
from packages.contracts.retrieval import SearchRequest

from ..state import RetrievalRuntimeContext
from ._shared import trusted_context


def make_prefilter_node(service):
    async def prefilter(state, runtime: Runtime[RetrievalRuntimeContext]):
        scope, active = await service.prefilter(
            request=SearchRequest.model_validate(state["request"]),
            context=trusted_context(runtime),
        )
        return {
            "scope": scope.model_dump(mode="json"),
            "active": [
                {
                    "source": a.source.model_dump(mode="json"),
                    "generation_id": a.generation_id,
                }
                for a in active
            ],
            "status": "running",
            "last_step": "prefilter",
        }

    return prefilter
