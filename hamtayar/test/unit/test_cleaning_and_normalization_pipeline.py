"""Contract-level integration for cleaning followed by Persian normalization."""

from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.document import DocumentBlock, ParsedDocument
from packages.documents.cleaning import DocumentCleaner
from packages.documents.normalization import (
    PersianNormalizationConfig,
    PersianNormalizer,
)


def test_document_pipeline_preserves_order_source_and_structure() -> None:
    source = SourceVersion(
        source=SourceRef(source_id="doc-1", knowledge_space_id="space-1", source_type="document"),
        version="v1",
    )
    blocks = [
        DocumentBlock(block_type="heading", text="\u0643\u0644\u064a\u0627\u062a", location=SourceLocation(page=1), heading_level=1),
        DocumentBlock(block_type="paragraph", text="\u0645\u064a\u200b   \u0634\u0648\u062f\x00  \u0643\u062a\u0627\u0628 \u0647\u0627", location=SourceLocation(page=1, start_line=2, end_line=2)),
        DocumentBlock(block_type="table", text="\u0633\u062a\u0648\u0646 \u0664\u0665\u0666", location=SourceLocation(page=2, sheet="S1", cell_range="A1:B1")),
        DocumentBlock(block_type="paragraph", text="\u06a9\u062f `user_id = 42`", location=SourceLocation(file_path="src/a.py", start_line=4, end_line=4)),
    ]
    doc = ParsedDocument(source=source, blocks=blocks, metadata={"extractor": "pdf"})
    cleaned = DocumentCleaner.clean_document(doc)
    output = PersianNormalizer.normalize_document(
        cleaned,
        PersianNormalizationConfig(digit_policy="fa"),
    )

    assert [block.block_type for block in output.blocks] == ["heading", "paragraph", "table", "paragraph"]
    assert output.blocks[1].normalized_text == "\u0645\u06cc\u200c\u0634\u0648\u062f \u06a9\u062a\u0627\u0628\u200c\u0647\u0627"
    assert output.blocks[2].normalized_text == "\u0633\u062a\u0648\u0646 \u06f4\u06f5\u06f6"
    assert output.blocks[3].normalized_text == "\u06a9\u062f `user_id = 42`"
    assert [block.location for block in output.blocks] == [block.location for block in blocks]
    assert output.source == source and output.metadata["extractor"] == "pdf"
    assert output.metadata["processing.cleaning_profile"] == DocumentCleaner.PROFILE
    assert output.metadata["processing.normalization_profile"] == PersianNormalizer.PROFILE
    assert [block.text for block in output.blocks] == [block.text for block in blocks]
    assert ParsedDocument.model_validate(output.model_dump()) == output
