"""S-02 service: reconciliation, validation, raising semantics and empty request."""

import uuid

import pytest

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest, IndexingResult
from packages.storage.exceptions import (
    ChunkValidationError,
    CollectionMismatchError,
    ReadBackMismatchError,
    StoreTimeoutError,
    StoreWriteError,
)
from packages.storage import service
from packages.storage.qdrant import adapter as adapter_module
from packages.storage.qdrant.config import Distance, StorageConfig

SOURCE = SourceVersion(
    source=SourceRef(source_id="doc-101", knowledge_space_id="ks-1", source_type="document"),
    version="v2",
)


def a_chunk(chunk_id: str, text: str = "متن فارسی English text") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source=SOURCE,
        kind="document",
        text=text,
        access=AccessMetadata(tenant_id="t1", acl_principals=["g:readers"]),
        location=SourceLocation(page=1),
    )


def an_embedding(chunk_id: str, model_id: str = "m-1", size: int = 4) -> EmbeddingRecord:
    return EmbeddingRecord(chunk_id=chunk_id, model_id=model_id, vector=[0.1] * size)


def a_request(chunk_ids=("c1", "c2"), **kwargs) -> IndexingRequest:
    return IndexingRequest(
        source=SOURCE,
        generation_id=kwargs.pop("generation_id", "gen-1"),
        chunks=kwargs.pop("chunks", [a_chunk(cid) for cid in chunk_ids]),
        embeddings=kwargs.pop("embeddings", [an_embedding(cid) for cid in chunk_ids]),
    )


class FakeAdapter:
    """Duck-typed stand-in for the Qdrant adapter (no SDK involvement).

    The stored points live on the class so they survive the per-call adapter construction, i.e. they
    behave like a real backend across multiple `store_chunks` / `read_chunks` calls.
    """

    instances: list["FakeAdapter"] = []
    backend: dict = {}
    profile_size = 4
    profile_distance = "Cosine"
    write_failure: Exception | None = None
    read_failure: Exception | None = None
    profile_failure: Exception | None = None
    drop_ids: set = set()

    def __init__(self, config):
        self.config = config
        self.groups: list[list] = []
        FakeAdapter.instances.append(self)

    @property
    def written(self) -> dict:
        return FakeAdapter.backend

    def profile(self):
        if FakeAdapter.profile_failure is not None:
            raise FakeAdapter.profile_failure
        return adapter_module.TargetCollectionProfile(
            collection_name=self.config.collection_name,
            vector_name=self.config.vector_name,
            vector_size=self.profile_size,
            distance=self.profile_distance,
        )

    def write_group(self, points):
        if FakeAdapter.write_failure is not None:
            raise FakeAdapter.write_failure
        self.groups.append(list(points))
        for point_id, vector, payload in points:
            # setdefault keeps a deliberately tampered record tampered
            FakeAdapter.backend.setdefault(point_id, (payload, vector))

    def read(self, ids):
        if FakeAdapter.read_failure is not None:
            raise FakeAdapter.read_failure
        return {
            point_id: FakeAdapter.backend[point_id]
            for point_id in ids
            if point_id in FakeAdapter.backend and point_id not in FakeAdapter.drop_ids
        }


@pytest.fixture
def fake_adapter(monkeypatch):
    FakeAdapter.instances = []
    FakeAdapter.backend = {}
    FakeAdapter.write_failure = None
    FakeAdapter.read_failure = None
    FakeAdapter.profile_failure = None
    FakeAdapter.drop_ids = set()
    FakeAdapter.profile_size = 4
    FakeAdapter.profile_distance = "Cosine"
    monkeypatch.setattr(service, "QdrantAdapter", FakeAdapter)
    return FakeAdapter


CONFIG = StorageConfig()


def failure_detail(excinfo) -> object:
    assert excinfo.value.result is not None
    return excinfo.value.result


# ---- success paths


def test_full_success_returns_indexing_result_and_needs_no_failure_detail(fake_adapter):
    result = service.store_chunks(a_request(), config=CONFIG)
    assert isinstance(result, IndexingResult)
    assert result.generation_id == "gen-1"
    assert result.indexed_count == 2
    assert result.validated is True


