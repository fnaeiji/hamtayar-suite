"""Contract-level tests for Markdown parsing."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument
from packages.ingestion.markdown import MarkdownParser


@pytest.fixture
def source() -> SourceVersion:
    return SourceVersion(
        source=SourceRef(source_id="guide", knowledge_space_id="space", source_type="document"),
        version="v1",
    )


def test_headings_paragraphs_and_order(source: SourceVersion) -> None:
    content = "# Title\n\nIntro text.\n\n### Subheading\nMore text.\n###### Deep"
    result = MarkdownParser.parse_content(content, source)
    assert [block.block_type for block in result.blocks] == ["heading", "paragraph", "heading", "paragraph", "heading"]
    assert [block.text for block in result.blocks] == ["Title", "Intro text.", "Subheading", "More text.", "Deep"]
    assert [block.location.start_line for block in result.blocks] == [1, 3, 5, 6, 7]


def test_lists_nested_lists_and_inline_markdown_are_retained(source: SourceVersion) -> None:
    content = "1. First\n   - Nested\n2. Second\n\nText with `code` and [link](https://x.test)."
    result = MarkdownParser.parse_content(content, source)
    assert len(result.blocks) == 2
    assert result.blocks[0].block_type == "list"
    assert result.blocks[0].text == "1. First\n   - Nested\n2. Second\n"
    assert result.blocks[0].protected_spans[0].kind == "list_marker"
    assert "`code`" in result.blocks[1].text and "[link](https://x.test)" in result.blocks[1].text


def test_table_is_one_table_block_and_keeps_source_rows(source: SourceVersion) -> None:
    content = "| Name | Value |\n| --- | --- |\n| A | 1 |\n| B | 2 |"
    result = MarkdownParser.parse_content(content, source)
    assert len(result.blocks) == 1
    assert result.blocks[0].block_type == "table"
    assert result.blocks[0].text == content
    assert result.blocks[0].location.start_line == 1
    assert result.blocks[0].location.end_line == 4


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_fenced_code_and_unclosed_fence_are_preserved(source: SourceVersion, fence: str) -> None:
    content = f"{fence}python\nprint('hi')\n{fence}"
    result = MarkdownParser.parse_content(content, source)
    assert result.blocks[0].block_type == "code"
    assert result.blocks[0].text == "print('hi')\n"
    assert result.blocks[0].code_language == "python"
    assert result.blocks[0].location.end_line == 3
    unclosed = MarkdownParser.parse_content(f"{fence}js\nconst x = 1", source)
    assert unclosed.blocks[0].block_type == "code"
    assert unclosed.blocks[0].text == "const x = 1"


def test_quotes_images_links_and_horizontal_rule_gracefully_retained(source: SourceVersion) -> None:
    content = "> quoted\n> second\n\n![alt](image.png) [site](https://x.test)\n\n---"
    result = MarkdownParser.parse_content(content, source)
    assert [block.block_type for block in result.blocks] == ["quote", "paragraph", "paragraph"]
    assert result.blocks[0].text == "> quoted\n> second"
    assert "![alt](image.png)" in result.blocks[1].text
    assert result.blocks[2].text == "---"


@pytest.mark.parametrize("content", ["", " \n\t\n"])
def test_empty_and_whitespace_only_documents(source: SourceVersion, content: str) -> None:
    result = MarkdownParser.parse_content(content, source)
    assert result.blocks == []
    assert result.metadata["original_content"] == content


def test_file_parsing_records_path_and_line_locations(source: SourceVersion, tmp_path: Path) -> None:
    file = tmp_path / "readme.md"
    file.write_text("# Heading\n\nBody", encoding="utf-8")
    result = MarkdownParser.parse_file(file, source)
    assert isinstance(result, ParsedDocument)
    assert result.metadata["source_file"] == str(file)
    assert result.blocks[1].location.file_path == str(file)
    assert (result.blocks[1].location.start_line, result.blocks[1].location.end_line) == (3, 3)


def test_original_content_source_metadata_and_contract_validation(source: SourceVersion) -> None:
    content = "# H\n\nBody"
    result = MarkdownParser.parse_content(content, source, file_path="docs/a.md")
    assert result.source == source
    assert result.metadata["original_content"] == content
    assert result.metadata["source_file"] == "docs/a.md"
    assert all(isinstance(block, DocumentBlock) for block in result.blocks)
    assert ParsedDocument.model_validate(result.model_dump()) == result
    with pytest.raises(ValidationError):
        DocumentBlock(block_type="unknown", text="bad")


def test_malformed_markdown_does_not_fail(source: SourceVersion) -> None:
    content = "##No space heading\n\n| broken table\n\n```unclosed\ntext"
    result = MarkdownParser.parse_content(content, source)
    assert len(result.blocks) == 3
    assert result.blocks[-1].block_type == "code"
    assert result.blocks[-1].text == "text"


def test_path_errors_are_reported(source: SourceVersion, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        MarkdownParser.parse_file(tmp_path / "missing.md", source)
