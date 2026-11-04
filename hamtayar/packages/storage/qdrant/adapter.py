"""The one production module that talks to Qdrant.

Everything third-party lives here: the client, its point/vector types, its distance enum and its
exceptions. Callers above this module only see project-owned types.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from packages.contracts.chunks import Chunk
from packages.contracts.indexing import EmbeddingRecord
from packages.contracts.storage import PayloadField
from packages.storage.search import SearchFilter, SearchHit, SearchMode, SearchQuery

from .config import Distance, StorageConfig

RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

#: Payload field carrying the searchable text; the full-text/BM25 index lives on this key.
TEXT_FIELD = PayloadField.TEXT

_DISTANCE_TO_SDK = {
    Distance.COSINE: rest.Distance.COSINE,
    Distance.DOT: rest.Distance.DOT,
    Distance.EUCLID: rest.Distance.EUCLID,
    Distance.MANHATTAN: rest.Distance.MANHATTAN,
}


class AdapterTransientError(Exception):
    """A failure that may succeed on retry (timeout, rate limit, temporary server status)."""


class AdapterPermanentError(Exception):
    """A failure that will not change on retry (rejected request, malformed response)."""


class AdapterUnavailableError(Exception):
    """The target could not be reached at all."""


@dataclass(frozen=True)
class TargetCollectionProfile:
    """Vector profile read from the target collection."""

    collection_name: str
    vector_name: str
    vector_size: int
    distance: str


def point_id_for(
    source_id: str, version: str, generation_id: str, chunk_id: str
) -> UUID:
    """Deterministic point identity; inputs are JSON-encoded, never delimiter-joined."""
    return uuid.uuid5(
        uuid.NAMESPACE_URL, json.dumps([source_id, version, generation_id, chunk_id])
    )


def _as_uuid(value: Any) -> Any:
    """The client may hand ids back as strings; the public boundary always speaks UUID."""
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return value


def build_payload(
    chunk: Chunk, embedding: EmbeddingRecord, generation_id: str
) -> dict[str, Any]:
    """Map landed contract values onto the single shared payload definition."""
    source = chunk.source
    return {
        PayloadField.CHUNK_ID: chunk.chunk_id,
        PayloadField.GENERATION_ID: generation_id,
        PayloadField.MODEL_ID: embedding.model_id,
        PayloadField.SOURCE_ID: source.source.source_id,
        PayloadField.VERSION: source.version,
        PayloadField.KNOWLEDGE_SPACE_ID: source.source.knowledge_space_id,
        PayloadField.SOURCE_TYPE: source.source.source_type,
        PayloadField.KIND: chunk.kind,
        PayloadField.TEXT: chunk.text,
        PayloadField.LOCATION: chunk.location.model_dump()
        if chunk.location is not None
        else None,
        PayloadField.TENANT_ID: chunk.access.tenant_id,
        PayloadField.ACL_PRINCIPALS: list(chunk.access.acl_principals),
        PayloadField.SYMBOL_ID: chunk.symbol_id,
        PayloadField.METADATA: dict(chunk.metadata),
    }


def _chain(exc: BaseException):
    """Yield the exception and its cause/context chain (cycle-safe)."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _translate(exc: BaseException) -> Exception:
    """Classify an exception into the adapter's own project-owned error taxonomy."""
    if isinstance(
        exc, (AdapterTransientError, AdapterPermanentError, AdapterUnavailableError)
    ):
        return exc

    chain = list(_chain(exc))

    for link in chain:
        status = getattr(link, "status_code", None)
        if status is not None:
            if status in RETRYABLE_STATUSES:
                return AdapterTransientError(str(exc))
            return AdapterPermanentError(str(exc))

    names = [type(link).__name__ for link in chain]
    # "cannot reach the target at all" wins over "the target was slow"
    if any(
        token in name
        for name in names
        for token in ("Connect", "Network", "Protocol", "ResponseHandling", "Proxy")
    ) or any(isinstance(link, (ConnectionError, OSError)) for link in chain[:-1]):
        if any("Timeout" in name or "TimedOut" in name for name in names):
            return AdapterUnavailableError(str(exc))
        return AdapterUnavailableError(str(exc))
    if any("Timeout" in name for name in names) or any(
        isinstance(link, (TimeoutError, socket.timeout)) for link in chain
    ):
        return AdapterTransientError(str(exc))
    if isinstance(exc, OSError):
        return AdapterUnavailableError(str(exc))
    return AdapterPermanentError(str(exc))


