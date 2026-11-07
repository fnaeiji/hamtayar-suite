"""Internal typed artifact interfaces shared across ingestion and storage."""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Literal, Protocol

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import ChunkingResult
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document import ParsedDocument
from packages.contracts.indexing import EmbeddingRecord


class ArtifactRepository(Protocol):
    async def stage_raw(
        self,
        *,
        source: SourceVersion,
        original: ContentRef,
        access: AccessMetadata,
    ) -> ContentRef: ...

    def materialize_raw(
        self,
        *,
        ref: ContentRef,
        source: SourceVersion,
    ) -> AbstractAsyncContextManager[Path]: ...

    async def put_parsed(
        self,
        *,
        source: SourceVersion,
        document: ParsedDocument,
        stage: Literal["parsed", "normalized"],
    ) -> ContentRef: ...

    async def get_parsed(
        self,
        *,
        ref: ContentRef,
        source: SourceVersion,
    ) -> ParsedDocument: ...

    async def put_chunks(
        self,
        *,
        source: SourceVersion,
        result: ChunkingResult,
    ) -> ContentRef: ...

    async def get_chunks(
        self,
        *,
        ref: ContentRef,
        source: SourceVersion,
    ) -> ChunkingResult: ...

    async def put_embeddings(
        self,
        *,
        source: SourceVersion,
        records: Sequence[EmbeddingRecord],
    ) -> ContentRef: ...

    async def get_embeddings(
        self,
        *,
        ref: ContentRef,
        source: SourceVersion,
    ) -> list[EmbeddingRecord]: ...
