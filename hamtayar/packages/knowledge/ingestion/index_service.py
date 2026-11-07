"""Assemble references into the existing Qdrant store_chunks contract."""

import asyncio
import hashlib
import json
from collections.abc import Callable

from packages.contracts.access import AccessMetadata
from packages.contracts.artifacts import ArtifactRepository
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document_ingestion import IndexProfile
from packages.contracts.indexing import IndexingRequest, IndexingResult
from packages.contracts.publication import GenerationCatalog
from packages.storage.service import StorageConfig


class DocumentIndexService:
    def __init__(
        self,
        *,
        artifacts: ArtifactRepository,
        catalog: GenerationCatalog,
        config: StorageConfig,
        profile: IndexProfile,
        store: Callable[..., IndexingResult] | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.catalog = catalog
        self.config = config
        self.profile = profile
        if store is None:
            # Lazy import permits testing without a real Qdrant SDK.
            from packages.storage.service import store_chunks

            store = store_chunks
        self.store = store

    async def index(
        self,
        *,
        source: SourceVersion,
        chunks: ContentRef,
        embeddings: ContentRef,
        access: AccessMetadata,
    ) -> IndexingResult:
        chunk_result = await self.artifacts.get_chunks(ref=chunks, source=source)
        vectors = await self.artifacts.get_embeddings(ref=embeddings, source=source)
        if not chunk_result.chunks or len(vectors) != len(chunk_result.chunks):
            raise ValueError("Index requires nonempty 1:1 chunk/vector alignment")
        ids = [c.chunk_id for c in chunk_result.chunks]
        vector_ids = [e.chunk_id for e in vectors]
        if (
            len(set(ids)) != len(ids)
            or len(set(vector_ids)) != len(vector_ids)
            or set(ids) != set(vector_ids)
        ):
            raise ValueError("Invalid or duplicated vector identities")
        if any(c.source != source or c.access != access for c in chunk_result.chunks):
            raise ValueError("Chunk identity or ACL mismatch")
        spec = self.profile.embedding
        if any(
            e.model_id != spec.model_id or len(e.vector) != spec.dimensions
            for e in vectors
        ):
            raise ValueError("Embedding configuration mismatch")
        if spec.dimensions != self.config.vector_size:
            raise ValueError("Qdrant collection vector dimension mismatch")
        payload = [
            access.tenant_id,
            source.model_dump(mode="json"),
            {
                "embedding": {"model_id": spec.model_id, "dimensions": spec.dimensions},
                "chunk_profile": self.profile.chunk_profile,
                "recipe_version": self.profile.recipe_version,
            },
            self.config.collection_name,
            self.config.vector_name,
            self.config.vector_size,
            ids,
            chunks.uri,
            embeddings.uri,
        ]
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        generation_id = f"doc-{digest}"
        request = IndexingRequest(
            source=source,
            generation_id=generation_id,
            chunks=chunk_result.chunks,
            embeddings=vectors,
        )
        # The existing storage entry point is synchronous; never block the Graph event loop.
        result = await asyncio.to_thread(self.store, request, config=self.config)
        if (
            not isinstance(result, IndexingResult)
            or result.generation_id != generation_id
        ):
            raise ValueError("Storage returned an unexpected generation")
        if not result.validated or result.indexed_count != len(chunk_result.chunks):
            return IndexingResult(
                generation_id=generation_id,
                indexed_count=result.indexed_count,
                validated=False,
            )
        await self.catalog.mark_validated(
            source=source,
            access=access,
            generation_id=generation_id,
            indexed_count=result.indexed_count,
        )
        return result