def test_empty_request_is_a_zero_count_success_and_never_touches_the_target(fake_adapter):
    result = service.store_chunks(
        IndexingRequest(source=SOURCE, generation_id="gen-1", chunks=[], embeddings=[]),
        config=CONFIG,
    )
    assert result.indexed_count == 0
    assert result.validated is True
    assert fake_adapter.instances == [], "the target must not be contacted for an empty request"


def test_write_groups_default_to_64(monkeypatch):
    from packages.storage import service as service_module

    FakeAdapter.instances = []
    FakeAdapter.write_failure = None
    FakeAdapter.read_failure = None
    FakeAdapter.drop_ids = set()
    monkeypatch.setattr(service_module, "QdrantAdapter", FakeAdapter)

    request = a_request(chunk_ids=tuple(f"c{i}" for i in range(130)))
    result = service.store_chunks(request, config=CONFIG)
    assert result.indexed_count == 130
    sizes = [len(group) for group in FakeAdapter.instances[0].groups]
    assert sizes == [64, 64, 2]


# ---- validation before any write


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda c, e: (c, e[:-1]), id="missing-embedding"),
        pytest.param(lambda c, e: (c, e + [an_embedding("extra")]), id="extra-embedding"),
        pytest.param(lambda c, e: (c, e + [e[0]]), id="duplicate-embedding-chunk-id"),
        pytest.param(lambda c, e: (c + [a_chunk("c1", "duplicate chunk")], e), id="duplicate-chunk-id"),
        pytest.param(lambda c, e: (c, [e[0], an_embedding("c2", model_id="m-2")]), id="mixed-model-id"),
        pytest.param(lambda c, e: (c, [e[0], an_embedding("c2", size=8)]), id="mixed-dimension"),
    ],
)
def test_reconciliation_failures_raise_validation_with_attached_detail(fake_adapter, mutate):
    chunks, embeddings = mutate([a_chunk("c1"), a_chunk("c2")], [an_embedding("c1"), an_embedding("c2")])
    request = a_request(chunks=chunks, embeddings=embeddings)

    with pytest.raises(ChunkValidationError) as excinfo:
        service.store_chunks(request, config=CONFIG)

    detail = failure_detail(excinfo)
    assert detail.requested == detail.failed, "requested must equal stored + failed"
    assert detail.stored == 0
    assert detail.requested >= len(chunks)
    assert fake_adapter.instances == [] or fake_adapter.instances[0].written == {}


def test_single_dimension_that_mismatches_the_config_is_a_collection_mismatch(fake_adapter):
    request = a_request(
        embeddings=[an_embedding("c1", size=1), an_embedding("c2", size=1)]
    )

    with pytest.raises(CollectionMismatchError) as excinfo:
        service.store_chunks(request, config=CONFIG)

    detail = failure_detail(excinfo)
    assert (detail.requested, detail.stored, detail.failed) == (2, 0, 2)


def test_collection_profile_mismatch_writes_nothing(fake_adapter):
    fake_adapter.profile_size = 8

    with pytest.raises(CollectionMismatchError) as excinfo:
        service.store_chunks(a_request(), config=CONFIG)

    detail = failure_detail(excinfo)
    assert (detail.requested, detail.stored, detail.failed) == (2, 0, 2)
    assert fake_adapter.instances[0].written == {}


def test_collection_distance_mismatch_writes_nothing(fake_adapter):
    fake_adapter.profile_distance = "Dot"

    with pytest.raises(CollectionMismatchError):
        service.store_chunks(a_request(), config=CONFIG)
    assert fake_adapter.instances[0].written == {}


# ---- honest failure outcomes


def test_a_write_failure_marks_the_group_and_the_unattempted_points(fake_adapter):
    fake_adapter.write_failure = adapter_module.AdapterPermanentError("upsert rejected")
    small_batches = StorageConfig(batch_size=1, sleep=lambda _s: None)

    with pytest.raises(StoreWriteError) as excinfo:
        service.store_chunks(a_request(), config=small_batches)

    detail = failure_detail(excinfo)
    assert detail.requested == 2
    assert detail.stored == 0
    assert detail.failed == 2
    categories = sorted(failure.category.value for failure in detail.failures)
    assert categories == ["unattempted", "write"]  # first group failed, second never attempted


