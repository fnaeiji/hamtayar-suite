"""Tests for general document text cleaning."""

from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument
from packages.documents.cleaning import CleaningConfig, DocumentCleaner


def sample_document() -> ParsedDocument:
    source = SourceVersion(source=SourceRef(source_id="s1", knowledge_space_id="k1", source_type="document"), version="v1")
    return ParsedDocument(source=source, blocks=[DocumentBlock(block_type="paragraph", text=" a\x00  b\ufeff\u200c\n\n\n c ", location=SourceLocation(page=2, start_line=3, end_line=4))], metadata={"tag": "kept"})


def test_clean_text_removes_controls_and_invisible_junk_but_keeps_newlines_and_zwnj() -> None:
    assert DocumentCleaner.clean_text("a\x00\ufeff\u200b\u200c\n\tb") == "a\u200c\n\tb"
    emoji = "\U0001f469\u200d\U0001f4bb"
    assert DocumentCleaner.clean_text(emoji) == emoji


def test_clean_text_normalizes_whitespace_and_blank_lines() -> None:
    assert DocumentCleaner.clean_text("a\u00a0  b  \r\n\r\n\r\n c ") == "a b  \n\n\n c "


def test_clean_document_preserves_source_and_structure() -> None:
    doc = sample_document()
    result = DocumentCleaner.clean_document(doc)
    assert result.blocks[0].text == doc.blocks[0].text
    assert result.blocks[0].normalized_text == " a b\u200c\n\n\n c "
    assert result.blocks[0].location == doc.blocks[0].location
    assert result.source == doc.source
    assert result.metadata["tag"] == "kept"
    assert result.metadata["processing.cleaning_profile"] == "document-cleaning-v2"
    assert result is not doc and result.blocks[0] is not doc.blocks[0]
    assert isinstance(result, ParsedDocument)


def test_config_can_disable_control_cleanup() -> None:
    assert DocumentCleaner.clean_text("a\x00b", CleaningConfig(remove_control_chars=False)) == "a\x00b"
