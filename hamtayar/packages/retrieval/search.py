"""Retrieval semantics: validate the request, resolve the authorized filter, ask storage, map back.

Layering: this module owns *what* to search for and how to interpret the answer. Engine access stays
inside `packages/storage` (single Qdrant adapter). Access restrictions are always applied inside the
query — nothing is filtered after retrieval.

Contract mapping (no contract change): `retrieval_method="semantic"` with the engine's similarity
score; the unranked lexical modes will map to `"keyword"` with `score is None` (see research.md).
"""

from __future__ import annotations

from collections.abc import Sequence

from packages.contracts.access import AccessScope
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.retrieval import RetrievalResponse, SearchResult
from packages.storage import service as storage_service
from packages.storage.service import SearchHit, StorageConfig

from .exceptions import SearchEngineError, SearchMappingError, SearchValidationError
from .filters import build_search_filter
from .query_text import QueryNormalizer, normalize_phrase, normalize_query

__all__ = [
    "MAX_LIMIT",
    "search_lexical_bm25",
    "search_lexical_filter",
    "search_lexical_phrase",
    "search_semantic",
]

MAX_LIMIT = 100  # aligns with SearchRequest.top_k (ge=1, le=100)

#: Storage's semantic entry point, aliased so tests can install a fake without touching storage.
search_storage_semantic = storage_service.search_semantic

#: Storage's lexical entry points, aliased so tests can install a fake without touching storage.
search_storage_lexical_filter = storage_service.search_lexical_filter
search_storage_lexical_phrase = storage_service.search_lexical_phrase
search_storage_lexical_bm25 = storage_service.search_lexical_bm25

#: Engine-facing failures exposed by the storage boundary; translated into `SearchEngineError`.
ENGINE_FAILURES = (
    storage_service.AdapterTransientError,
    storage_service.AdapterUnavailableError,
    storage_service.AdapterPermanentError,
)


def search_semantic(
    query_vector: Sequence[float],
    *,
    scope: AccessScope | None,
    config: StorageConfig,
    limit: int = 10,
    requested_source_ids: list[str] | None = None,
    generation_ids: list[str] | None = None,
) -> RetrievalResponse:
    """Dense-vector semantic search over authorized chunks.

    Args:
        query_vector: caller-supplied embedding; this layer never embeds a query.
        scope: trusted access scope; missing or unusable → `SearchScopeRequiredError` (fail closed).
        config: storage configuration (engine URL, collection, vector name/size).
        limit: result count, `1 <= limit <= MAX_LIMIT`.
        requested_source_ids: optional narrowing; never widens the scope.
        generation_ids: optional generation restriction.

    Raises:
        SearchValidationError: invalid limit, empty vector or dimension mismatch.
        SearchScopeRequiredError: missing/insufficient access scope.
        SearchMappingError: a stored record cannot be mapped to the retrieval contracts.
        Exception: storage/engine failures propagate unchanged (they already carry an `ErrorCode`).
    """
    _validate_limit(limit)
    _validate_vector(query_vector, config.vector_size)

    search_filter = build_search_filter(
        scope,
        requested_source_ids=requested_source_ids,
        generation_ids=generation_ids,
    )
    if search_filter is None:
        return RetrievalResponse(results=[])  # deny: no query executed

    try:
        hits = search_storage_semantic(
            list(query_vector), search_filter=search_filter, limit=limit, config=config
        )
    except ENGINE_FAILURES as exc:
        raise SearchEngineError(f"search engine failure: {exc}") from exc
    return RetrievalResponse(
        results=[_to_search_result(hit, method="semantic") for hit in hits]
    )


def search_lexical_filter(
    query_text: str,
    *,
    scope: AccessScope | None,
    config: StorageConfig,
    normalizer: QueryNormalizer,
    limit: int = 10,
    requested_source_ids: list[str] | None = None,
    generation_ids: list[str] | None = None,
) -> RetrievalResponse:
    """Unranked lexical filtering: hits are matches, never a ranking, so `score` stays None.

    The query is normalized with the injected document normalizer before it reaches the engine.
    """
    return _run_lexical(
        query_text,
        normalizer=normalizer,
        phrase=False,
        scope=scope,
        config=config,
        limit=limit,
        requested_source_ids=requested_source_ids,
        generation_ids=generation_ids,
    )


def search_lexical_phrase(
    phrase: str,
    *,
    scope: AccessScope | None,
    config: StorageConfig,
    normalizer: QueryNormalizer,
    limit: int = 10,
    requested_source_ids: list[str] | None = None,
    generation_ids: list[str] | None = None,
) -> RetrievalResponse:
    """Order-sensitive phrase search; matches are unranked and expose ``score=None``."""
    return _run_lexical(
        phrase,
        normalizer=normalizer,
        phrase=True,
        scope=scope,
        config=config,
        limit=limit,
        requested_source_ids=requested_source_ids,
        generation_ids=generation_ids,
    )


