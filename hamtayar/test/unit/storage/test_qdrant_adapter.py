"""S-02 adapter: identity, payload mapping, retry taxonomy and read-back mapping."""

import json
import uuid
from typing import ClassVar

import pytest

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord
from packages.contracts.storage import PayloadField
from packages.storage.qdrant.adapter import (
    RETRYABLE_STATUSES,
    AdapterPermanentError,
    AdapterTransientError,
    AdapterUnavailableError,
    QdrantAdapter,
    TargetCollectionProfile,
    build_payload,
    point_id_for,
)
from packages.storage.qdrant.config import Distance, StorageConfig
from packages.storage.search import SearchFilter, SearchMode, SearchQuery

SOURCE = SourceVersion(
    source=SourceRef(
        source_id="doc-101", knowledge_space_id="ks-1", source_type="document"
    ),
    version="v2",
)


def a_chunk(chunk_id: str = "c1", text: str = "متن فارسی English text") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source=SOURCE,
        kind="document",
        text=text,
        access=AccessMetadata(tenant_id="t1", acl_principals=["g:readers"]),
        location=SourceLocation(page=3, section="intro"),
        symbol_id=None,
        metadata={"lang": "fa"},
    )


def an_embedding(
    chunk_id: str = "c1", model_id: str = "m-1", size: int = 4
) -> EmbeddingRecord:
    return EmbeddingRecord(chunk_id=chunk_id, model_id=model_id, vector=[0.1] * size)


# ---- identity


def test_point_id_matches_the_json_encoded_uuid5_formula():
    expected = uuid.uuid5(
        uuid.NAMESPACE_URL, json.dumps(["doc-101", "v2", "gen-1", "c1"])
    )
    assert point_id_for("doc-101", "v2", "gen-1", "c1") == expected


def test_point_id_is_stable_and_every_input_changes_it():
    base = point_id_for("doc-101", "v2", "gen-1", "c1")
    assert point_id_for("doc-101", "v2", "gen-1", "c1") == base
    assert point_id_for("doc-102", "v2", "gen-1", "c1") != base
    assert point_id_for("doc-101", "v3", "gen-1", "c1") != base
    assert point_id_for("doc-101", "v2", "gen-2", "c1") != base
    assert point_id_for("doc-101", "v2", "gen-1", "c2") != base


def test_separator_inside_a_component_cannot_alias_two_identities():
    # Naive "a:b" + "c" vs "a" + "b:c" would collide if the components were joined.
    left = point_id_for("a:b", "v", "g", "c")
    right = point_id_for("a", "v", "g", "b:c")
    assert left != right


def test_phrase_search_discards_undocumented_engine_score(monkeypatch):
    adapter = QdrantAdapter(StorageConfig(), client=object())
    point_id = str(uuid.uuid4())
    payload = {
        PayloadField.CHUNK_ID: "c1",
        PayloadField.TEXT: "semantic search",
        PayloadField.SOURCE_ID: "doc-1",
        PayloadField.VERSION: "v1",
        PayloadField.GENERATION_ID: "gen-1",
        PayloadField.KNOWLEDGE_SPACE_ID: "ks-1",
        PayloadField.SOURCE_TYPE: "document",
        PayloadField.KIND: "document",
    }
    monkeypatch.setattr(
        adapter,
        "_post_json",
        lambda path, body: {
            "result": {"points": [{"id": point_id, "payload": payload, "score": 9.5}]}
        },
    )

    hits = adapter.search(
        SearchQuery(mode=SearchMode.PHRASE, limit=5, text="semantic search"),
        SearchFilter(tenant_id="tenant-A", principals=("reader",)),
    )

    assert hits[0].score is None


def test_phrase_search_rejects_unexpected_response_shape(monkeypatch):
    adapter = QdrantAdapter(StorageConfig(), client=object())
    monkeypatch.setattr(adapter, "_post_json", lambda path, body: {"result": {}})

    with pytest.raises(AdapterPermanentError, match="unexpected response shape"):
        adapter.search(
            SearchQuery(mode=SearchMode.PHRASE, limit=5, text="semantic search"),
            SearchFilter(tenant_id="tenant-A", principals=("reader",)),
        )


# ---- payload mapping


def test_payload_uses_exactly_the_shared_field_definition():
    payload = build_payload(a_chunk(), an_embedding(), "gen-1")
    assert tuple(sorted(payload)) == tuple(sorted(PayloadField.ALL))


def test_payload_values_are_copied_from_the_landed_contracts():
    chunk = a_chunk()
    embedding = an_embedding()
    payload = build_payload(chunk, embedding, "gen-1")

    assert payload["chunk_id"] == "c1"
    assert payload["generation_id"] == "gen-1"
    assert payload["model_id"] == "m-1"
    assert payload["source_id"] == "doc-101"
    assert payload["version"] == "v2"
    assert payload["knowledge_space_id"] == "ks-1"
    assert payload["source_type"] == "document"
    assert payload["kind"] == "document"
    assert payload["text"] == chunk.text
    assert payload["location"] == {
        "page": 3,
        "section": "intro",
        "sheet": None,
        "cell_range": None,
        "file_path": None,
        "start_line": None,
        "end_line": None,
    }
    assert payload["tenant_id"] == "t1"
    assert payload["acl_principals"] == ["g:readers"]
    assert payload["symbol_id"] is None
    assert payload["metadata"] == {"lang": "fa"}


def test_payload_carries_no_provisional_or_publication_keys():
    payload = build_payload(a_chunk(), an_embedding(), "gen-1")
    for forbidden in ("access_scope", "published_generation", "point_id", "vector"):
        assert forbidden not in payload


# ---- retry taxonomy (fake client, no SDK import in the test)


