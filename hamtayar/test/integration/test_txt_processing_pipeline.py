"""Run a TXT fixture through parsing, cleaning, and normalization."""

from pathlib import Path

from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.document import ParsedDocument
from packages.documents.cleaning import DocumentCleaner
from packages.documents.normalization import PersianNormalizer
from packages.ingestion.txt import TxtParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "txt"


def test_txt_cleaning_normalization_pipeline() -> None:
    path = FIXTURES / "pipeline_sample.txt"
    source = SourceVersion(
        source=SourceRef(source_id="txt-pipeline-sample", knowledge_space_id="integration-tests", source_type="document"),
        version="v1",
    )
    parsed = TxtParser.parse_file(path, source)
    cleaned = DocumentCleaner.clean_document(parsed)
    processed = PersianNormalizer.normalize_document(cleaned)

    assert isinstance(processed, ParsedDocument)
    assert [block.block_type for block in processed.blocks] == ["paragraph"] * 4
    assert processed.blocks[0].normalized_text == "\u0631\u0627\u0647\u0646\u0645\u0627\u06cc \u0633\u0627\u0645\u0627\u0646\u0647"
    assert processed.blocks[1].normalized_text == "\u0645\u06cc\u200c\u0634\u0648\u062f\u060c \u06a9\u062a\u0627\u0628\u200c\u0647\u0627 \u0646\u0633\u062e\u0647 \u0664\u0665\u0666.   "
    assert "https://example.com/v2?id=123" in processed.blocks[2].normalized_text
    assert processed.blocks[3].normalized_text == "\u06cc\u0627\u062f\u062f\u0627\u0634\u062a \u0628\u0627 \u0641\u0627\u0635\u0644\u0647."
    assert processed.source == source
    assert processed.metadata["parser"] == "txt"
    assert processed.metadata["original_content"] == path.read_text(encoding="utf-8")
    assert processed.metadata["processing.cleaning_profile"] == DocumentCleaner.PROFILE
    assert processed.metadata["processing.normalization_profile"] == PersianNormalizer.PROFILE
    assert processed.metadata["processing.hazm_version"] == PersianNormalizer.hazm_version()
    assert [block.block_id for block in processed.blocks] == [f"block-{i:06d}" for i in range(1, 5)]
    assert [(block.location.start_line, block.location.end_line) for block in processed.blocks] == [
        (1, 1), (3, 3), (5, 5), (7, 7)
    ]
    assert processed.blocks[1].text == parsed.blocks[1].text
    assert ParsedDocument.model_validate(processed.model_dump()) == processed
