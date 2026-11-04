import pytest
from pydantic import ValidationError

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import (
    Chunk,
    ChunkingItem,
    ChunkingRequest,
    ChunkingResult,
)
from packages.contracts.common import (
    SourceLocation,
    SourceRef,
    SourceVersion,
)
from packages.contracts.document import ProtectedSpan


@pytest.fixture
def source_version():
    """Create a valid document source version."""

    return SourceVersion(
        source=SourceRef(
            source_id="doc-101",
            knowledge_space_id="engineering",
            source_type="document",
        ),
        version="v1",
    )


@pytest.fixture
def access_metadata():
    """Create valid access metadata."""

    return AccessMetadata(
        tenant_id="company-1",
        acl_principals=["team-hamtayar"],
    )


@pytest.fixture
def valid_chunk(source_version, access_metadata):
    """Create a valid document chunk."""

    return Chunk(
        chunk_id="chunk-101",
        source=source_version,
        kind="document",
        text="Hamtayar is a RAG system.",
        access=access_metadata,
        location=SourceLocation(
            page=2,
            section="Architecture",
        ),
    )


# ChunkingItem tests


def test_chunking_item_valid():
    item = ChunkingItem(text="Sample content")

    assert item.text == "Sample content"


def test_chunking_item_accepts_empty_text_for_preparation():
    assert ChunkingItem(text="").text == ""


def test_chunking_item_defaults_document_structure_independently():
    first = ChunkingItem(text="code item")
    second = ChunkingItem(text="another code item")

    assert first.block_id is None
    assert first.block_type is None
    assert first.heading_level is None
    assert first.code_language is None
    assert first.protected_spans == []
    assert first.protected_spans is not second.protected_spans


def test_chunking_item_preserves_location_and_symbol():
    item = ChunkingItem(
        text="def get_user(): pass",
        location=SourceLocation(
            file_path="src/users.py",
            start_line=10,
            end_line=15,
        ),
        symbol_id="sym-101",
    )

    assert item.symbol_id == "sym-101"
    assert item.location.start_line == 10


def test_chunking_item_rejects_invalid_location():
    with pytest.raises(ValidationError):
        ChunkingItem(
            text="Sample content",
            location={"page": 0},
        )


def test_chunking_item_preserves_document_structure_and_protected_spans():
    item = ChunkingItem(
        text="`value`",
        block_id="block-000001",
        block_type="heading",
        heading_level=2,
        protected_spans=[ProtectedSpan(start=0, end=7, kind="inline_code")],
    )

    assert item.block_id == "block-000001"
    assert item.block_type == "heading"
    assert item.heading_level == 2
    assert item.protected_spans[0].end == 7


@pytest.mark.parametrize(
    "kwargs",
    [
        {"block_type": "paragraph", "heading_level": 2},
        {"block_type": "heading", "heading_level": 7},
        {"block_type": "paragraph", "code_language": "python"},
    ],
)
def test_chunking_item_rejects_inconsistent_heading_and_code_metadata(kwargs):
    with pytest.raises(ValidationError):
        ChunkingItem(text="content", **kwargs)


@pytest.mark.parametrize(
    "spans",
    [
        [ProtectedSpan(start=0, end=5, kind="url")],
        [
            ProtectedSpan(start=1, end=4, kind="url"),
            ProtectedSpan(start=3, end=4, kind="path"),
        ],
        [
            ProtectedSpan(start=2, end=4, kind="url"),
            ProtectedSpan(start=0, end=1, kind="path"),
        ],
    ],
)
def test_chunking_item_rejects_out_of_bounds_unsorted_or_overlapping_spans(spans):
    with pytest.raises(ValidationError):
        ChunkingItem(text="abcd", protected_spans=spans)


# ChunkingRequest tests


def test_chunking_request_valid(source_version, access_metadata):
    request = ChunkingRequest(
        source=source_version,
        kind="document",
        items=[ChunkingItem(text="Sample content")],
        access=access_metadata,
    )

    assert len(request.items) == 1
    assert request.source.version == "v1"


@pytest.mark.parametrize("kind", ["document", "code"])
def test_chunking_request_accepts_supported_kinds(
    source_version, access_metadata, kind
):
    request = ChunkingRequest(
        source=source_version,
        kind=kind,
        items=[ChunkingItem(text="Sample content")],
        access=access_metadata,
    )

    assert request.kind == kind


def test_chunking_request_rejects_invalid_kind(source_version, access_metadata):
    with pytest.raises(ValidationError):
        ChunkingRequest(
            source=source_version,
            kind="image",
            items=[ChunkingItem(text="Sample content")],
            access=access_metadata,
        )