def test_a_later_batch_failure_counts_the_acknowledged_batches(fake_adapter):
    """Regression (B1): a mid-batch failure used to break requested == stored + failed."""
    request = a_request(chunk_ids=("c1", "c2", "c3"))
    small_batches = StorageConfig(batch_size=1, sleep=lambda _s: None)

    calls = {"n": 0}
    real_write = fake_adapter.write_group

    def write_group(self, points):
        calls["n"] += 1
        if calls["n"] == 2:  # second batch fails, first was acknowledged
            raise adapter_module.AdapterPermanentError("upsert rejected on batch 2")
        return real_write(self, points)

    fake_adapter.write_group = write_group

    with pytest.raises(StoreWriteError) as excinfo:
        service.store_chunks(request, config=small_batches)

    detail = failure_detail(excinfo)
    assert detail.requested == 3
    assert detail.stored == 1, "the acknowledged first batch must be counted"
    assert detail.failed == 2
    assert detail.requested == detail.stored + detail.failed
    assert detail.failed == len(detail.failures)
    categories = sorted(failure.category.value for failure in detail.failures)
    assert categories == ["unattempted", "write"]


def test_a_later_batch_timeout_also_counts_the_acknowledged_batches(fake_adapter):
    request = a_request(chunk_ids=("c1", "c2", "c3"))
    small_batches = StorageConfig(batch_size=1, sleep=lambda _s: None)

    calls = {"n": 0}
    real_write = fake_adapter.write_group

    def write_group(self, points):
        calls["n"] += 1
        if calls["n"] == 3:
            raise adapter_module.AdapterUnavailableError("connection refused on batch 3")
        return real_write(self, points)

    fake_adapter.write_group = write_group

    with pytest.raises(StoreTimeoutError) as excinfo:
        service.store_chunks(request, config=small_batches)

    detail = failure_detail(excinfo)
    assert (detail.requested, detail.stored, detail.failed) == (3, 2, 1)
    assert detail.requested == detail.stored + detail.failed


def test_unavailable_target_raises_timeout_with_attached_detail(fake_adapter):
    fake_adapter.write_failure = adapter_module.AdapterUnavailableError("connection refused")

    with pytest.raises(StoreTimeoutError) as excinfo:
        service.store_chunks(a_request(), config=CONFIG)

    detail = failure_detail(excinfo)
    assert detail.stored == 0
    assert detail.failed == 2
    assert detail.failed > 0, "a raised error always carries at least one failure"


# ---- empty / asymmetric request shapes (B2)


def test_embeddings_without_any_chunk_name_the_orphan_embedding(fake_adapter):
    request = a_request(chunks=[], embeddings=[an_embedding("orphan-1")])

    with pytest.raises(ChunkValidationError) as excinfo:
        service.store_chunks(request, config=CONFIG)

    detail = failure_detail(excinfo)
    assert (detail.requested, detail.stored, detail.failed) == (1, 0, 1)
    assert detail.requested == detail.stored + detail.failed
    assert [failure.chunk_id for failure in detail.failures] == ["orphan-1"]
    assert "no matching chunk" in detail.failures[0].reason
    assert fake_adapter.instances == [], "no target work may happen for an invalid request"


def test_chunks_without_any_embedding_name_the_orphan_chunk(fake_adapter):
    request = a_request(chunks=[a_chunk("c9")], embeddings=[])

    with pytest.raises(ChunkValidationError) as excinfo:
        service.store_chunks(request, config=CONFIG)

    detail = failure_detail(excinfo)
    assert (detail.requested, detail.stored, detail.failed) == (1, 0, 1)
    assert detail.requested == detail.stored + detail.failed
    assert [failure.chunk_id for failure in detail.failures] == ["c9"]
    assert fake_adapter.instances == []