class QdrantAdapter:
    """Thin, retrying wrapper over the Qdrant client. No business decisions live here."""

    def __init__(self, config: StorageConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = QdrantClient(
                url=self._config.url,
                timeout=self._sdk_timeout(),
                prefer_grpc=False,
                check_compatibility=False,
            )
        return self._client

    def _sdk_timeout(self) -> int:
        """The client takes whole seconds; the project config keeps a float."""
        return max(1, round(self._config.timeout_seconds))

    # ---- collection profile

    def profile(self) -> TargetCollectionProfile:
        info = self._with_retries(
            lambda: self.client.get_collection(
                collection_name=self._config.collection_name
            )
        )
        vectors = info.config.params.vectors
        named = (
            vectors[self._config.vector_name] if isinstance(vectors, dict) else vectors
        )
        distance = getattr(named.distance, "value", str(named.distance))
        return TargetCollectionProfile(
            collection_name=self._config.collection_name,
            vector_name=self._config.vector_name,
            vector_size=int(named.size),
            distance=str(distance),
        )

    # ---- write

    def write_group(
        self, points: Sequence[tuple[UUID, Sequence[float], dict[str, Any]]]
    ) -> None:
        structs = [
            rest.PointStruct(
                id=point_id,
                vector={self._config.vector_name: list(vector)},
                payload=payload,
            )
            for point_id, vector, payload in points
        ]
        self._with_retries(
            lambda: self.client.upsert(
                collection_name=self._config.collection_name,
                points=structs,
                wait=True,
                timeout=self._sdk_timeout(),
            )
        )

    # ---- read

    def read(
        self, ids: Sequence[UUID]
    ) -> dict[UUID, tuple[dict[str, Any], list[float]]]:
        records = self._with_retries(
            lambda: self.client.retrieve(
                collection_name=self._config.collection_name,
                ids=list(ids),
                with_payload=True,
                with_vectors=True,
            )
        )
        found: dict[UUID, tuple[dict[str, Any], list[float]]] = {}
        for record in records:
            vector = record.vector
            if isinstance(vector, dict):
                vector = vector.get(self._config.vector_name, [])
            found[_as_uuid(record.id)] = (
                dict(record.payload or {}),
                list(vector or []),
            )
        return found

    # ---- search (semantic / unranked lexical / phrase / native BM25)

    def search(
        self, query: SearchQuery, search_filter: SearchFilter
    ) -> tuple[SearchHit, ...]:
        """Execute one search. All four modes share the same authorized filter."""
        engine_filter = _to_engine_filter(search_filter)
        if query.mode is None:  # semantic
            response = self._with_retries(
                lambda: self.client.query_points(
                    collection_name=self._config.collection_name,
                    query=list(query.vector or []),
                    using=self._config.vector_name,
                    query_filter=engine_filter,
                    limit=query.limit,
                    with_payload=True,
                )
            )
            return tuple(_hit_from_point(point) for point in _response_points(response))

        if query.mode is SearchMode.FILTER:
            # Verified 2026-11-03: scroll + MatchText matches without producing any score.
            text_only = rest.Filter(
                must=[
                    *_engine_filter_clauses(search_filter),
                    rest.FieldCondition(
                        key=TEXT_FIELD, match=rest.MatchText(text=query.text or "")
                    ),
                ]
            )
            records, _offset = self._with_retries(
                lambda: self.client.scroll(
                    collection_name=self._config.collection_name,
                    scroll_filter=text_only,
                    limit=query.limit,
                    with_payload=True,
                    with_vectors=False,
                )
            )
            return tuple(_hit_from_record(record) for record in records)

        if query.mode is SearchMode.BM25:
            response = self._with_retries(
                lambda: self.client.query_points(
                    collection_name=self._config.collection_name,
                    query=rest.TextQuery(text=query.text or ""),
                    using=TEXT_FIELD,
                    query_filter=engine_filter,
                    limit=query.limit,
                    with_payload=True,
                )
            )
            return tuple(_hit_from_point(point) for point in _response_points(response))

        return self._phrase_search(query, search_filter)

    def _phrase_search(
        self, query: SearchQuery, search_filter: SearchFilter
    ) -> tuple[SearchHit, ...]:
        """Phrase search: the client has no `MatchPhrase` model, so the condition is sent as REST.

        Confined to this adapter; uses the configured URL/timeout and the same error taxonomy.
        """
        phrase = query.text or ""
        body = {
            "query": {"text": phrase},
            "using": TEXT_FIELD,
            "limit": query.limit,
            "with_payload": True,
            "filter": {
                "must": [
                    *_rest_filter_clauses(search_filter),
                    {"key": TEXT_FIELD, "match": {"phrase": phrase}},
                ]
            },
        }
        payload = self._post_json(
            f"/collections/{self._config.collection_name}/points/query", body
        )
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("points"), list):
            raise AdapterPermanentError(
                "phrase search returned an unexpected response shape"
            )
        points = result["points"]
        if not all(isinstance(point, dict) for point in points):
            raise AdapterPermanentError("phrase search returned a malformed point")
        # The response is produced by a scored text query constrained by a phrase predicate.
        # Qdrant does not document that number as a phrase-relevance score, so exposing it would
        # invite callers to treat it as BM25. Phrase search is therefore an unranked match.
        return tuple(
            _hit_from_payload(point.get("id"), point.get("payload") or {}, None)
            for point in points
        )

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = self._config.url.rstrip("/") + path
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._config.timeout_seconds
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise AdapterPermanentError(
                        "phrase search returned a non-object response"
                    )
                return payload
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code in RETRYABLE_STATUSES:
                raise AdapterTransientError(
                    f"phrase search rejected ({exc.code}): {detail}"
                ) from exc
            raise AdapterPermanentError(
                f"phrase search rejected ({exc.code}): {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AdapterUnavailableError(
                f"phrase search could not reach the target: {exc}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterPermanentError(
                "phrase search returned malformed JSON"
            ) from exc

    # ---- retry policy: fixed small bound, no server-directed delay

    def _with_retries(self, call: Callable[[], Any]) -> Any:
        attempt = 0
        while True:
            try:
                return call()
            except Exception as exc:
                failure = _translate(exc)
                if (
                    isinstance(failure, AdapterTransientError)
                    and attempt < self._config.max_retries
                ):
                    attempt += 1
                    if self._config.retry_backoff_seconds:
                        self._config.sleep(self._config.retry_backoff_seconds)
                    continue
                raise failure from exc


