"""I-01A indexing integration: request construction, ErrorDetail mapping, honest failure."""

import ast
import pathlib
from uuid import UUID

import pytest

from apps.document_ingestion.storage_errors import to_error_detail
from apps.document_ingestion import indexing as indexing_module
from apps.document_ingestion.indexing import IndexingFailed, index_generation
from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.errors import ErrorCode, ErrorDetail
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest, IndexingResult
from packages.contracts.storage import FailureCategory, StoreFailure, StoreResult
from packages.storage.service import (
    ChunkValidationError,
    CollectionMismatchError,
    ReadBackMismatchError,
    StorageConfig,
    StoreTimeoutError,
    StoreWriteError,
)

SOURCE = SourceVersion(
    source=SourceRef(source_id="doc-101", knowledge_space_id="ks-1", source_type="document"),
    version="v2",
)
CONFIG = StorageConfig()


def a_chunk(chunk_id: str, text: str = "متن فارسی English", source: SourceVersion = SOURCE) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source=source,
        kind="document",
        text=text,
        access=AccessMetadata(tenant_id="tenant-a", acl_principals=["g:readers", "u:1"]),
        location=SourceLocation(page=3, section="intro"),
        metadata={"lang": "fa"},
    )


def an_embedding(chunk_id: str, model_id: str = "embed-4d") -> EmbeddingRecord:
    return EmbeddingRecord(chunk_id=chunk_id, model_id=model_id, vector=[0.1, 0.2, 0.3, 0.4])


def a_failure(**overrides) -> StoreFailure:
    data = {"chunk_id": "c1", "category": FailureCategory.WRITE, "reason": "upsert rejected"}
    data.update(overrides)
    return StoreFailure(**data)


class SpyStore:
    """Stand-in for `store_chunks`: records the request, returns or raises on demand."""

    def __init__(self, *, result=None, error=None):
        self.result = result
        self.error = error
        self.calls: list[tuple] = []

    def __call__(self, request, *, config):
        self.calls.append((request, config))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def installed(monkeypatch):
    """Install a spy `store_chunks` into the indexing module."""

    def install(*, result=None, error=None) -> SpyStore:
        spy = SpyStore(result=result, error=error)
        monkeypatch.setattr(indexing_module, "store_chunks", spy)
        return spy

    return install


# ---- success path and request construction


def test_index_generation_returns_the_verified_result(installed):
    expected = IndexingResult(generation_id="gen-1", indexed_count=2, validated=True)
    spy = installed(result=expected)

    result = index_generation(
        [a_chunk("c1"), a_chunk("c2")],
        [an_embedding("c1"), an_embedding("c2")],
        source=SOURCE,
        generation_id="gen-1",
        config=CONFIG,
    )

    assert result is expected
    assert len(spy.calls) == 1


def test_request_preserves_source_version_generation_and_access_metadata(installed):
    spy = installed(result=IndexingResult(generation_id="gen-7", indexed_count=1, validated=True))

    index_generation(
        [a_chunk("c1")],
        [an_embedding("c1", model_id="m-9")],
        source=SOURCE,
        generation_id="gen-7",
        config=CONFIG,
    )

    request, config = spy.calls[0]
    assert isinstance(request, IndexingRequest)
    assert config is CONFIG
    assert request.generation_id == "gen-7"
    assert request.source == SOURCE
    assert request.source.source.source_id == "doc-101"
    assert request.source.version == "v2"
    assert request.chunks[0].chunk_id == "c1"
    assert request.chunks[0].access.tenant_id == "tenant-a"
    assert list(request.chunks[0].access.acl_principals) == ["g:readers", "u:1"]
    assert request.chunks[0].location.section == "intro"
    assert request.chunks[0].metadata == {"lang": "fa"}
    assert [embedding.model_id for embedding in request.embeddings] == ["m-9"]
    assert request.embeddings[0].vector == [0.1, 0.2, 0.3, 0.4]


def test_input_sequences_are_not_mutated_and_are_copied(installed):
    installed(result=IndexingResult(generation_id="gen-1", indexed_count=1, validated=True))
    chunks = [a_chunk("c1")]
    embeddings = [an_embedding("c1")]

    index_generation(chunks, embeddings, source=SOURCE, generation_id="gen-1", config=CONFIG)

    assert chunks == [a_chunk("c1")]
    assert embeddings == [an_embedding("c1")]


# ---- storage failure -> ErrorDetail


def _result(failed: int = 1, *, category=FailureCategory.WRITE, retryable=False) -> StoreResult:
    failures = tuple(
        a_failure(chunk_id=f"c{index}", category=category, retryable=retryable)
        for index in range(1, failed + 1)
    )
    return StoreResult(requested=failed, stored=0, failed=failed, failures=failures)


