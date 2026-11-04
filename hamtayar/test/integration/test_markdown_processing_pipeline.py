"""Run a Markdown fixture through parsing, cleaning, and normalization."""

from pathlib import Path

from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.document import ParsedDocument
from packages.documents.cleaning import DocumentCleaner
from packages.ingestion.markdown import MarkdownParser
from packages.documents.normalization import PersianNormalizer

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "markdown"


def test_markdown_cleaning_normalization_pipeline() -> None:
    path = FIXTURES / "pipeline_sample.md"
    source = SourceVersion(
        source=SourceRef(source_id="markdown-pipeline-sample", knowledge_space_id="integration-tests", source_type="document"),
        version="v1",
    )
    parsed = MarkdownParser.parse_file(path, source)
    cleaned = DocumentCleaner.clean_document(parsed)
    processed = PersianNormalizer.normalize_document(cleaned)

    assert isinstance(processed, ParsedDocument)
    assert [block.block_type for block in processed.blocks] == ["heading", "paragraph", "table", "code"]
    assert processed.blocks[0].heading_level == 1
    assert processed.blocks[0].normalized_text == "\u0631\u0627\u0647\u0646\u0645\u0627\u06cc \u06a9\u0627\u0631\u0628\u0631\u06cc"
    assert processed.blocks[1].normalized_text == "\u0645\u06cc\u200c\u0634\u0648\u062f\u060c \u06a9\u062a\u0627\u0628\u200c\u0647\u0627 \u0628\u0627 \u0646\u0633\u062e\u0647 \u0664\u0665\u0666.   "
    assert processed.blocks[2].normalized_text.endswith("| \u0645\u062f\u0644 | \u0661\u0662 |")
    assert processed.blocks[3].code_language == "python"
    assert processed.blocks[3].text == "value = 42 # \u0643\u062f\n"
    assert processed.blocks[3].normalized_text == processed.blocks[3].text
    assert processed.blocks[3].block_id == "block-000004"
    assert processed.source == source
    assert processed.metadata["parser"] == "markdown"
    assert processed.metadata["original_content"] == path.read_text(encoding="utf-8")
    assert processed.metadata["processing.cleaning_profile"] == DocumentCleaner.PROFILE
    assert processed.metadata["processing.normalization_profile"] == PersianNormalizer.PROFILE
    assert processed.metadata["processing.hazm_version"] == PersianNormalizer.hazm_version()
    assert [(block.location.start_line, block.location.end_line) for block in processed.blocks] == [
        (1, 1), (3, 3), (5, 7), (9, 11)
    ]
    assert all(block.location.file_path == str(path) for block in processed.blocks)
    assert processed.blocks[0].location == SourceLocation(file_path=str(path), start_line=1, end_line=1)
    assert ParsedDocument.model_validate(processed.model_dump()) == processed
