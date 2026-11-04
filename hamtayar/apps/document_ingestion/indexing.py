"""Indexing integration boundary: hand a prepared generation to Storage.

Framework-independent on purpose: no LangGraph, no worker, no workflow state. The ingestion
workflow node (I-01A follow-up) calls `index_generation()` and decides how to persist the failure.

Flow: Chunk/EmbeddingRecord (real contracts) -> IndexingRequest -> store_chunks() -> IndexingResult
      and on failure: storage exception -> ErrorDetail -> IndexingFailed (raised, never returned)
"""

from __future__ import annotations

from typing import Sequence

from apps.document_ingestion.storage_errors import STORAGE_ERROR_TYPES, to_error_detail
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceVersion
from packages.contracts.errors import ErrorDetail
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest, IndexingResult
from packages.contracts.storage import StoreResult
from packages.storage.service import StorageConfig, store_chunks

__all__ = ["IndexingFailed", "index_generation"]


class IndexingFailed(Exception):
    """The generation was not stored. Carries the shared `ErrorDetail` and the full `StoreResult`."""

    def __init__(self, detail: ErrorDetail, *, store_result: StoreResult) -> None:
        super().__init__(detail.message)
        self.detail = detail
        self.store_result = store_result

    @property
    def retryable(self) -> bool:
        return self.detail.retryable

    def to_error_detail(self) -> ErrorDetail:
        return self.detail


def index_generation(
    chunks: Sequence[Chunk],
    embeddings: Sequence[EmbeddingRecord],
    *,
    source: SourceVersion,
    generation_id: str,
    config: StorageConfig,
) -> IndexingResult:
    """Store one prepared generation and return the verified `IndexingResult`.

    Raises `IndexingFailed` for every failure Storage reports; unexpected errors propagate
    unchanged. A successful return means Storage verified the read-back (`validated is True`).
    """
    chunk_list = list(chunks)
    embedding_list = list(embeddings)

    _require_single_source(chunk_list, source)

    request = IndexingRequest(
        source=source,
        generation_id=generation_id,
        chunks=chunk_list,
        embeddings=embedding_list,
    )

    try:
        result = store_chunks(request, config=config)
    except STORAGE_ERROR_TYPES as exc:
        raise IndexingFailed(to_error_detail(exc), store_result=exc.result) from exc

    if not result.validated:
        raise RuntimeError(
            "storage returned an IndexingResult that was not read-back verified; "
            "refusing to report success"
        )
    return result


def _require_single_source(chunks: list[Chunk], source: SourceVersion) -> None:
    """Guard the generation/source pairing Storage does not check itself."""
    for chunk in chunks:
        if chunk.source != source:
            raise ValueError(
                f"chunk {chunk.chunk_id!r} belongs to source "
                f"{chunk.source.source.source_id!r}/{chunk.source.version!r}, "
                f"not {source.source.source_id!r}/{source.version!r}"
            )
