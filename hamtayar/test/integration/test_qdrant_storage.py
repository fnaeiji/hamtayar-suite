"""S-02 integration: real local Qdrant, synthetic Persian/English data.

Never asserts success while the service is unreachable: the fixtures skip with a reason instead.
"""

import pytest

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest, IndexingResult
from packages.storage.exceptions import CollectionMismatchError, StoreTimeoutError
from packages.storage.qdrant.adapter import point_id_for
from packages.storage.qdrant.config import StorageConfig
from packages.storage.service import read_chunks, store_chunks

SOURCES = (
    ("مدرک-۱۰۱", "ks-1", "v1"),
    ("doc-202-en", "ks-1", "v2"),
    ("مدرک-۳۰۳", "ks-2", "v1"),
)

TEXTS = (
    "متن فارسی برای آزمون ذخیره‌سازی و بازخوانی داده.",
    "English text for the storage round-trip test.",
    "متن مختلط Mixed فارسی and English 123.",
)


def a_chunk(chunk_id: str, source_id: str, version: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source=SourceVersion(
            source=SourceRef(source_id=source_id, knowledge_space_id="ks-1", source_type="document"),
            version=version,
        ),
        kind="document",
        text=text,
        access=AccessMetadata(tenant_id="tenant-a", acl_principals=["g:readers", "u:1"]),
        location=SourceLocation(page=2, section="بخش اول"),
    )


def an_embedding(chunk_id: str, size: int = 4, model_id: str = "synthetic-embed-4d") -> EmbeddingRecord:
    return EmbeddingRecord(chunk_id=chunk_id, model_id=model_id, vector=[0.11, 0.22, 0.33, 0.44][:size])


def a_request(count: int, generation_id: str = "gen-0001") -> IndexingRequest:
    chunks, embeddings = [], []
    for index in range(count):
        source_id, _, version = SOURCES[index % len(SOURCES)]
        chunk_id = f"chunk-{index:03d}"
        chunks.append(a_chunk(chunk_id, source_id, version, TEXTS[index % len(TEXTS)]))
        embeddings.append(an_embedding(chunk_id))
    return IndexingRequest(
        source=chunks[0].source, generation_id=generation_id, chunks=chunks, embeddings=embeddings
    )


def test_store_and_read_back_mixed_language_chunks(config, point_count):
    request = a_request(6)

    result = store_chunks(request, config=config)

    assert isinstance(result, IndexingResult)
    assert result.indexed_count == 6
    assert result.validated is True
    assert point_count(config.collection_name) == 6

    ids = [
        point_id_for(
            chunk.source.source.source_id, chunk.source.version, request.generation_id, chunk.chunk_id
        )
        for chunk in request.chunks
    ]
    records = read_chunks(ids, config=config)
    assert {record.chunk_id for record in records} == {chunk.chunk_id for chunk in request.chunks}
    persian = [record for record in records if "فارسی" in record.text]
    assert persian, "Persian text must round-trip intact"
    assert persian[0].location is not None and persian[0].location.section == "بخش اول"


def test_identical_resubmission_keeps_ids_and_count(config, point_count):
    request = a_request(5)

    first = store_chunks(request, config=config)
    second = store_chunks(request, config=config)

    assert (first.indexed_count, second.indexed_count) == (5, 5)
    assert point_count(config.collection_name) == 5


def test_a_new_generation_creates_distinct_points(config, point_count):
    store_chunks(a_request(3, generation_id="gen-A"), config=config)
    store_chunks(a_request(3, generation_id="gen-B"), config=config)

    assert point_count(config.collection_name) == 6


def test_request_larger_than_one_write_group_is_fully_stored(config, point_count):
    request = a_request(130)

    result = store_chunks(request, config=config)

    assert result.indexed_count == 130
    assert result.validated is True
    assert point_count(config.collection_name) == 130


def test_empty_request_returns_zero_count_success(config, point_count):
    empty = IndexingRequest(
        source=SourceVersion(
            source=SourceRef(source_id="doc-101", knowledge_space_id="ks-1", source_type="document"),
            version="v1",
        ),
        generation_id="gen-empty",
        chunks=[],
        embeddings=[],
    )

    result = store_chunks(empty, config=config)

    assert (result.indexed_count, result.validated) == (0, True)
    assert point_count(config.collection_name) == 0


def test_unreachable_target_raises_timeout_with_attached_detail(qdrant_url):
    unreachable = StorageConfig(
        url="http://127.0.0.1:6399",  # nothing listens here
        collection_name="does_not_exist",
        max_retries=0,
        timeout_seconds=1,
    )

    with pytest.raises(StoreTimeoutError) as excinfo:
        store_chunks(a_request(1), config=unreachable)

    assert excinfo.value.result is not None
    assert excinfo.value.result.failed > 0, "a raised error always carries failure detail"


def test_wrong_dimension_fails_before_any_write(config, point_count):
    request = a_request(2)
    wrong = IndexingRequest(
        source=request.source,
        generation_id=request.generation_id,
        chunks=request.chunks,
        embeddings=[
            EmbeddingRecord(chunk_id=chunk.chunk_id, model_id="m", vector=[0.5, 0.5])
            for chunk in request.chunks
        ],
    )

    with pytest.raises(CollectionMismatchError):
        store_chunks(wrong, config=config)

    assert point_count(config.collection_name) == 0