def test_an_extra_embedding_is_reported_in_addition_to_the_chunks(fake_adapter):
    request = a_request(embeddings=[an_embedding("c1"), an_embedding("c2"), an_embedding("c3")])

    with pytest.raises(ChunkValidationError) as excinfo:
        service.store_chunks(request, config=CONFIG)

    detail = failure_detail(excinfo)
    assert (detail.requested, detail.stored, detail.failed) == (3, 0, 3)
    assert detail.requested == detail.stored + detail.failed
    assert "c3" in [failure.chunk_id for failure in detail.failures]
    assert fake_adapter.instances == []


# ---- read operations must not raise write-flavoured errors (B3)


def test_read_chunks_permanent_failure_raises_read_back_error_not_write_error(fake_adapter):
    fake_adapter.read_failure = adapter_module.AdapterPermanentError("malformed response")

    with pytest.raises(ReadBackMismatchError):
        service.read_chunks([uuid.uuid4()], config=CONFIG)


def test_store_read_back_permanent_failure_raises_read_back_error_not_write_error(fake_adapter):
    fake_adapter.read_failure = adapter_module.AdapterPermanentError("malformed response")

    with pytest.raises(ReadBackMismatchError) as excinfo:
        service.store_chunks(a_request(chunk_ids=("c1",)), config=CONFIG)

    detail = failure_detail(excinfo)
    assert detail.requested == detail.stored + detail.failed


# ---- Task 1/2: operation-level retryability on the real paths


def test_validation_failure_is_not_retryable(fake_adapter):
    with pytest.raises(ChunkValidationError) as excinfo:
        service.store_chunks(a_request(embeddings=[]), config=CONFIG)

    assert excinfo.value.retryable is False
    assert all(not failure.retryable for failure in excinfo.value.result.failures)


def test_collection_mismatch_is_not_retryable(fake_adapter):
    fake_adapter.profile_size = 8

    with pytest.raises(CollectionMismatchError) as excinfo:
        service.store_chunks(a_request(), config=CONFIG)

    assert excinfo.value.retryable is False


def test_unreadable_target_profile_is_retryable(fake_adapter):
    fake_adapter.profile_failure = adapter_module.AdapterUnavailableError("connection refused")

    with pytest.raises(StoreTimeoutError) as excinfo:
        service.store_chunks(a_request(), config=CONFIG)

    assert excinfo.value.retryable is True
    assert all(failure.retryable for failure in excinfo.value.result.failures)
    assert all(failure.category.value == "timeout" for failure in excinfo.value.result.failures)


def test_transient_write_failure_is_retryable(fake_adapter):
    fake_adapter.write_failure = adapter_module.AdapterTransientError("503 after retries")

    with pytest.raises(StoreWriteError) as excinfo:
        service.store_chunks(a_request(chunk_ids=("c1",)), config=CONFIG)

    assert excinfo.value.retryable is True


def test_permanent_write_failure_is_not_retryable(fake_adapter):
    fake_adapter.write_failure = adapter_module.AdapterPermanentError("400 rejected")

    with pytest.raises(StoreWriteError) as excinfo:
        service.store_chunks(a_request(chunk_ids=("c1",)), config=CONFIG)

    assert excinfo.value.retryable is False


def test_read_chunks_unavailable_target_is_retryable(fake_adapter):
    """Task 1 / F1: a read timeout must not report retryable=False."""
    fake_adapter.read_failure = adapter_module.AdapterUnavailableError("connection refused")

    with pytest.raises(StoreTimeoutError) as excinfo:
        service.read_chunks([uuid.uuid4()], config=CONFIG)

    assert excinfo.value.retryable is True
    failures = excinfo.value.result.failures
    assert failures and all(failure.retryable for failure in failures)
    assert all(failure.category.value == "timeout" for failure in failures)


def test_read_chunks_transient_failure_is_retryable(fake_adapter):
    fake_adapter.read_failure = adapter_module.AdapterTransientError("timed out")

    with pytest.raises(StoreTimeoutError) as excinfo:
        service.read_chunks([uuid.uuid4()], config=CONFIG)

    assert excinfo.value.retryable is True


