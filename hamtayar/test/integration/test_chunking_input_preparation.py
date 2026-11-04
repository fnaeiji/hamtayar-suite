"""Exercise processed Markdown/TXT fixtures through chunk input preparation."""

from pathlib import Path

from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceRef, SourceVersion
from packages.documents.cleaning import DocumentCleaner
from packages.documents.normalization import PersianNormalizer
from packages.ingestion.markdown import MarkdownParser
from packages.ingestion.txt import TxtParser
from packages.knowledge.service import (
    count_prepared_request,
    load_configuration,
    prepare_chunking_request,
)
from packages.knowledge.tokenizer import TokenizerIdentity

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ACCESS = AccessMetadata(
    tenant_id="integration-tenant",
    acl_principals=["integration-reviewer"],
)


class _PipelineCountingFake:
    """Exercise request integration; real BGE verification has its own test."""

    identity = TokenizerIdentity(
        backend="test",
        tokenizer_id="test-only",
        configured_revision=None,
    )

    def __init__(self):
        self.inputs = []

    def count_tokens(self, text: str, *, include_special_tokens: bool) -> int:
        self.inputs.append((text, include_special_tokens))
        return len(text)


def _source(source_id: str) -> SourceVersion:
    return SourceVersion(
        source=SourceRef(
            source_id=source_id,
            knowledge_space_id="chunking-integration",
            source_type="document",
        ),
        version="v1",
    )


def test_markdown_parser_cleaner_normalizer_preparation_pipeline():
    path = FIXTURES / "markdown" / "pipeline_sample.md"
    source = _source("markdown-chunking-fixture")
    parsed = MarkdownParser.parse_file(path, source)
    cleaned = DocumentCleaner.clean_document(parsed)
    processed = PersianNormalizer.normalize_document(cleaned)
    configuration = load_configuration()
    request = prepare_chunking_request(
        processed, access=ACCESS, configuration=configuration
    )
    counter = _PipelineCountingFake()
    report = count_prepared_request(
        request, configuration=configuration, tokenizer=counter
    )

    assert [item.block_type for item in request.items] == [
        block.block_type for block in processed.blocks
    ]
    assert [item.block_id for item in request.items] == [
        block.block_id for block in processed.blocks
    ]
    assert [item.text for item in request.items] == [
        block.effective_text for block in processed.blocks
    ]
    assert request.items[0].heading_level == processed.blocks[0].heading_level == 1
    code_item = next(item for item in request.items if item.block_type == "code")
    assert code_item.code_language == "python"
    assert request.items[-1].location.file_path == str(path)
    assert request.source == source
    assert request.access == ACCESS
    assert [item.token_count for item in report.items] == [
        len(item.text) for item in request.items
    ]
    assert [text for text, _include_special in counter.inputs] == [
        item.text for item in request.items
    ]
    assert processed.metadata["processing.cleaning_profile"] == DocumentCleaner.PROFILE
    assert (
        processed.metadata["processing.normalization_profile"]
        == PersianNormalizer.PROFILE
    )
    assert processed.metadata["processing.hazm_version"]
    assert processed.metadata["parser"] == "markdown"


def test_txt_parser_cleaner_normalizer_preparation_pipeline():
    path = FIXTURES / "txt" / "pipeline_sample.txt"
    source = _source("txt-chunking-fixture")
    parsed = TxtParser.parse_file(path, source)
    cleaned = DocumentCleaner.clean_document(parsed)
    processed = PersianNormalizer.normalize_document(cleaned)
    configuration = load_configuration()
    request = prepare_chunking_request(
        processed, access=ACCESS, configuration=configuration
    )
    counter = _PipelineCountingFake()
    report = count_prepared_request(
        request, configuration=configuration, tokenizer=counter
    )

    assert [item.block_type for item in request.items] == ["paragraph"] * 4
    assert [item.text for item in request.items] == [
        block.effective_text for block in processed.blocks
    ]
    assert [item.block_id for item in request.items] == [
        block.block_id for block in processed.blocks
    ]
    assert [item.location for item in request.items] == [
        block.location for block in processed.blocks
    ]
    assert request.source == source
    assert request.access == ACCESS
    assert [item.token_count for item in report.items] == [
        len(item.text) for item in request.items
    ]
    assert [text for text, _include_special in counter.inputs] == [
        item.text for item in request.items
    ]
    assert processed.metadata["processing.cleaning_profile"] == DocumentCleaner.PROFILE
    assert (
        processed.metadata["processing.normalization_profile"]
        == PersianNormalizer.PROFILE
    )
    assert processed.metadata["processing.hazm_version"]
    assert processed.metadata["parser"] == "txt"
