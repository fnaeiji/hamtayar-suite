from langgraph.runtime import Runtime

from ..state import RetrievalRuntimeContext
from ._shared import dump, results_from, trusted_context


def make_reauthorize_node(service):
    async def reauthorize(state, runtime: Runtime[RetrievalRuntimeContext]):
        results = await service.reauthorize(
            results=results_from(state), context=trusted_context(runtime)
        )
        return {"results": dump(results), "last_step": "reauthorize"}

    return reauthorize