class FakeResponseError(Exception):
    def __init__(self, status_code: int, retry_after: str | None = None):
        super().__init__(f"status {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after
        self.headers = {"retry-after": retry_after} if retry_after else {}


class FakeTimeoutError(Exception):
    pass


class FakeClient:
    def __init__(self, failures=(), records=None):
        self.failures = list(failures)
        self.calls = 0
        self.records = records or {}
        self.upserted = []
        self.requested_ids = None
        self.vector_names = []

    def upsert(self, collection_name, points, wait=True, timeout=None):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        self.upserted.extend(points)

    def retrieve(self, collection_name, ids, with_payload=True, with_vectors=False):
        self.requested_ids = list(ids)
        return [self.records[i] for i in ids if i in self.records]

    def get_collection(self, collection_name):
        class _Vectors:
            size = 4

            class distance:
                value = "Cosine"

        class _Params:
            vectors: ClassVar = {"dense": _Vectors()}

        class _Config:
            params = _Params()

        class _Info:
            config = _Config()

        return _Info()


def an_adapter(client, **config_kwargs) -> QdrantAdapter:
    # real retries must not sleep in unit tests
    config_kwargs.setdefault("sleep", lambda _seconds: None)
    return QdrantAdapter(StorageConfig(**config_kwargs), client=client)


def test_retryable_statuses_are_the_documented_set():
    assert RETRYABLE_STATUSES == frozenset({408, 429, 500, 502, 503, 504})


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_statuses_are_retried_up_to_the_bound_then_raise_transient(status):
    client = FakeClient(failures=[FakeResponseError(status) for _ in range(3)])
    adapter = an_adapter(client, max_retries=2)
    with pytest.raises(AdapterTransientError):
        adapter.write_group([(uuid.uuid4(), [0.1, 0.2, 0.3, 0.4], {"chunk_id": "c1"})])
    assert client.calls == 3  # one attempt + max_retries


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_statuses_are_not_retried(status):
    client = FakeClient(failures=[FakeResponseError(status)])
    adapter = an_adapter(client, max_retries=2)
    with pytest.raises(AdapterPermanentError):
        adapter.write_group([(uuid.uuid4(), [0.1, 0.2, 0.3, 0.4], {"chunk_id": "c1"})])
    assert client.calls == 1


def test_transport_failures_are_transient_and_unavailable_is_distinct():
    client = FakeClient(failures=[FakeTimeoutError("timed out")] * 3)
    adapter = an_adapter(client, max_retries=2)
    with pytest.raises(AdapterTransientError):
        adapter.write_group([(uuid.uuid4(), [0.1, 0.2, 0.3, 0.4], {"chunk_id": "c1"})])

    client = FakeClient(failures=[ConnectionError("refused")])
    adapter = an_adapter(client, max_retries=0)
    with pytest.raises(AdapterUnavailableError):
        adapter.write_group([(uuid.uuid4(), [0.1, 0.2, 0.3, 0.4], {"chunk_id": "c1"})])


def test_retry_after_header_is_never_used_to_schedule_a_delay():
    sleeps: list[float] = []
    client = FakeClient(
        failures=[
            FakeResponseError(429, retry_after="7"),
            FakeResponseError(429, retry_after="7"),
        ]
    )
    adapter = QdrantAdapter(
        StorageConfig(max_retries=2, retry_backoff_seconds=0.5, sleep=sleeps.append),
        client=client,
    )
    adapter.write_group([(uuid.uuid4(), [0.1, 0.2, 0.3, 0.4], {"chunk_id": "c1"})])

    assert sleeps == [0.5, 0.5], "only the fixed local backoff, one per retry"
    assert 7 not in sleeps, "the server's Retry-After must never be used"
    assert client.calls == 3


def test_retry_backoff_is_configurable_and_defaults_to_half_a_second():
    assert StorageConfig().retry_backoff_seconds == 0.5
    sleeps: list[float] = []
    client = FakeClient(failures=[FakeResponseError(503)])
    adapter = QdrantAdapter(
        StorageConfig(max_retries=1, retry_backoff_seconds=0.05, sleep=sleeps.append),
        client=client,
    )
    adapter.write_group([(uuid.uuid4(), [0.1, 0.2, 0.3, 0.4], {"chunk_id": "c1"})])
    assert sleeps == [0.05]


# ---- profile and read-back mapping


def test_profile_is_read_from_the_target_collection():
    adapter = an_adapter(FakeClient())
    profile = adapter.profile()
    assert isinstance(profile, TargetCollectionProfile)
    assert profile.collection_name == "hamtayar_test_chunks"
    assert profile.vector_name == "dense"
    assert profile.vector_size == 4
    assert profile.distance == "Cosine"


def test_distance_enum_is_mapped_to_the_sdk_inside_the_adapter_only():
    from packages.storage.qdrant import adapter as adapter_module

    assert adapter_module._DISTANCE_TO_SDK[Distance.COSINE] == "Cosine"
    assert adapter_module._DISTANCE_TO_SDK[Distance.DOT] == "Dot"
    # the config stays SDK-free
    assert isinstance(StorageConfig().distance, Distance)


def test_read_returns_payload_and_vector_keyed_by_point_id():
    point_id = uuid.uuid4()

    class _Record:
        def __init__(self):
            self.id = point_id
            self.payload = {"chunk_id": "c1"}
            self.vector = {"dense": [0.1, 0.2, 0.3, 0.4]}

    adapter = an_adapter(FakeClient(records={point_id: _Record()}))
    found = adapter.read([point_id])
    assert set(found) == {point_id}
    payload, vector = found[point_id]
    assert payload["chunk_id"] == "c1"
    assert len(vector) == 4  # dimension only, never float equality
