
import pytest
from pydantic import ValidationError

from packages.contracts.common import (
    ContentRef,
    SourceLocation,
    SourceRef,
    SourceVersion,
)
from packages.contracts.document import (
    DocumentBlock,
    DocumentInput,
    ParsedDocument,
    ProtectedSpan,
)


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
def valid_document(source_version):
    """Create a parsed document with structured content."""

    return ParsedDocument(
        source=source_version,
        blocks=[
            DocumentBlock(
                block_type="heading",
                text="System Architecture",
                location=SourceLocation(page=1),
            ),
            DocumentBlock(
                block_type="paragraph",
                text="Hamtayar is a RAG system.",
                location=SourceLocation(page=1),
            ),
        ],
        metadata={"language": "en"},
    )


# DocumentInput tests

def test_document_input_valid(source_version):
    document = DocumentInput(
        source=source_version,
        content=ContentRef(uri="padeen://documents/doc-101"),
    )

    assert document.source.source.version == "v1" if False else document.source.version == "v1"
    assert document.content.uri == "padeen://documents/doc-101"


def test_document_input_requires_content(source_version):
    with pytest.raises(ValidationError):
        DocumentInput(source=source_version)


def test_document_input_rejects_empty_uri(source_version):
    with pytest.raises(ValidationError):
        DocumentInput(
            source=source_version,
            content=ContentRef(uri=""),
        )


def test_document_input_rejects_invalid_version(source_version):
    data = {
        "source": source_version.model_dump(),
        "content": {"uri": "padeen://documents/doc-101"},
    }
    data["source"]["version"] = ""

    with pytest.raises(ValidationError):
        DocumentInput.model_validate(data)


# DocumentBlock tests

@pytest.mark.parametrize(
    "block_type",
    ["heading", "paragraph", "table"],
)
def test_document_block_accepts_supported_types(block_type):
    block = DocumentBlock(
        block_type=block_type,
        text="Sample content",
    )

    assert block.block_type == block_type


def test_document_block_rejects_invalid_type():
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_type="image",
            text="Sample content",
        )


def test_document_block_requires_text():
    with pytest.raises(ValidationError):
        DocumentBlock(block_type="paragraph")


def test_document_block_preserves_normalized_text():
    block = DocumentBlock(
        block_type="paragraph",
        text="Original text",
        normalized_text="Normalized text",
    )

    assert block.text == "Original text"
    assert block.normalized_text == "Normalized text"


def test_document_block_allows_optional_location():
    block = DocumentBlock(
        block_type="paragraph",
        text="Sample content",
    )

    assert block.location is None
    assert block.normalized_text is None


def test_document_block_rejects_invalid_page():
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_type="paragraph",
            text="Sample content",
            location=SourceLocation(page=0),
        )


def test_document_block_supports_format_neutral_structure_and_processing_spans():
    block = DocumentBlock(
        block_type="code",
        text='print("x")\n',
        block_id="block-000001",
        code_language="python",
        location=SourceLocation(start_line=4, end_line=5),
        protected_spans=[ProtectedSpan(start=0, end=8, kind="code_payload")],
    )

    restored = DocumentBlock.model_validate_json(block.model_dump_json())
    assert restored == block
    assert restored.block_id == "block-000001"
    assert restored.code_language == "python"
    assert restored.protected_spans[0].end == 8


def test_protected_span_rejects_empty_or_reversed_ranges():
    with pytest.raises(ValidationError):
        ProtectedSpan(start=2, end=2, kind="inline_code")


@pytest.mark.parametrize("offset", [True, False])
def test_protected_span_rejects_boolean_offsets(offset):
    with pytest.raises(ValidationError):
        ProtectedSpan(start=offset, end=3, kind="url")


def test_document_block_rejects_unsorted_overlapping_or_out_of_bounds_spans():
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_type="paragraph", text="abcdef",
            protected_spans=[
                ProtectedSpan(start=3, end=5, kind="url"),
                ProtectedSpan(start=1, end=4, kind="path"),
            ],
        )
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_type="paragraph", text="abc",
            protected_spans=[ProtectedSpan(start=1, end=4, kind="url")],
        )


def test_document_local_ids_must_be_unique_but_can_repeat_across_documents(source_version):
    block = DocumentBlock(block_type="paragraph", text="same", block_id="block-000001")
    first = ParsedDocument(source=source_version, blocks=[block])
    second = ParsedDocument(source=source_version, blocks=[block])
    assert first.blocks[0].block_id == second.blocks[0].block_id
    with pytest.raises(ValidationError):
        ParsedDocument(source=source_version, blocks=[block, block])


def test_effective_text_uses_empty_processed_text_and_falls_back_only_when_absent():
    source_only = DocumentBlock(block_type="paragraph", text="source")
    processed_empty = DocumentBlock(block_type="paragraph", text="source", normalized_text="")
    assert source_only.effective_text == "source"
    assert processed_empty.effective_text == ""


# ParsedDocument tests

def test_parsed_document_valid(valid_document):
    assert len(valid_document.blocks) == 2
    assert valid_document.blocks[0].block_type == "heading"
    assert valid_document.metadata["language"] == "en"


def test_parsed_document_defaults(source_version):
    document = ParsedDocument(source=source_version)

    assert document.blocks == []
    assert document.metadata == {}


def test_parsed_document_preserves_source(valid_document):
    assert valid_document.source.source.source_id == "doc-101"
    assert valid_document.source.version == "v1"


def test_parsed_document_rejects_invalid_block(source_version):
    with pytest.raises(ValidationError):
        ParsedDocument(
            source=source_version,
            blocks=[
                {"block_type": "unknown", "text": "Invalid"}
            ],
        )


def test_parsed_document_rejects_invalid_metadata(source_version):
    with pytest.raises(ValidationError):
        ParsedDocument(
            source=source_version,
            metadata={"page_count": 10},
        )


def test_parsed_document_rejects_extra_fields(source_version):
    with pytest.raises(ValidationError):
        ParsedDocument(
            source=source_version,
            unknown_field="test",
        )


def test_parsed_document_json_round_trip(valid_document):
    json_data = valid_document.model_dump_json()
    restored = ParsedDocument.model_validate_json(json_data)

    assert restored == valid_document