def search_lexical_bm25(
    query_text: str,
    *,
    scope: AccessScope | None,
    config: StorageConfig,
    normalizer: QueryNormalizer,
    limit: int = 10,
    requested_source_ids: list[str] | None = None,
    generation_ids: list[str] | None = None,
) -> RetrievalResponse:
    """Native BM25 relevance ranking over authorized chunks.

    The scores are the engine's own BM25 values in the engine's order — nothing is computed,
    re-ranked or fused here. The query is normalized with the injected document normalizer.

    Contract representation: `retrieval_method="keyword"` with a numeric score. This is
    indistinguishable, by field alone, from a scored lexical result; the operation identity plus the
    score invariant (`keyword` + score ⇒ BM25, `keyword` + `None` ⇒ unranked match) carries the
    distinction until T030 decides whether `SearchMode` gains an explicit `bm25` value.
    """
    _validate_limit(limit)
    try:
        text = normalize_query(query_text, normalizer=normalizer)
    except ValueError as exc:
        raise SearchValidationError(str(exc)) from exc

    search_filter = build_search_filter(
        scope,
        requested_source_ids=requested_source_ids,
        generation_ids=generation_ids,
    )
    if search_filter is None:
        return RetrievalResponse(results=[])  # deny: no query executed

    try:
        hits = search_storage_lexical_bm25(
            text, search_filter=search_filter, limit=limit, config=config
        )
    except ENGINE_FAILURES as exc:
        raise SearchEngineError(f"search engine failure: {exc}") from exc
    return RetrievalResponse(
        results=[_to_search_result(hit, method="keyword") for hit in hits]
    )


def _run_lexical(
    value: str,
    *,
    normalizer: QueryNormalizer,
    phrase: bool,
    scope: AccessScope | None,
    config: StorageConfig,
    limit: int,
    requested_source_ids: list[str] | None,
    generation_ids: list[str] | None,
) -> RetrievalResponse:
    _validate_limit(limit)
    try:
        text = (
            normalize_phrase(value, normalizer=normalizer)
            if phrase
            else normalize_query(value, normalizer=normalizer)
        )
    except ValueError as exc:
        raise SearchValidationError(str(exc)) from exc

    search_filter = build_search_filter(
        scope,
        requested_source_ids=requested_source_ids,
        generation_ids=generation_ids,
    )
    if search_filter is None:
        return RetrievalResponse(results=[])  # deny: no query executed

    storage_call = (
        search_storage_lexical_phrase if phrase else search_storage_lexical_filter
    )
    try:
        hits = storage_call(
            text, search_filter=search_filter, limit=limit, config=config
        )
    except ENGINE_FAILURES as exc:
        raise SearchEngineError(f"search engine failure: {exc}") from exc
    return RetrievalResponse(
        results=[_to_search_result(hit, method="keyword") for hit in hits]
    )


def _validate_limit(limit: int) -> None:
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= MAX_LIMIT
    ):
        raise SearchValidationError(
            f"limit must be an integer between 1 and {MAX_LIMIT}, got {limit!r}"
        )


def _validate_vector(query_vector: Sequence[float], expected_size: int) -> None:
    if not query_vector:
        raise SearchValidationError("query_vector must not be empty")
    if len(query_vector) != expected_size:
        raise SearchValidationError(
            f"query_vector has dimension {len(query_vector)}, expected {expected_size}"
        )


def _to_search_result(hit: SearchHit, *, method: str) -> SearchResult:
    """Map a storage hit onto the shared contract.

    `method` is the retrieval-level label: `"semantic"` keeps the similarity score, `"keyword"`
    carries either no score (unranked full-text/phrase) or the engine's BM25 score.
    """
    try:
        source = SourceVersion(
            source=SourceRef(
                source_id=hit.source_id,
                knowledge_space_id=hit.knowledge_space_id,
                source_type=hit.source_type,
            ),
            version=hit.version,
        )
        return SearchResult(
            evidence_id=hit.chunk_id or str(hit.point_id),
            source=source,
            generation_id=hit.generation_id,
            retrieval_method=method,
            text=hit.text,
            location=SourceLocation(**hit.location) if hit.location else None,
            score=hit.score,
        )
    except Exception as exc:
        raise SearchMappingError(
            f"stored record {hit.point_id} cannot be mapped to SearchResult: {exc}"
        ) from exc
