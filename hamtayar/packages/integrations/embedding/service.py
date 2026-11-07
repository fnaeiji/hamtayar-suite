"""Embedding batching and contract validation; vendor SDK behind injected port."""

import math
from collections.abc import Sequence
from typing import Protocol

from packages.contracts.artifacts import ArtifactRepository
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document_ingestion import ArtifactOutcome, EmbeddingProfile
from packages.contracts.errors import ErrorCode, ErrorDetail
from packages.contracts.indexing import EmbeddingRecord


class EmbeddingProvider(Protocol):
    async def embed_texts(
        self,
        texts: Sequence[str],
        *,
        model_id: str,
    ) -> Sequence[Sequence[float]]: ...


class EmbeddingService:
    def __init__(
        self,
        *,
        artifacts: ArtifactRepository,
        provider: EmbeddingProvider,
        spec: EmbeddingProfile,
        batch_size: int,
        normalize_embeddings: bool = True,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.artifacts = artifacts
        self.provider = provider
        self.spec = spec
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings

    async def embed(
        self,
        *,
        source: SourceVersion,
        chunks: ContentRef,
    ) -> ArtifactOutcome:
        try:
            result = await self.artifacts.get_chunks(ref=chunks, source=source)
            if not result.chunks:
                raise ValueError("Cannot embed empty chunks")
            if any(chunk.source != source for chunk in result.chunks):
                raise ValueError("Embedding source mismatch")
            spec = self.spec
            records: list[EmbeddingRecord] = []
            for start in range(0, len(result.chunks), self.batch_size):
                batch = result.chunks[start : start + self.batch_size]
                vectors = list(
                    await self.provider.embed_texts(
                        [chunk.text for chunk in batch],
                        model_id=spec.model_id,
                    )
                )
                if len(vectors) != len(batch):
                    raise ValueError("Incomplete embedding batch")
                for chunk, vector in zip(batch, vectors, strict=True):
                    numbers = list(vector)
                    if len(numbers) != spec.dimensions or any(
                        type(v) not in (float, int) or not math.isfinite(v)
                        for v in numbers
                    ):
                        raise ValueError("Embedding vector invalid")
                    if self.normalize_embeddings:
                        norm = math.sqrt(math.fsum(float(v) ** 2 for v in numbers))
                        if norm == 0 or not math.isfinite(norm):
                            raise ValueError("Invalid vector norm")
                        numbers = [float(v) / norm for v in numbers]
                    records.append(
                        EmbeddingRecord(
                            chunk_id=chunk.chunk_id,
                            model_id=spec.model_id,
                            vector=[float(v) for v in numbers],
                        )
                    )
            ref = await self.artifacts.put_embeddings(source=source, records=records)
            return ArtifactOutcome(ref=ref)
        except FileNotFoundError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.SOURCE_NOT_FOUND,
                    message="Chunk artifact unavailable",
                )
            )
        except ValueError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR, message="Invalid embedding result"
                )
            )
        # Provider exception is intentionally propagated: TASK-07 node retry
        # can classify transient errors. No fake production provider is used.