@pytest.mark.parametrize(
    "error, expected_code, expected_retryable",
    [
        (StoreWriteError("permanent write failure", result=_result()), ErrorCode.STORAGE_ERROR, False),
        (
            StoreWriteError("transient write failure", result=_result(retryable=True)),
            ErrorCode.STORAGE_ERROR,
            True,
        ),
        (
            StoreTimeoutError(
                "target unavailable",
                result=_result(category=FailureCategory.TIMEOUT, retryable=True),
            ),
            ErrorCode.STORAGE_ERROR,
            True,
        ),
        (
            ChunkValidationError(
                "chunks and embeddings do not match", result=_result(category=FailureCategory.VALIDATION)
            ),
            ErrorCode.VALIDATION_ERROR,
            False,
        ),
        (
            CollectionMismatchError(
                "vector size mismatch", result=_result(category=FailureCategory.MISMATCH)
            ),
            ErrorCode.STORAGE_ERROR,
            False,
        ),
        (
            ReadBackMismatchError(
                "read-back mismatch", result=_result(category=FailureCategory.READ_BACK)
            ),
            ErrorCode.STORAGE_ERROR,
            False,
        ),
    ],
)
def test_storage_failures_become_indexing_failed_with_error_detail(
    installed, error, expected_code, expected_retryable
):
    installed(error=error)

    with pytest.raises(IndexingFailed) as excinfo:
        index_generation(
            [a_chunk("c1")], [an_embedding("c1")], source=SOURCE, generation_id="gen-1", config=CONFIG
        )

    failed = excinfo.value
    assert isinstance(failed.detail, ErrorDetail)
    assert failed.detail.code is expected_code
    assert failed.detail.retryable is expected_retryable
    assert failed.retryable is expected_retryable
    assert failed.detail.message
    assert failed.store_result is error.result, "the full StoreResult must stay available"
    assert excinfo.value.__cause__ is error, "the original storage error must stay chained"


def test_failure_message_carries_counts_and_causes():
    error = StoreWriteError("upsert rejected", result=_result(failed=2))
    detail = to_error_detail(error)

    assert "requested=2 stored=0 failed=2" in detail.message
    assert "StoreWriteError" in detail.message
    assert "c1: upsert rejected" in detail.message


def test_failure_message_is_bounded():
    failures = tuple(
        a_failure(chunk_id=f"chunk-{index}", reason="x" * 200) for index in range(1, 51)
    )
    result = StoreResult(requested=50, stored=0, failed=50, failures=failures)

    detail = to_error_detail(StoreWriteError("huge", result=result))

    assert len(detail.message) <= 500
    assert detail.message.endswith("...")


def test_no_false_success_on_storage_failure(installed):
    installed(error=StoreWriteError("rejected", result=_result()))
    returned = None

    try:
        returned = index_generation(
            [a_chunk("c1")], [an_embedding("c1")], source=SOURCE, generation_id="gen-1", config=CONFIG
        )
    except IndexingFailed:
        pass

    assert returned is None


def test_unverified_result_is_never_reported_as_success(installed):
    installed(result=IndexingResult(generation_id="gen-1", indexed_count=1, validated=False))

    with pytest.raises(RuntimeError, match="not read-back verified"):
        index_generation(
            [a_chunk("c1")], [an_embedding("c1")], source=SOURCE, generation_id="gen-1", config=CONFIG
        )


# ---- unexpected errors are not swallowed, and the boundary stays SDK-free


def test_unexpected_errors_propagate_unchanged(installed):
    installed(error=RuntimeError("bug in the caller"))

    with pytest.raises(RuntimeError, match="bug in the caller"):
        index_generation(
            [a_chunk("c1")], [an_embedding("c1")], source=SOURCE, generation_id="gen-1", config=CONFIG
        )


def test_a_chunk_from_another_source_is_rejected_before_storage(installed):
    spy = installed(result=IndexingResult(generation_id="gen-1", indexed_count=1, validated=True))
    other = SourceVersion(
        source=SourceRef(source_id="doc-999", knowledge_space_id="ks-1", source_type="document"),
        version="v9",
    )

    with pytest.raises(ValueError, match="belongs to source"):
        index_generation(
            [a_chunk("c1", source=other)],
            [an_embedding("c1")],
            source=SOURCE,
            generation_id="gen-1",
            config=CONFIG,
        )

    assert spy.calls == []


def test_integration_boundary_has_no_qdrant_dependency():
    """No SDK and no adapter may leak into the application boundary.

    `packages.storage.qdrant.config` is allowed: `StorageConfig` is SDK-neutral and lives there by
    design; the Qdrant client and the adapter are what must stay out.
    """
    import apps.document_ingestion.storage_errors as storage_errors

    for module in (indexing_module, storage_errors):
        tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not [name for name in imported if "qdrant_client" in name], module.__name__
        assert "packages.storage.qdrant.adapter" not in imported, module.__name__


def test_store_result_is_reachable_for_diagnostics_without_contract_changes():
    point_id = UUID("12345678-1234-5678-1234-567812345678")
    result = StoreResult(
        requested=2,
        stored=0,
        failed=2,
        failures=(
            a_failure(chunk_id="c1"),
            a_failure(point_id=point_id, chunk_id=None, category=FailureCategory.READ_BACK),
        ),
    )
    error = ReadBackMismatchError("x", result=result)
    failed = IndexingFailed(to_error_detail(error), store_result=error.result)

    assert failed.store_result.failures[1].point_id == point_id
    assert failed.to_error_detail() is failed.detail