def test_chunking_request_accepts_empty_items_for_empty_documents(
    source_version, access_metadata
):
    request = ChunkingRequest(
        source=source_version,
        kind="document",
        items=[],
        access=access_metadata,
    )

    assert request.items == []


def test_chunking_request_requires_access(source_version):
    with pytest.raises(ValidationError):
        ChunkingRequest(
            source=source_version,
            kind="document",
            items=[ChunkingItem(text="Sample content")],
        )


def test_chunking_request_default_profile(source_version, access_metadata):
    request = ChunkingRequest(
        source=source_version,
        kind="document",
        items=[ChunkingItem(text="Sample content")],
        access=access_metadata,
    )

    assert request.processing_profile == "default"


def test_chunking_request_rejects_invalid_item_structure(
    source_version, access_metadata
):
    with pytest.raises(ValidationError):
        ChunkingRequest(
            source=source_version,
            kind="document",
            items=[{"text": "content", "block_type": "image"}],
            access=access_metadata,
        )


def test_chunking_request_rejects_duplicate_document_block_ids(
    source_version, access_metadata
):
    with pytest.raises(ValidationError, match="unique within a document request"):
        ChunkingRequest(
            source=source_version,
            kind="document",
            items=[
                ChunkingItem(text="first", block_id="same"),
                ChunkingItem(text="second", block_id="same"),
            ],
            access=access_metadata,
        )


def test_chunking_request_keeps_legacy_code_item_shape(source_version, access_metadata):
    request = ChunkingRequest(
        source=source_version,
        kind="code",
        items=[ChunkingItem(text="def f(): pass", symbol_id="symbol-1")],
        access=access_metadata,
    )

    assert request.items[0].symbol_id == "symbol-1"
    assert request.items[0].block_type is None


def test_document_chunking_request_json_round_trip(source_version, access_metadata):
    original = ChunkingRequest(
        source=source_version,
        kind="document",
        items=[
            ChunkingItem(
                text="`code`",
                block_id="block-1",
                block_type="code",
                code_language="python",
                protected_spans=[ProtectedSpan(start=0, end=6, kind="inline_code")],
            )
        ],
        access=access_metadata,
    )

    restored = ChunkingRequest.model_validate_json(original.model_dump_json())

    assert restored == original


# Chunk tests


def test_chunk_valid(valid_chunk):
    assert valid_chunk.chunk_id == "chunk-101"
    assert valid_chunk.kind == "document"
    assert valid_chunk.text == "Hamtayar is a RAG system."


def test_chunk_rejects_empty_id(valid_chunk):
    data = valid_chunk.model_dump()
    data["chunk_id"] = ""

    with pytest.raises(ValidationError):
        Chunk.model_validate(data)


def test_chunk_rejects_empty_text(valid_chunk):
    data = valid_chunk.model_dump()
    data["text"] = ""

    with pytest.raises(ValidationError):
        Chunk.model_validate(data)


def test_chunk_requires_access(valid_chunk):
    data = valid_chunk.model_dump()
    del data["access"]

    with pytest.raises(ValidationError):
        Chunk.model_validate(data)


def test_chunk_default_metadata(valid_chunk):
    assert valid_chunk.metadata == {}


def test_chunk_preserves_source_and_location(valid_chunk):
    assert valid_chunk.source.source.source_id == "doc-101"
    assert valid_chunk.source.version == "v1"
    assert valid_chunk.location.page == 2
    assert valid_chunk.location.section == "Architecture"


def test_chunk_rejects_invalid_metadata(valid_chunk):
    data = valid_chunk.model_dump()
    data["metadata"] = {"language": ["en", "fa"]}

    with pytest.raises(ValidationError):
        Chunk.model_validate(data)


def test_chunk_json_round_trip(valid_chunk):
    json_data = valid_chunk.model_dump_json()
    restored = Chunk.model_validate_json(json_data)

    assert restored == valid_chunk
    assert restored.access.tenant_id == "company-1"


# ChunkingResult tests


def test_chunking_result_defaults():
    result = ChunkingResult()

    assert result.chunks == []


def test_chunking_result_contains_chunks(valid_chunk):
    result = ChunkingResult(chunks=[valid_chunk])

    assert len(result.chunks) == 1
    assert result.chunks[0].chunk_id == "chunk-101"


def test_chunking_result_rejects_invalid_chunk(valid_chunk):
    data = valid_chunk.model_dump()
    data["chunk_id"] = ""

    with pytest.raises(ValidationError):
        ChunkingResult(chunks=[data])


def test_chunking_result_json_round_trip(valid_chunk):
    original = ChunkingResult(chunks=[valid_chunk])

    json_data = original.model_dump_json()
    restored = ChunkingResult.model_validate_json(json_data)

    assert restored == original
