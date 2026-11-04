"""Regression checks for protected and structural document content."""

from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument, ProtectedSpan
from packages.documents.cleaning import DocumentCleaner
from packages.ingestion.markdown import MarkdownParser
from packages.documents.normalization import (
    PersianNormalizationConfig,
    PersianNormalizer,
)
from packages.ingestion.txt import TxtParser


def source() -> SourceVersion:
    return SourceVersion(
        source=SourceRef(source_id="regression", knowledge_space_id="tests", source_type="document"),
        version="v3",
    )


def test_markdown_code_inline_identifiers_headings_lists_and_hardbreaks() -> None:
    markdown = (
        "## \u0633\u0631\u0641\u0635\u0644\n\n"
        "\u0643\u064e\u062a\u0627\u0628 v1.2.3 user_id = 42 \U0001f469\u200d\U0001f4bb\n\n"
        "1. \u0646\u0633\u062e\u0647 42\n"
        "   - nested\n\n"
        "first line  \nsecond line `print(\"\u0643  123\")` and [link](https://example.test/v2?id=123)\n\n"
        "```python\n"
        "    print(\"\u0643  123\")\n"
        "```\n\n"
        "    print(\"\u0643  123\")\n"
    )
    parsed = MarkdownParser.parse_content(markdown, source(), file_path="sample.md")
    cleaned = DocumentCleaner.clean_document(parsed)
    processed = PersianNormalizer.normalize_document(cleaned)

    assert processed.blocks[0].block_type == "heading" and processed.blocks[0].heading_level == 2
    assert processed.blocks[0].normalized_text == "\u0633\u0631\u0641\u0635\u0644"
    prose = processed.blocks[1].normalized_text
    assert "v1.2.3" in prose and "user_id = 42" in prose
    assert "\u06a9\u062a\u0627\u0628" in prose
    assert "\U0001f469\u200d\U0001f4bb" in prose

    list_block = next(block for block in processed.blocks if block.block_type == "list")
    assert "1. \u0646\u0633\u062e\u0647 42" in list_block.normalized_text
    assert "   - nested" in list_block.normalized_text

    hardbreak = next(block for block in processed.blocks if "first line" in block.text)
    assert "first line  \nsecond line" in hardbreak.text
    assert '`print("\u0643  123")`' in hardbreak.normalized_text
    assert "https://example.test/v2?id=123" in hardbreak.normalized_text

    code = next(block for block in processed.blocks if block.block_type == "code")
    assert code.code_language == "python"
    assert code.text == '    print("\u0643  123")\n'
    assert code.normalized_text == code.text
    indented = processed.blocks[-1]
    assert indented.block_type == "code"
    assert indented.text == '    print("\u0643  123")'


def test_number_policies_only_change_unprotected_prose() -> None:
    source_text = "\u0646\u0633\u062e\u0647 42, version v1.2.3, `id=123`"
    source_document = MarkdownParser.parse_content(source_text, source())
    processed = PersianNormalizer.normalize_document(
        DocumentCleaner.clean_document(source_document),
        PersianNormalizationConfig(digit_policy="fa"),
    )
    result = processed.blocks[0].normalized_text
    assert "\u06f4\u06f2" in result
    assert "v1.2.3" in result and "`id=123`" in result


def test_txt_keeps_markdown_syntax_tabs_and_line_boundaries() -> None:
    text = "# ordinary text\n**not markdown**\tcolumn\tvalue\nsecond line\n"
    parsed = TxtParser.parse_content(text, source(), file_path="notes.txt")
    cleaned = DocumentCleaner.clean_document(parsed)
    processed = PersianNormalizer.normalize_document(cleaned)

    assert len(processed.blocks) == 1
    assert processed.blocks[0].block_type == "paragraph"
    assert processed.blocks[0].normalized_text == text.rstrip("\n")
    assert "# ordinary text" in processed.blocks[0].normalized_text
    assert "**not markdown**" in processed.blocks[0].normalized_text
    assert "\t" in processed.blocks[0].normalized_text
    assert processed.metadata["original_content"] == text
    assert processed.metadata["original_content_semantics"].startswith("decoded UTF-8 text")
    assert ParsedDocument.model_validate(processed.model_dump()) == processed


def test_cleaner_handles_bom_nul_and_newlines_without_dropping_joiners() -> None:
    text = "\ufeffA\x00\r\n\u0645\u06cc\u200c\u0631\u0648\u0645 \U0001f469\u200d\U0001f4bb"
    cleaned = DocumentCleaner.clean_text(text)
    assert cleaned == "A\n\u0645\u06cc\u200c\u0631\u0648\u0645 \U0001f469\u200d\U0001f4bb"