def test_read_chunks_permanent_failure_is_not_retryable(fake_adapter):
    fake_adapter.read_failure = adapter_module.AdapterPermanentError("malformed response")

    with pytest.raises(ReadBackMismatchError) as excinfo:
        service.read_chunks([uuid.uuid4()], config=CONFIG)

    assert excinfo.value.retryable is False
    assert all(not failure.retryable for failure in excinfo.value.result.failures)


def test_store_read_back_unavailable_is_retryable(fake_adapter):
    fake_adapter.read_failure = adapter_module.AdapterUnavailableError("connection refused")

    with pytest.raises(StoreTimeoutError) as excinfo:
        service.store_chunks(a_request(chunk_ids=("c1",)), config=CONFIG)

    assert excinfo.value.retryable is True
    assert excinfo.value.result.requested == excinfo.value.result.stored + excinfo.value.result.failed


def test_store_read_back_mismatch_is_not_retryable(fake_adapter):
    request = a_request(chunk_ids=("c1",))
    service.store_chunks(request, config=CONFIG)
    fake_adapter.drop_ids = {next(iter(fake_adapter.backend))}

    with pytest.raises(ReadBackMismatchError) as excinfo:
        service.store_chunks(request, config=CONFIG)

    assert excinfo.value.retryable is False
    assert all(failure.category.value == "read_back" for failure in excinfo.value.result.failures)


def test_read_back_mismatch_raises_read_back_error_with_verified_counts(fake_adapter):
    request = a_request(chunk_ids=("c1", "c2"))
    service.store_chunks(request, config=CONFIG)  # warm the fake so points exist
    fake_adapter.drop_ids = {next(iter(fake_adapter.instances[0].written))}

    with pytest.raises(ReadBackMismatchError) as excinfo:
        service.store_chunks(request, config=CONFIG)

    detail = failure_detail(excinfo)
    assert detail.requested == 2
    assert detail.stored == 1
    assert detail.failed == 1


def test_altered_payload_is_a_read_back_mismatch(fake_adapter):
    request = a_request(chunk_ids=("c1",))
    service.store_chunks(request, config=CONFIG)
    point_id = next(iter(fake_adapter.instances[0].written))
    payload, vector = fake_adapter.instances[0].written[point_id]
    fake_adapter.instances[0].written[point_id] = ({**payload, "text": "tampered"}, vector)

    with pytest.raises(ReadBackMismatchError):
        service.store_chunks(request, config=CONFIG)


def test_read_back_compares_dimension_not_values(fake_adapter):
    request = a_request(chunk_ids=("c1",))
    service.store_chunks(request, config=CONFIG)
    point_id = next(iter(fake_adapter.instances[0].written))
    payload, _ = fake_adapter.instances[0].written[point_id]
    # float32-style drift and different values, same dimension, must still verify
    fake_adapter.instances[0].written[point_id] = (payload, [0.30000001192092896, 0.1, 0.2, 0.7])

    result = service.store_chunks(request, config=CONFIG)
    assert result.indexed_count == 1


# ---- read_chunks


def test_read_chunks_returns_landed_chunk_contracts(fake_adapter):
    service.store_chunks(a_request(chunk_ids=("c1",)), config=CONFIG)
    point_id = next(iter(fake_adapter.instances[0].written))

    records = service.read_chunks([point_id], config=CONFIG)

    assert len(records) == 1
    chunk = records[0]
    assert isinstance(chunk, Chunk)
    assert chunk.chunk_id == "c1"
    assert chunk.source.source.source_id == "doc-101"
    assert chunk.access.tenant_id == "t1"


def test_read_chunks_missing_id_raises_read_back_error_with_counts(fake_adapter):
    service.store_chunks(a_request(chunk_ids=("c1",)), config=CONFIG)
    point_id = next(iter(fake_adapter.instances[0].written))
    fake_adapter.drop_ids = {point_id}

    with pytest.raises(ReadBackMismatchError) as excinfo:
        service.read_chunks([point_id, uuid.uuid4()], config=CONFIG)

    detail = failure_detail(excinfo)
    assert (detail.requested, detail.stored, detail.failed) == (2, 0, 2)


def test_storage_config_is_reexported_by_the_service_module():
    assert service.StorageConfig is StorageConfig
    assert StorageConfig().distance is Distance.COSINE
