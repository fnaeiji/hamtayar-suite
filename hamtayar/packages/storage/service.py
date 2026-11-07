"""The only public storage entry point (S-02).

`packages.contracts.indexing.IndexingRequest` in, `IndexingResult` out on full success. Any failure
raises one of the five typed errors with the operation's `StoreResult` attached.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest, IndexingResult
from packages.contracts.storage import (
    FailureCategory,
    PayloadField,
    StoreFailure,
    StoreResult,
)
from packages.storage.artifacts.repository import LocalArtifactRepository
from packages.storage.exceptions import (
    ChunkValidationError,
    CollectionMismatchError,
    ReadBackMismatchError,
    StoreTimeoutError,
    StoreWriteError,
)
from packages.storage.qdrant.adapter import (
    AdapterPermanentError,
    AdapterTransientError,
    AdapterUnavailableError,
    QdrantAdapter,
    build_payload,
    point_id_for,
)
from packages.storage.qdrant.config import Distance, StorageConfig
from packages.storage.search import SearchFilter, SearchHit, SearchMode, SearchQuery

__all__ = [
    # engine-facing failure taxonomy, re-exported so callers never reach into qdrant/
    "AdapterPermanentError",
    "AdapterTransientError",
    "AdapterUnavailableError",
    "ChunkValidationError",
    "CollectionMismatchError",
    "Distance",
    "LocalArtifactRepository",
    "ReadBackMismatchError",
    "SearchFilter",
    "SearchHit",
    "SearchMode",
    "SearchQuery",
    "StorageConfig",
    "StoreTimeoutError",
    "StoreWriteError",
    "read_chunks",
    "search_lexical_bm25",
    "search_lexical_filter",
    "search_lexical_phrase",
    "search_semantic",
    "store_chunks",
]

_COMPARED_FIELDS = (
    PayloadField.CHUNK_ID,
    PayloadField.SOURCE_ID,
    PayloadField.VERSION,
    PayloadField.GENERATION_ID,
    PayloadField.MODEL_ID,
    PayloadField.TEXT,
    PayloadField.LOCATION,
)


def store_chunks(request: IndexingRequest, *, config: StorageConfig) -> IndexingResult:
    """Store one index generation and verify it by read-back."""
    chunks = list(request.chunks)
    embeddings = list(request.embeddings)

    if not chunks and not embeddings:
        return IndexingResult(
            generation_id=request.generation_id, indexed_count=0, validated=True
        )

    pairs = _reconcile(chunks, embeddings, config)
    adapter = _adapter(config)

    profile = _profile_or_raise(adapter, chunks)
    _require_matching_profile(profile, config, chunks, embeddings[0].vector)

    points: list[tuple[UUID, list[float], dict[str, Any]]] = []
    for chunk, embedding in pairs:
        points.append(
            (
                point_id_for(
                    chunk.source.source.source_id,
                    chunk.source.version,
                    request.generation_id,
                    chunk.chunk_id,
                ),
                list(embedding.vector),
                build_payload(chunk, embedding, request.generation_id),
            )
        )

    _write_all(adapter, points, config)
    verified = _verify_read_back(adapter, points, config)

    return IndexingResult(
        generation_id=request.generation_id, indexed_count=verified, validated=True
    )


def read_chunks(ids: Sequence[UUID], *, config: StorageConfig) -> tuple[Chunk, ...]:
    """Read stored points back as the landed `Chunk` contract, in requested order."""
    requested = list(ids)
    adapter = _adapter(config)

    try:
        found = adapter.read(requested)
    except AdapterUnavailableError as exc:
        raise StoreTimeoutError(
            str(exc),
            result=_read_failure(
                requested,
                {},
                "target unavailable",
                retryable=True,
                category=FailureCategory.TIMEOUT,
            ),
        ) from exc
    except AdapterTransientError as exc:
        raise StoreTimeoutError(
            str(exc),
            result=_read_failure(
                requested,
                {},
                str(exc),
                retryable=True,
                category=FailureCategory.TIMEOUT,
            ),
        ) from exc
    except AdapterPermanentError as exc:
        raise ReadBackMismatchError(
            str(exc), result=_read_failure(requested, {}, str(exc))
        ) from exc

    records: list[Chunk] = []
    failures: list[StoreFailure] = []
    for point_id in requested:
        record = found.get(point_id)
        if record is None:
            failures.append(
                StoreFailure(
                    point_id=point_id,
                    category=FailureCategory.READ_BACK,
                    reason="requested point is not present in the collection",
                )
            )
            continue
        payload, _vector = record
        try:
            records.append(_chunk_from_payload(payload))
        except Exception as exc:  # noqa: BLE001 - malformed payload is a read-back failure
            failures.append(
                StoreFailure(
                    point_id=point_id,
                    chunk_id=payload.get(PayloadField.CHUNK_ID),
                    category=FailureCategory.READ_BACK,
                    reason=f"stored payload is malformed: {exc}",
                )
            )

    if failures:
        result = StoreResult(
            requested=len(requested),
            stored=len(records),
            failed=len(failures),
            failures=tuple(failures),
        )
        raise ReadBackMismatchError("read-back verification failed", result=result)

    return tuple(records)


# ---- search: semantic, unranked lexical, phrase, native BM25


def search_semantic(
    query_vector: Sequence[float],
    *,
    search_filter: SearchFilter,
    limit: int,
    config: StorageConfig,
) -> tuple[SearchHit, ...]:
    """Dense-vector similarity search. The vector is caller-supplied; nothing is embedded here."""
    _require_limit(limit)
    if not query_vector:
        raise ValueError("query_vector must not be empty")
    if len(query_vector) != config.vector_size:
        raise ValueError(
            f"query_vector has dimension {len(query_vector)}, expected {config.vector_size}"
        )
    query = SearchQuery(mode=None, limit=limit, vector=list(query_vector))
    return _adapter(config).search(query, search_filter)


def search_lexical_filter(
    query_text: str,
    *,
    search_filter: SearchFilter,
    limit: int,
    config: StorageConfig,
) -> tuple[SearchHit, ...]:
    """Unranked full-text match: hits carry `score=None` (never a fabricated ranking)."""
    _require_limit(limit)
    text = _require_text(query_text, "query_text")
    query = SearchQuery(mode=SearchMode.FILTER, limit=limit, text=text)
    return _adapter(config).search(query, search_filter)


def search_lexical_phrase(
    phrase: str,
    *,
    search_filter: SearchFilter,
    limit: int,
    config: StorageConfig,
) -> tuple[SearchHit, ...]:
    """Order-sensitive phrase match; the engine path stays inside the Qdrant adapter."""
    _require_limit(limit)
    text = _require_text(phrase, "phrase")
    query = SearchQuery(mode=SearchMode.PHRASE, limit=limit, text=text)
    return _adapter(config).search(query, search_filter)


def search_lexical_bm25(
    query_text: str,
    *,
    search_filter: SearchFilter,
    limit: int,
    config: StorageConfig,
) -> tuple[SearchHit, ...]:
    """Native BM25 ranking; scores come from the engine, ordered descending."""
    _require_limit(limit)
    text = _require_text(query_text, "query_text")
    query = SearchQuery(mode=SearchMode.BM25, limit=limit, text=text)
    return _adapter(config).search(query, search_filter)


def _require_limit(limit: int) -> None:
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")


def _require_text(value: str, name: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    return text


# ---- validation before any write


def _reconcile(
    chunks: list[Chunk], embeddings: list[EmbeddingRecord], config: StorageConfig
) -> list[tuple[Chunk, EmbeddingRecord]]:
    seen: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in seen:
            raise ChunkValidationError(
                f"duplicate chunk_id in request: {chunk.chunk_id}",
                result=_pre_write_failure(chunks, "duplicate chunk_id in request"),
            )
        seen.add(chunk.chunk_id)

    by_chunk_id: dict[str, EmbeddingRecord] = {}
    for embedding in embeddings:
        if embedding.chunk_id in by_chunk_id:
            raise ChunkValidationError(
                f"duplicate embedding for chunk_id {embedding.chunk_id}",
                result=_pre_write_failure(chunks, "duplicate embedding chunk_id"),
            )
        by_chunk_id[embedding.chunk_id] = embedding

    chunk_ids = {chunk.chunk_id for chunk in chunks}
    missing = chunk_ids - set(by_chunk_id)
    extra = set(by_chunk_id) - chunk_ids
    if missing or extra:
        raise ChunkValidationError(
            "chunks and embeddings must match 1:1 by chunk_id "
            f"(missing={sorted(missing)}, extra={sorted(extra)})",
            result=_pre_write_failure(
                chunks, "chunk/embedding reconciliation failed", embeddings=embeddings
            ),
        )

    model_ids = {embedding.model_id for embedding in embeddings}
    if len(model_ids) != 1:
        raise ChunkValidationError(
            f"mixed model_id in one request: {sorted(model_ids)}",
            result=_pre_write_failure(chunks, "mixed model_id"),
        )

    dimensions = {len(embedding.vector) for embedding in embeddings}
    if len(dimensions) != 1:
        raise ChunkValidationError(
            f"mixed vector dimension in one request: {sorted(dimensions)}",
            result=_pre_write_failure(chunks, "mixed vector dimension"),
        )
    dimension = dimensions.pop()
    if dimension == 0:
        raise ChunkValidationError(
            "embedding vector must not be empty",
            result=_pre_write_failure(chunks, "empty vector"),
        )
    if dimension != config.vector_size:
        raise CollectionMismatchError(
            f"embedding dimension {dimension} does not match configured vector size {config.vector_size}",
            result=_pre_write_failure(
                chunks,
                "embedding dimension mismatch",
                category=FailureCategory.MISMATCH,
            ),
        )

    return [(chunk, by_chunk_id[chunk.chunk_id]) for chunk in chunks]


def _pre_write_failure(
    chunks: list[Chunk],
    reason: str,
    category: FailureCategory = FailureCategory.VALIDATION,
    embeddings: Sequence[EmbeddingRecord] = (),
    retryable: bool = False,
) -> StoreResult:
    """Failure detail for a request rejected before any write.

    `requested` counts the request items that could not be validated: every chunk, plus every
    embedding that names a `chunk_id` no chunk in the request provides. Orphan embeddings are named
    individually instead of collapsing into a zero-failure summary.
    """
    failures = [
        StoreFailure(
            chunk_id=chunk.chunk_id,
            category=category,
            reason=reason,
            retryable=retryable,
        )
        for chunk in chunks
    ]
    known = {chunk.chunk_id for chunk in chunks}
    orphaned: set[str] = set()
    for embedding in embeddings:
        if embedding.chunk_id in known or embedding.chunk_id in orphaned:
            continue
        orphaned.add(embedding.chunk_id)
        failures.append(
            StoreFailure(
                chunk_id=embedding.chunk_id,
                category=category,
                reason=f"embedding has no matching chunk in the request: {embedding.chunk_id}",
                retryable=retryable,
            )
        )
    return StoreResult(
        requested=len(failures),
        stored=0,
        failed=len(failures),
        failures=tuple(failures),
    )


def _adapter(config: StorageConfig) -> QdrantAdapter:
    return QdrantAdapter(config)


def _profile_or_raise(adapter: QdrantAdapter, chunks: list[Chunk]):
    try:
        return adapter.profile()
    except AdapterUnavailableError as exc:
        raise StoreTimeoutError(
            str(exc),
            result=_pre_write_failure(
                chunks,
                "target unavailable",
                category=FailureCategory.TIMEOUT,
                retryable=True,
            ),
        ) from exc
    except AdapterTransientError as exc:
        raise StoreTimeoutError(
            str(exc),
            result=_pre_write_failure(
                chunks, str(exc), category=FailureCategory.TIMEOUT, retryable=True
            ),
        ) from exc
    except AdapterPermanentError as exc:
        raise CollectionMismatchError(
            str(exc),
            result=_pre_write_failure(
                chunks, str(exc), category=FailureCategory.MISMATCH
            ),
        ) from exc


def _require_matching_profile(
    profile, config: StorageConfig, chunks: list[Chunk], vector
) -> None:
    mismatches = []
    if profile.vector_name != config.vector_name:
        mismatches.append(
            f"vector_name expected {config.vector_name!r} got {profile.vector_name!r}"
        )
    if profile.vector_size != config.vector_size:
        mismatches.append(
            f"vector_size expected {config.vector_size} got {profile.vector_size}"
        )
    if profile.distance != config.distance.value:
        mismatches.append(
            f"distance expected {config.distance.value!r} got {profile.distance!r}"
        )
    if len(vector) != profile.vector_size:
        mismatches.append(
            f"embedding length {len(vector)} != target size {profile.vector_size}"
        )
    if mismatches:
        raise CollectionMismatchError(
            "target collection profile does not match: " + "; ".join(mismatches),
            result=_pre_write_failure(
                chunks, "; ".join(mismatches), category=FailureCategory.MISMATCH
            ),
        )


# ---- write and read-back


def _write_all(
    adapter: QdrantAdapter,
    points: list[tuple[UUID, list[float], dict[str, Any]]],
    config: StorageConfig,
) -> None:
    groups = [
        points[index : index + config.batch_size]
        for index in range(0, len(points), config.batch_size)
    ]
    for position, group in enumerate(groups):
        try:
            adapter.write_group(group)
        except (AdapterTransientError, AdapterPermanentError) as exc:
            raise StoreWriteError(
                str(exc),
                result=_write_failure(
                    points,
                    groups,
                    position,
                    str(exc),
                    retryable=isinstance(exc, AdapterTransientError),
                ),
            ) from exc
        except AdapterUnavailableError as exc:
            raise StoreTimeoutError(
                str(exc),
                result=_write_failure(
                    points,
                    groups,
                    position,
                    str(exc),
                    retryable=True,
                    category=FailureCategory.TIMEOUT,
                ),
            ) from exc


def _write_failure(
    points,
    groups,
    failed_position: int,
    reason: str,
    *,
    retryable: bool,
    category: FailureCategory = FailureCategory.WRITE,
) -> StoreResult:
    """Failure detail for a write that stopped part-way through the batches.

    `stored` counts the points of the batches Qdrant already acknowledged, so
    `requested == stored + failed` always holds and nothing is silently dropped. On a write failure
    `stored` therefore means "acknowledged by the target", not "verified by read-back"; read-back
    verification is required before a successful `IndexingResult` is ever returned.
    """
    acknowledged = sum(len(group) for group in groups[:failed_position])
    failed_group = groups[failed_position]
    failures = [
        StoreFailure(
            point_id=point_id,
            chunk_id=payload.get(PayloadField.CHUNK_ID),
            category=category,
            reason=reason,
            retryable=retryable,
        )
        for point_id, _vector, payload in failed_group
    ]
    for later_group in groups[failed_position + 1 :]:
        for point_id, _vector, payload in later_group:
            failures.append(
                StoreFailure(
                    point_id=point_id,
                    chunk_id=payload.get(PayloadField.CHUNK_ID),
                    category=FailureCategory.UNATTEMPTED,
                    reason="not attempted because an earlier write group failed",
                )
            )
    return StoreResult(
        requested=len(points),
        stored=acknowledged,
        failed=len(failures),
        failures=tuple(failures),
    )


def _verify_read_back(
    adapter: QdrantAdapter,
    points: list[tuple[UUID, list[float], dict[str, Any]]],
    config: StorageConfig,
) -> int:
    ids = [point_id for point_id, _vector, _payload in points]
    try:
        found = adapter.read(ids)
    except AdapterUnavailableError as exc:
        raise StoreTimeoutError(
            str(exc),
            result=_read_failure(
                ids, {}, str(exc), retryable=True, category=FailureCategory.TIMEOUT
            ),
        ) from exc
    except AdapterTransientError as exc:
        raise StoreTimeoutError(
            str(exc),
            result=_read_failure(
                ids, {}, str(exc), retryable=True, category=FailureCategory.TIMEOUT
            ),
        ) from exc
    except AdapterPermanentError as exc:
        raise ReadBackMismatchError(
            str(exc), result=_read_failure(ids, {}, str(exc))
        ) from exc

    verified = 0
    failures: list[StoreFailure] = []
    for point_id, _vector, payload in points:
        chunk_id = payload.get(PayloadField.CHUNK_ID)
        record = found.get(point_id)
        if record is None:
            failures.append(
                StoreFailure(
                    point_id=point_id,
                    chunk_id=chunk_id,
                    category=FailureCategory.READ_BACK,
                    reason="point is missing after the write",
                )
            )
            continue
        stored_payload, stored_vector = record
        mismatched = [
            field
            for field in _COMPARED_FIELDS
            if stored_payload.get(field) != payload.get(field)
        ]
        if mismatched:
            failures.append(
                StoreFailure(
                    point_id=point_id,
                    chunk_id=chunk_id,
                    category=FailureCategory.READ_BACK,
                    reason="payload mismatch: " + ", ".join(mismatched),
                )
            )
            continue
        if len(stored_vector) != config.vector_size:
            failures.append(
                StoreFailure(
                    point_id=point_id,
                    chunk_id=chunk_id,
                    category=FailureCategory.READ_BACK,
                    reason=f"vector dimension {len(stored_vector)} != {config.vector_size}",
                )
            )
            continue
        verified += 1

    if failures:
        result = StoreResult(
            requested=len(points),
            stored=verified,
            failed=len(failures),
            failures=tuple(failures),
        )
        raise ReadBackMismatchError("read-back verification failed", result=result)

    return verified


def _read_failure(
    ids: Sequence[UUID],
    found: dict,
    reason: str,
    *,
    retryable: bool = False,
    category: FailureCategory = FailureCategory.READ_BACK,
) -> StoreResult:
    missing = [point_id for point_id in ids if point_id not in found]
    failures = tuple(
        StoreFailure(
            point_id=point_id, category=category, reason=reason, retryable=retryable
        )
        for point_id in (missing or list(ids))
    )
    return StoreResult(
        requested=len(ids),
        stored=len(found),
        failed=len(failures),
        failures=failures,
    )


def _chunk_from_payload(payload: dict[str, Any]) -> Chunk:
    location = payload.get(PayloadField.LOCATION)
    return Chunk(
        chunk_id=payload[PayloadField.CHUNK_ID],
        source=SourceVersion(
            source=SourceRef(
                source_id=payload[PayloadField.SOURCE_ID],
                knowledge_space_id=payload[PayloadField.KNOWLEDGE_SPACE_ID],
                source_type=payload[PayloadField.SOURCE_TYPE],
            ),
            version=payload[PayloadField.VERSION],
        ),
        kind=payload[PayloadField.KIND],
        text=payload[PayloadField.TEXT],
        access=AccessMetadata(
            tenant_id=payload[PayloadField.TENANT_ID],
            acl_principals=payload[PayloadField.ACL_PRINCIPALS],
        ),
        location=SourceLocation(**location) if location else None,
        symbol_id=payload.get(PayloadField.SYMBOL_ID),
        metadata=payload.get(PayloadField.METADATA) or {},
    )
