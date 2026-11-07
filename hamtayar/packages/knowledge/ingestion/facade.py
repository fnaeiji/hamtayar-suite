"""Container-composed delegation to seven injected ingestion services.

Intentionally imports only shared contracts and no domain implementations.
"""

from packages.contracts.access import AccessMetadata
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document import DocumentInput
from packages.contracts.document_ingestion import (
    ArtifactOutcome,
    ChunkArtifactOutcome,
    DocumentWorkflowPorts,
)
from packages.contracts.indexing import (
    IndexingResult,
    PublicationRequest,
    PublicationResult,
)


class DefaultDocumentWorkflowPorts(DocumentWorkflowPorts):
    def __init__(
        self,
        *,
        loader,
        parser,
        normalizer,
        chunker,
        embedder,
        indexer,
        publisher,
    ) -> None:
        self.loader, self.parser, self.normalizer = loader, parser, normalizer
        self.chunker, self.embedder, self.indexer, self.publisher = (
            chunker,
            embedder,
            indexer,
            publisher,
        )

    async def load_document(
        self,
        *,
        document: DocumentInput,
        access: AccessMetadata,
    ) -> ArtifactOutcome:
        return await self.loader.load_document(document=document, access=access)

    async def parse(
        self,
        *,
        source: SourceVersion,
        loaded: ContentRef,
        filename: str,
        content_type: str,
    ) -> ArtifactOutcome:
        return await self.parser.parse(
            source=source, loaded=loaded, filename=filename, content_type=content_type
        )

    async def normalize(
        self,
        *,
        source: SourceVersion,
        parsed: ContentRef,
        profile: str,
    ) -> ArtifactOutcome:
        return await self.normalizer.normalize(
            source=source, parsed=parsed, profile=profile
        )

    async def chunk(
        self,
        *,
        source: SourceVersion,
        normalized: ContentRef,
        access: AccessMetadata,
        profile: str,
    ) -> ChunkArtifactOutcome:
        return await self.chunker.chunk(
            source=source, normalized=normalized, access=access, profile=profile
        )

    async def embed(
        self,
        *,
        source: SourceVersion,
        chunks: ContentRef,
    ) -> ArtifactOutcome:
        return await self.embedder.embed(source=source, chunks=chunks)

    async def index(
        self,
        *,
        source: SourceVersion,
        chunks: ContentRef,
        embeddings: ContentRef,
        access: AccessMetadata,
    ) -> IndexingResult:
        return await self.indexer.index(
            source=source, chunks=chunks, embeddings=embeddings, access=access
        )

    async def activate(
        self,
        *,
        request: PublicationRequest,
        access: AccessMetadata,
    ) -> PublicationResult:
        return await self.publisher.activate(request=request, access=access)
