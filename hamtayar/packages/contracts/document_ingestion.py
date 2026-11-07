"""Shared TASK-08 workflow port contracts; free of apps, SDK and frameworks."""

from dataclasses import dataclass
from typing import Protocol

from packages.contracts.access import AccessMetadata
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document import DocumentInput
from packages.contracts.errors import ErrorDetail
from packages.contracts.indexing import (
    IndexingResult,
    PublicationRequest,
    PublicationResult,
)


@dataclass(frozen=True)
class ArtifactOutcome:
    ref: ContentRef | None = None
    error: ErrorDetail | None = None

    def __post_init__(self) -> None:
        if (self.ref is None) == (self.error is None):
            raise ValueError("Exactly one of ref or error is required")


@dataclass(frozen=True)
class ChunkArtifactOutcome(ArtifactOutcome):
    count: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if type(self.count) is not int or self.count < 0:
            raise ValueError("count must be a non-negative integer")


class DocumentWorkflowPorts(Protocol):
    async def load_document(
        self,
        *,
        document: DocumentInput,
        access: AccessMetadata,
    ) -> ArtifactOutcome: ...

    async def parse(
        self,
        *,
        source: SourceVersion,
        loaded: ContentRef,
        filename: str,
        content_type: str,
    ) -> ArtifactOutcome: ...

    async def normalize(
        self,
        *,
        source: SourceVersion,
        parsed: ContentRef,
        profile: str,
    ) -> ArtifactOutcome: ...

    async def chunk(
        self,
        *,
        source: SourceVersion,
        normalized: ContentRef,
        access: AccessMetadata,
        profile: str,
    ) -> ChunkArtifactOutcome: ...

    async def embed(
        self,
        *,
        source: SourceVersion,
        chunks: ContentRef,
    ) -> ArtifactOutcome: ...

    async def index(
        self,
        *,
        source: SourceVersion,
        chunks: ContentRef,
        embeddings: ContentRef,
        access: AccessMetadata,
    ) -> IndexingResult: ...

    async def activate(
        self,
        *,
        request: PublicationRequest,
        access: AccessMetadata,
    ) -> PublicationResult: ...


@dataclass(frozen=True)
class EmbeddingProfile:
    """Portable runtime parameters, mapped from KnowledgeConfiguration in Bootstrap."""

    model_id: str
    dimensions: int

    def __post_init__(self) -> None:
        if not self.model_id.strip() or self.dimensions < 1:
            raise ValueError("Valid embedding model_id and dimensions are required")


@dataclass(frozen=True)
class IndexProfile:
    """Stable generation recipe independent of a particular ingestion module."""

    embedding: EmbeddingProfile
    chunk_profile: str
    recipe_version: str

    def __post_init__(self) -> None:
        if not self.chunk_profile.strip() or not self.recipe_version.strip():
            raise ValueError("Index recipe identifiers must be nonempty")
