"""Regression coverage for conservative Hazm-backed normalization."""

from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument, ProtectedSpan
from packages.ingestion.markdown import MarkdownParser
from packages.documents.normalization import (
    PersianNormalizationConfig,
    PersianNormalizer,
)


def test_arabic_characters_diacritics_and_tatweel() -> None:
    source = "\u0639\u0644\u064a \u0643\u064e\u062a\u0627\u0628\u0640 \u0622 \u0621"
    expected = "\u0639\u0644\u06cc \u06a9\u062a\u0627\u0628 \u0622 \u0621"
    assert PersianNormalizer.normalize_text(source) == expected
    config = PersianNormalizationConfig(remove_diacritics=False, remove_tatweel=False)
    unchanged_marks = PersianNormalizer.normalize_text(source, config)
    assert "\u064e" in unchanged_marks and "\u0640" in unchanged_marks


def test_affix_spacing_and_meaningful_joiners() -> None:
    text = "\u0645\u06cc \u0634\u0648\u062f \u06a9\u062a\u0627\u0628 \u0647\u0627 \u0628\u0647\u062a\u0631\u06cc\u0646"
    expected = "\u0645\u06cc\u200c\u0634\u0648\u062f \u06a9\u062a\u0627\u0628\u200c\u0647\u0627 \u0628\u0647\u062a\u0631\u06cc\u0646"
    assert PersianNormalizer.normalize_text(text) == expected
    assert PersianNormalizer.normalize_text("\u0646\u0645\u06cc\u200c\u200c\u062f\u0627\u0646\u0645") == "\u0646\u0645\u06cc\u200c\u062f\u0627\u0646\u0645"
    emoji = "\U0001f469\u200d\U0001f4bb"
    assert PersianNormalizer.normalize_text(emoji) == emoji


def test_number_conversion_is_opt_in_and_protects_identifiers() -> None:
    text = "\u0646\u0633\u062e\u0647 123 \u0648 \u0664\u0665\u0666 \u0648 \u06f7\u06f8\u06f9"
    assert PersianNormalizer.normalize_text(text) == text
    assert PersianNormalizer.normalize_text(text, PersianNormalizationConfig(digit_policy="fa")) == (
        "\u0646\u0633\u062e\u0647 \u06f1\u06f2\u06f3 \u0648 \u06f4\u06f5\u06f6 \u0648 \u06f7\u06f8\u06f9"
    )
    assert PersianNormalizer.normalize_text(text, PersianNormalizationConfig(digit_policy="en")) == (
        "\u0646\u0633\u062e\u0647 123 \u0648 456 \u0648 789"
    )
    tech = "\u0646\u0633\u062e\u0647 v1.2.3 user_id = 42"
    assert PersianNormalizer.normalize_text(tech, PersianNormalizationConfig(digit_policy="fa")) == tech


def test_parser_spans_protect_inline_code_and_link_destination() -> None:
    src = SourceVersion(source=SourceRef(source_id="s", knowledge_space_id="k", source_type="document"), version="v1")
    content = "\u0645\u062a\u0646 `print(\"\u0643  123\")` [\u067e\u06cc\u0648\u0646\u062f](https://example.org/v2?id=123)"
    parsed = MarkdownParser.parse_content(content, src)
    block = parsed.blocks[0]
    assert block.protected_spans and block.protected_spans[0].kind == "inline_code"
    normalized = PersianNormalizer.normalize_block(block, PersianNormalizationConfig(digit_policy="fa"))
    assert '`print("\u0643  123")`' in normalized.normalized_text
    assert "https://example.org/v2?id=123" in normalized.normalized_text


def test_code_blocks_are_exact_bypass_and_contract_fields_survive() -> None:
    block = DocumentBlock(
        block_type="code",
        text='print("\u0643  123")\n',
        code_language="python",
        location=SourceLocation(start_line=3, end_line=3),
        block_id="block-000001",
    )
    result = PersianNormalizer.normalize_block(block, PersianNormalizationConfig(digit_policy="fa"))
    assert result.normalized_text == block.text
    assert result.text == block.text and result.code_language == "python"
    assert result.block_id == block.block_id and result.location == block.location


def test_normalization_disabled_is_an_exact_bypass() -> None:
    text = "\u0643\u064e  v1.2.3\u200c\U0001f469\u200d\U0001f4bb"
    assert PersianNormalizer.normalize_text(text, PersianNormalizationConfig(enabled=False)) == text


def test_spans_are_rebased_after_cleaning_changes_prefix_length() -> None:
    text = "\u0643\u062a\u0627\u0628   v1.2.3   123"
    start = text.index("v1.2.3")
    block = DocumentBlock(
        block_type="paragraph",
        text=text,
        protected_spans=[ProtectedSpan(start=start, end=start + len("v1.2.3"), kind="technical_identifier")],
    )
    from packages.documents.cleaning import DocumentCleaner

    cleaned = DocumentCleaner.clean_block(block)
    processed = PersianNormalizer.normalize_block(cleaned, PersianNormalizationConfig(digit_policy="fa"))
    assert processed.normalized_text == "\u06a9\u062a\u0627\u0628 v1.2.3 \u06f1\u06f2\u06f3"
    span = next(span for span in processed.protected_spans if span.kind == "technical_identifier")
    assert processed.normalized_text[span.start:span.end] == "v1.2.3"


def test_document_normalization_records_hazm_provenance() -> None:
    src = SourceVersion(source=SourceRef(source_id="s", knowledge_space_id="k", source_type="document"), version="v1")
    block = DocumentBlock(block_type="heading", text="\u0643\u0650\u062a\u0627\u0628", location=SourceLocation(page=1, section="intro"), heading_level=1, block_id="heading-1")
    doc = ParsedDocument(source=src, blocks=[block], metadata={"origin": "pdf"})
    result = PersianNormalizer.normalize_document(doc)
    assert result.blocks[0].normalized_text == "\u06a9\u062a\u0627\u0628"
    assert result.blocks[0].location == block.location
    assert result.source == src and result.metadata["origin"] == "pdf"
    assert result.metadata["processing.hazm_version"] == PersianNormalizer.hazm_version()
    assert result.metadata["processing.normalization_config"]
    assert ParsedDocument.model_validate(result.model_dump()) == result