def test_protected_span_offsets_rebase_after_cleaning_and_diacritic_removal() -> None:
    original = "\x00\u064e\U0001f469 v1.2.3"
    identifier_start = original.index("v1.2.3")
    block = DocumentBlock(
        block_type="paragraph", text=original,
        protected_spans=[ProtectedSpan(
            start=identifier_start, end=identifier_start + len("v1.2.3"),
            kind="technical_identifier",
        )],
    )
    cleaned = DocumentCleaner.clean_block(block)
    normalized = PersianNormalizer.normalize_block(
        cleaned, PersianNormalizationConfig(digit_policy="fa"),
    )
    assert normalized.text == original
    assert normalized.normalized_text == "\U0001f469 v1.2.3"
    span = normalized.protected_spans[0]
    assert normalized.normalized_text[span.start:span.end] == "v1.2.3"
    assert span.start == len("\U0001f469 ")  # Python code points, not UTF-16 units.


def test_multiple_adjacent_and_boundary_spans_keep_exact_substrings() -> None:
    text = "abcdefghijk"
    spans = [
        ProtectedSpan(start=0, end=3, kind="inline_code"),
        ProtectedSpan(start=3, end=6, kind="inline_code"),
        ProtectedSpan(start=8, end=len(text), kind="inline_code"),
    ]
    block = DocumentBlock(block_type="paragraph", text=text, protected_spans=spans)
    processed = PersianNormalizer.normalize_block(
        block, PersianNormalizationConfig(digit_policy="fa"),
    )
    assert [(s.start, s.end) for s in processed.protected_spans] == [(0, 3), (3, 6), (8, len(text))]
    assert [processed.effective_text[s.start:s.end] for s in processed.protected_spans] == [
        "abc", "def", "ijk",
    ]


def test_protected_ranges_use_deduplicated_primary_kind_and_exact_url_destination() -> None:
    text = "[link](https://example.test/a(b)?id=42) v1.2.3 C:\\work\\release2\\file-42.txt"
    processed = PersianNormalizer.normalize_block(
        DocumentBlock(block_type="paragraph", text=text),
        PersianNormalizationConfig(digit_policy="fa"),
    )
    assert all("+" not in span.kind for span in processed.protected_spans)
    url_span = next(span for span in processed.protected_spans if span.kind == "url")
    assert processed.effective_text[url_span.start:url_span.end] == "https://example.test/a(b)?id=42"
    assert not processed.effective_text[url_span.start:url_span.end].endswith(")")
    version_span = next(span for span in processed.protected_spans if span.kind == "technical_identifier")
    assert processed.effective_text[version_span.start:version_span.end] == "v1.2.3"
    path_span = next(span for span in processed.protected_spans if span.kind == "path")
    assert processed.effective_text[path_span.start:path_span.end] == r"C:\work\release2\file-42.txt"


def test_processing_populates_effective_text_for_empty_disabled_and_code_blocks() -> None:
    empty = DocumentBlock(block_type="paragraph", text="\x00")
    code = DocumentBlock(block_type="code", text='print("\u0643  123")\n')
    doc = ParsedDocument(source=source(), blocks=[empty, code])
    cleaned = DocumentCleaner.clean_document(doc)
    disabled = PersianNormalizer.normalize_document(
        cleaned, PersianNormalizationConfig(enabled=False, digit_policy="fa"),
    )
    assert disabled.blocks[0].normalized_text == ""
    assert disabled.blocks[0].effective_text == ""
    assert disabled.blocks[1].normalized_text == code.text
    assert disabled.blocks[1].effective_text == code.text


def test_enabled_options_change_prose_but_not_protected_code_and_technical_text() -> None:
    text = "\u0643\u064eتاب 42, v1.2.3 `print(\"\u0643  123\")`"
    parsed = MarkdownParser.parse_content(text, source())
    cleaned = DocumentCleaner.clean_document(parsed)
    result = PersianNormalizer.normalize_document(
        cleaned,
        PersianNormalizationConfig(
            digit_policy="fa", correct_spacing=True, persian_style=True,
            reduce_repeated_characters=True,
        ),
    ).blocks[0].normalized_text
    assert "\u06a9تاب ۴۲" in result
    assert "v1.2.3" in result
    assert '`print("\u0643  123")`' in result


def test_repeated_markdown_parsing_is_deterministic_and_locations_are_source_lines() -> None:
    markdown = "# Heading\n\n- first\n  - nested\n\nlast\n"
    one = MarkdownParser.parse_content(markdown, source(), file_path="same.md")
    two = MarkdownParser.parse_content(markdown, source(), file_path="same.md")
    assert one.blocks == two.blocks
    assert [(b.block_id, b.block_type) for b in one.blocks] == [
        (b.block_id, b.block_type) for b in two.blocks
    ]
    assert one.blocks[0].location.start_line == one.blocks[0].location.end_line == 1
    list_block = next(b for b in one.blocks if b.block_type == "list")
    assert list_block.location.start_line == 3
    assert list_block.location.end_line == 4  # Blank separators are excluded; end is inclusive.
