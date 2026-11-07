"""Atomically activate a previously validated generation via injected catalog.

Calling application MUST obtain trusted authorization (including publish right)
before invoking the graph; AccessMetadata alone does not prove authorization.
"""

from packages.contracts.access import AccessMetadata
from packages.contracts.indexing import PublicationRequest, PublicationResult
from packages.contracts.publication import GenerationCatalog


class DocumentPublicationService:
    def __init__(self, *, catalog: GenerationCatalog) -> None:
        self.catalog = catalog

    async def activate(
        self,
        *,
        request: PublicationRequest,
        access: AccessMetadata,
    ) -> PublicationResult:
        published = await self.catalog.publish(
            source=request.source,
            access=access,
            generation_id=request.generation_id,
        )
        return PublicationResult(
            generation_id=request.generation_id, published=published
        )
