from packages.contracts.access import AccessScope
from packages.contracts.common import SourceVersion
from packages.contracts.publication import ActiveGeneration
from packages.contracts.retrieval import SearchRequest

from ._shared import dump


def make_retrieve_node(service):
    async def retrieve(state):
        response = await service.retrieve(
            request=SearchRequest.model_validate(state["request"]),
            scope=AccessScope.model_validate(state["scope"]),
            active=[
                ActiveGeneration(
                    SourceVersion.model_validate(a["source"]), a["generation_id"]
                )
                for a in state["active"]
            ],
        )
        return {
            "results": dump(response.results),
            "partial": response.partial,
            "warnings": response.warnings,
            "last_step": "retrieve",
        }

    return retrieve