# ---- search helpers (module level)


def _response_points(response: Any) -> Sequence[Any]:
    points = getattr(response, "points", None)
    if not isinstance(points, (list, tuple)):
        raise AdapterPermanentError("search returned an unexpected response shape")
    return points


def _engine_filter_clauses(search_filter: SearchFilter) -> list[rest.Condition]:
    """Tenant and principals are mandatory; source and generation narrow the scope."""
    clauses: list[rest.Condition] = [
        rest.FieldCondition(
            key=PayloadField.TENANT_ID,
            match=rest.MatchValue(value=search_filter.tenant_id),
        ),
        rest.FieldCondition(
            key=PayloadField.ACL_PRINCIPALS,
            match=rest.MatchAny(any=list(search_filter.principals)),
        ),
    ]
    if search_filter.source_ids is not None:
        clauses.append(
            rest.FieldCondition(
                key=PayloadField.SOURCE_ID,
                match=rest.MatchAny(any=list(search_filter.source_ids)),
            )
        )
    if search_filter.generation_ids is not None:
        clauses.append(
            rest.FieldCondition(
                key=PayloadField.GENERATION_ID,
                match=rest.MatchAny(any=list(search_filter.generation_ids)),
            )
        )
    return clauses


def _to_engine_filter(search_filter: SearchFilter) -> rest.Filter:
    return rest.Filter(must=_engine_filter_clauses(search_filter))


def _rest_filter_clauses(search_filter: SearchFilter) -> list[dict[str, Any]]:
    """Same filter as plain JSON, for the REST phrase path."""
    clauses: list[dict[str, Any]] = [
        {"key": PayloadField.TENANT_ID, "match": {"value": search_filter.tenant_id}},
        {
            "key": PayloadField.ACL_PRINCIPALS,
            "match": {"any": list(search_filter.principals)},
        },
    ]
    if search_filter.source_ids is not None:
        clauses.append(
            {
                "key": PayloadField.SOURCE_ID,
                "match": {"any": list(search_filter.source_ids)},
            }
        )
    if search_filter.generation_ids is not None:
        clauses.append(
            {
                "key": PayloadField.GENERATION_ID,
                "match": {"any": list(search_filter.generation_ids)},
            }
        )
    return clauses


def _hit_from_payload(
    point_id: Any, payload: dict[str, Any], score: float | None
) -> SearchHit:
    return SearchHit(
        point_id=_as_uuid(point_id),
        chunk_id=payload.get(PayloadField.CHUNK_ID),
        text=payload.get(PayloadField.TEXT),
        source_id=payload.get(PayloadField.SOURCE_ID),
        version=payload.get(PayloadField.VERSION),
        generation_id=payload.get(PayloadField.GENERATION_ID),
        knowledge_space_id=payload.get(PayloadField.KNOWLEDGE_SPACE_ID),
        source_type=payload.get(PayloadField.SOURCE_TYPE),
        kind=payload.get(PayloadField.KIND),
        location=payload.get(PayloadField.LOCATION),
        score=float(score) if score is not None else None,
    )


def _hit_from_point(point: Any) -> SearchHit:
    return _hit_from_payload(point.id, dict(point.payload or {}), point.score)


def _hit_from_record(record: Any) -> SearchHit:
    """Unranked full-text matches carry no score by construction."""
    return _hit_from_payload(record.id, dict(record.payload or {}), None)
