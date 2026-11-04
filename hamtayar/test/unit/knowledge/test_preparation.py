import pytest

from packages.contracts.access import AccessMetadata
from packages.contracts.chunks import ChunkingRequest
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument, ProtectedSpan
from packages.knowledge.service import load_configuration, prepare_chunking_request


@pytest.fixture
def source_version():
    return SourceVersion(
        source=SourceRef(
            source_id="document-42",
            knowledge_space_id="research",
            source_type="document",
        ),
        version="rev-7",
    )


@pytest.fixture
def access_metadata():
    return AccessMetadata(tenant_id="tenant-test", acl_principals=["group-reviewers"])


@pytest.fixture
def configuration():
    return load_configuration()


def test_maps_every_document_block_type_and_preserves_structure(
    source_version, access_metadata, configuration
):
    blocks = [
        DocumentBlock(
            block_type="heading",
            text="Heading",
            normalized_text="Heading",
            block_id="block-1",
            heading_level=2,
            location=SourceLocation(file_path="guide.md", start_line=1, end_line=1),
        ),
        DocumentBlock(
            block_type="paragraph",
            text="fallback text",
            normalized_text=None,
            block_id="block-2",
            location=SourceLocation(start_line=2, end_line=3),
        ),
        DocumentBlock(
            block_type="list",
            text="- item",
            normalized_text="  - item",
            block_id="block-3",
        ),
        DocumentBlock(
            block_type="table", text="|a|", normalized_text="|a|", block_id="block-4"
        ),
        DocumentBlock(
            block_type="code",
            text="print(1)",
            normalized_text="print(1)",
            block_id="block-5",
            code_language="python",
        ),
        DocumentBlock(
            block_type="quote",
            text="> quoted",
            normalized_text="> quoted",
            block_id="block-6",
        ),
    ]
    document = ParsedDocument(
        source=source_version,
        blocks=blocks,
        metadata={
            "original_content": "full source is deliberately not copied",
            "processing.cleaning_profile": "clean-v2",
            "processing.normalization_profile": "normalize-v2",
        },
    )

    request = prepare_chunking_request(
        document, access=access_metadata, configuration=configuration
    )

    assert request.kind == "document"
    assert request.source == source_version
    assert request.source.source.knowledge_space_id == "research"
    assert request.source.source.source_id == "document-42"
    assert request.source.version == "rev-7"
    assert [item.block_type for item in request.items] == [
        "heading",
        "paragraph",
        "list",
        "table",
        "code",
        "quote",
    ]
    assert [item.block_id for item in request.items] == [
        f"block-{i}" for i in range(1, 7)
    ]
    assert [item.text for item in request.items] == [
        "Heading",
        "fallback text",
        "  - item",
        "|a|",
        "print(1)",
        "> quoted",
    ]
    assert request.items[0].heading_level == 2
    assert request.items[4].code_language == "python"
    assert request.items[0].location == blocks[0].location
    assert request.items[1].location == blocks[1].location
    assert request.items[0].symbol_id is None
    assert request.processing_profile == configuration.chunking.profile
    assert request.access == access_metadata
    dumped_items = [item.model_dump() for item in request.items]
    assert all("original_content" not in item for item in dumped_items)
    assert "processing.cleaning_profile" not in request.model_dump()


@pytest.mark.parametrize(
    ("text", "normalized_text", "expected"),
    [
        ("source text", None, "source text"),
        ("source text", "", ""),
        ("source text", " \t ", " \t "),
    ],
)
def test_effective_text_preserves_none_empty_and_whitespace(
    source_version, access_metadata, configuration, text, normalized_text, expected
):
    document = ParsedDocument(
        source=source_version,
        blocks=[
            DocumentBlock(
                block_type="paragraph",
                text=text,
                normalized_text=normalized_text,
            )
        ],
    )

    request = prepare_chunking_request(
        document, access=access_metadata, configuration=configuration
    )

    assert request.items[0].text == expected


def test_empty_document_produces_empty_prepared_request(
    source_version, access_metadata, configuration
):
    request = prepare_chunking_request(
        ParsedDocument(source=source_version),
        access=access_metadata,
        configuration=configuration,
    )

    assert request.items == []
    assert request.source == source_version
    assert request.access == access_metadata
    assert request.processing_profile == configuration.chunking.profile


def test_protected_spans_keep_coordinates_and_substrings(
    source_version, access_metadata, configuration
):
    document = ParsedDocument(
        source=source_version,
        blocks=[
            DocumentBlock(
                block_type="paragraph",
                text="source",
                normalized_text="pré `value`",
                protected_spans=[ProtectedSpan(start=4, end=11, kind="inline_code")],
                location=SourceLocation(
                    file_path="source.md", start_line=4, end_line=4
                ),
            )
        ],
    )

    request = prepare_chunking_request(
        document, access=access_metadata, configuration=configuration
    )

    item = request.items[0]
    span = item.protected_spans[0]
    assert item.text[span.start : span.end] == "`value`"
    assert (span.start, span.end) == (4, 11)
    assert item.location == SourceLocation(
        file_path="source.md", start_line=4, end_line=4
    )


def test_preparation_copies_mutable_source_access_location_and_spans(
    source_version, access_metadata, configuration
):
    document = ParsedDocument(
        source=source_version,
        blocks=[
            DocumentBlock(
                block_type="paragraph",
                text="https://example.test",
                block_id="block-1",
                location=SourceLocation(
                    file_path="source.txt", start_line=1, end_line=1
                ),
                protected_spans=[ProtectedSpan(start=0, end=20, kind="url")],
            )
        ],
    )

    request = prepare_chunking_request(
        document, access=access_metadata, configuration=configuration
    )
    request.access.acl_principals.append("new-principal")
    request.items[0].protected_spans[0].kind = "path"
    request.items[0].location.file_path = "changed.txt"
    request.source.source.source_id = "changed-id"

    assert access_metadata.acl_principals == ["group-reviewers"]
    assert document.blocks[0].protected_spans[0].kind == "url"
    assert document.blocks[0].location.file_path == "source.txt"
    assert document.source.source.source_id == "document-42"


def test_missing_block_ids_and_locations_remain_missing(
    source_version, access_metadata, configuration
):
    document = ParsedDocument(
        source=source_version,
        blocks=[DocumentBlock(block_type="paragraph", text="no invented identity")],
    )

    item = prepare_chunking_request(
        document, access=access_metadata, configuration=configuration
    ).items[0]

    assert item.block_id is None
    assert item.location is None


def test_only_document_sources_can_be_prepared(access_metadata, configuration):
    repository_source = SourceVersion(
        source=SourceRef(
            source_id="repo-1",
            knowledge_space_id="research",
            source_type="repository",
        ),
        version="commit-1",
    )

    with pytest.raises(ValueError, match="requires a document source"):
        prepare_chunking_request(
            ParsedDocument(source=repository_source),
            access=access_metadata,
            configuration=configuration,
        )


def test_prepared_request_round_trips_through_shared_contracts(
    source_version, access_metadata, configuration
):
    document = ParsedDocument(
        source=source_version,
        blocks=[
            DocumentBlock(
                block_type="heading",
                text="Title",
                normalized_text="Title",
                block_id="block-1",
                heading_level=1,
            )
        ],
    )
    request = prepare_chunking_request(
        document, access=access_metadata, configuration=configuration
    )

    restored = ChunkingRequest.model_validate_json(request.model_dump_json())

    assert restored == request
