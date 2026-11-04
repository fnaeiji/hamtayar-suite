
import pytest
from pydantic import ValidationError

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.indexing import (
    EmbeddingRecord,
    IndexingRequest,
    IndexingResult,
    PublicationRequest,
    PublicationResult,
)


@pytest.fixture
def source_version():
    """Create a valid source version."""

    return SourceVersion(
        source=SourceRef(
            source_id="doc-101",
            knowledge_space_id="engineering",
            source_type="document",
        ),
        version="v1",
    )


@pytest.fixture
def valid_chunk(source_version):
    """Create a valid chunk with access metadata."""

    return Chunk(
        chunk_id="chunk-101",
        source=source_version,
        kind="document",
        text="Hamtayar is an enterprise RAG system.",
        access=AccessMetadata(
            tenant_id="company-1",
            acl_principals=["team-hamtayar"],
        ),
    )


@pytest.fixture
def valid_embedding():
    """Create a valid embedding record."""

    return EmbeddingRecord(
        chunk_id="chunk-101",
        model_id="embedding-model-v1",
        vector=[0.1, 0.2, 0.3],
    )


@pytest.fixture
def valid_request(source_version, valid_chunk, valid_embedding):
    """Create a valid indexing request."""

    return IndexingRequest(
        source=source_version,
        generation_id="gen-001",
        chunks=[valid_chunk],
        embeddings=[valid_embedding],
    )


# EmbeddingRecord tests

def test_embedding_record_valid(valid_embedding):
    assert valid_embedding.chunk_id == "chunk-101"
    assert valid_embedding.model_id == "embedding-model-v1"
    assert len(valid_embedding.vector) == 3


@pytest.mark.parametrize(
    "field",
    ["chunk_id", "model_id"],
)
def test_embedding_record_rejects_empty_identifiers(
    valid_embedding, field
):
    data = valid_embedding.model_dump()
    data[field] = ""

    with pytest.raises(ValidationError):
        EmbeddingRecord.model_validate(data)


def test_embedding_record_rejects_empty_vector(valid_embedding):
    data = valid_embedding.model_dump()
    data["vector"] = []

    with pytest.raises(ValidationError):
        EmbeddingRecord.model_validate(data)


def test_embedding_record_rejects_non_numeric_vector(valid_embedding):
    data = valid_embedding.model_dump()
    data["vector"] = [0.1, "invalid", 0.3]

    with pytest.raises(ValidationError):
        EmbeddingRecord.model_validate(data)


def test_embedding_record_json_round_trip(valid_embedding):
    json_data = valid_embedding.model_dump_json()
    restored = EmbeddingRecord.model_validate_json(json_data)

    assert restored == valid_embedding


# IndexingRequest tests

def test_indexing_request_valid(valid_request):
    assert valid_request.generation_id == "gen-001"
    assert len(valid_request.chunks) == 1
    assert len(valid_request.embeddings) == 1


def test_indexing_request_defaults_to_empty_embeddings(
    source_version, valid_chunk
):
    request = IndexingRequest(
        source=source_version,
        generation_id="gen-001",
        chunks=[valid_chunk],
    )

    assert request.embeddings == []


def test_indexing_request_rejects_empty_generation_id(valid_request):
    data = valid_request.model_dump()
    data["generation_id"] = ""

    with pytest.raises(ValidationError):
        IndexingRequest.model_validate(data)


def test_indexing_request_requires_chunks(valid_request):
    data = valid_request.model_dump()
    del data["chunks"]

    with pytest.raises(ValidationError):
        IndexingRequest.model_validate(data)


def test_indexing_request_rejects_invalid_chunk(valid_request):
    data = valid_request.model_dump()
    data["chunks"][0]["chunk_id"] = ""

    with pytest.raises(ValidationError):
        IndexingRequest.model_validate(data)


def test_indexing_request_preserves_access_metadata(valid_request):
    chunk = valid_request.chunks[0]

    assert chunk.access.tenant_id == "company-1"
    assert chunk.access.acl_principals == ["team-hamtayar"]


def test_indexing_request_json_round_trip(valid_request):
    json_data = valid_request.model_dump_json()
    restored = IndexingRequest.model_validate_json(json_data)

    assert restored == valid_request


# IndexingResult tests

def test_indexing_result_valid():
    result = IndexingResult(
        generation_id="gen-001",
        indexed_count=10,
        validated=True,
    )

    assert result.indexed_count == 10
    assert result.validated is True


def test_indexing_result_accepts_zero_indexed_count():
    result = IndexingResult(
        generation_id="gen-001",
        indexed_count=0,
    )

    assert result.indexed_count == 0


def test_indexing_result_rejects_negative_indexed_count():
    with pytest.raises(ValidationError):
        IndexingResult(
            generation_id="gen-001",
            indexed_count=-1,
        )


def test_indexing_result_defaults_to_not_validated():
    result = IndexingResult(
        generation_id="gen-001",
        indexed_count=5,
    )

    assert result.validated is False


def test_indexing_result_json_round_trip():
    original = IndexingResult(
        generation_id="gen-001",
        indexed_count=5,
        validated=True,
    )

    json_data = original.model_dump_json()
    restored = IndexingResult.model_validate_json(json_data)

    assert restored == original


# PublicationRequest tests

def test_publication_request_valid(source_version):
    request = PublicationRequest(
        source=source_version,
        generation_id="gen-001",
    )

    assert request.source.version == "v1"
    assert request.generation_id == "gen-001"


def test_publication_request_rejects_empty_generation_id(
    source_version,
):
    with pytest.raises(ValidationError):
        PublicationRequest(
            source=source_version,
            generation_id="",
        )


def test_publication_request_requires_source():
    with pytest.raises(ValidationError):
        PublicationRequest(generation_id="gen-001")


def test_publication_request_json_round_trip(source_version):
    original = PublicationRequest(
        source=source_version,
        generation_id="gen-001",
    )

    json_data = original.model_dump_json()
    restored = PublicationRequest.model_validate_json(json_data)

    assert restored == original


# PublicationResult tests

@pytest.mark.parametrize("published", [True, False])
def test_publication_result_accepts_boolean_status(published):
    result = PublicationResult(
        generation_id="gen-001",
        published=published,
    )

    assert result.published is published


def test_publication_result_requires_published():
    with pytest.raises(ValidationError):
        PublicationResult(generation_id="gen-001")


def test_publication_result_json_round_trip():
    original = PublicationResult(
        generation_id="gen-001",
        published=True,
    )

    json_data = original.model_dump_json()
    restored = PublicationResult.model_validate_json(json_data)

    assert restored == original
