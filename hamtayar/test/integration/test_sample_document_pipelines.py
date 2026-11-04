"""Run the document pipeline on the larger Markdown and TXT sample files."""

import json
from pathlib import Path
from typing import Any

from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.document import ParsedDocument
from packages.documents.cleaning import DocumentCleaner
from packages.ingestion.markdown import MarkdownParser
from packages.documents.normalization import PersianNormalizer
from packages.ingestion.txt import TxtParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
OUTPUTS = Path(__file__).resolve().parents[1] / "outputs" / "documents"
PATH_MARKERS = {
    "markdown": "test/fixtures/markdown/sample_document.md",
    "txt": "test/fixtures/txt/sample_document.txt",
}


def _snapshot_data(document: ParsedDocument, source_path: Path, path_marker: str) -> dict[str, Any]:
    """Replace machine-specific absolute paths with stable fixture paths."""
    data = document.model_dump(mode="json")
    data["metadata"]["source_file"] = path_marker
    for block in data["blocks"]:
        if block["location"] is not None and block["location"]["file_path"] == str(source_path):
            block["location"]["file_path"] = path_marker
    return data


def _run_pipeline(kind: str, extension: str) -> tuple[ParsedDocument, ParsedDocument, Path]:
    path = (FIXTURES / kind / f"sample_document.{extension}").resolve()
    source = SourceVersion(
        source=SourceRef(
            source_id=f"sample-document-{kind}",
            knowledge_space_id="integration-tests",
            source_type="document",
        ),
        version="v1",
    )
    parser = MarkdownParser if kind == "markdown" else TxtParser
    parsed = parser.parse_file(path, source)
    cleaned = DocumentCleaner.clean_document(parsed)
    processed = PersianNormalizer.normalize_document(cleaned)
    return parsed, processed, path


def test_sample_markdown_file_pipeline() -> None:
    parsed, processed, path = _run_pipeline("markdown", "md")

    assert [block.block_type for block in processed.blocks].count("heading") >= 4
    assert processed.blocks[0].block_type == "heading"
    assert processed.blocks[0].heading_level == 1
    assert processed.blocks[0].normalized_text == "\u0631\u0627\u0647\u0646\u0645\u0627\u06cc \u0622\u0632\u0645\u0627\u06cc\u0634\u06cc \u0633\u0627\u0645\u0627\u0646\u0647 \u062e\u062f\u0645\u0627\u062a"
    assert any(block.block_type == "table" for block in processed.blocks)
    assert "https://example.org/docs/123?q=" in next(
        block.normalized_text for block in processed.blocks if "https://example.org/docs/123" in block.text
    )
    code_block = next(block for block in processed.blocks if block.block_type == "code")
    assert code_block.code_language == "python"
    assert '    print("\u0643  123")' in code_block.text
    assert code_block.normalized_text == code_block.text
    version_line = next(block.normalized_text for block in processed.blocks if "version v1.2.3" in block.text)
    assert "version v1.2.3" in version_line
    assert "\U0001f469\u200d\U0001f4bb" in processed.metadata["original_content"]
    nested_list = next(block for block in processed.blocks if block.block_type == "list" and "\u0646\u0633\u062e\u0647 English" in block.text)
    assert "  - " in nested_list.text
    hard_break_block = next(block for block in processed.blocks if "\u062f\u0648 \u0641\u0627\u0635\u0644\u0647 \u067e\u0627\u06cc\u0627\u0646" in block.text)
    assert "  \n" in hard_break_block.text
    assert processed.metadata["original_content"] == path.read_text(encoding="utf-8")
    assert processed.metadata["source_file"] == str(path)
    assert processed.source == parsed.source
    assert all(block.location.file_path == str(path) for block in processed.blocks)

    snapshot = OUTPUTS / "sample_markdown_processed.json"
    expected = json.loads(snapshot.read_text(encoding="utf-8"))
    assert _snapshot_data(processed, path, PATH_MARKERS["markdown"]) == expected


def test_sample_txt_file_pipeline() -> None:
    parsed, processed, path = _run_pipeline("txt", "txt")

    assert all(block.block_type == "paragraph" for block in processed.blocks)
    assert len(processed.blocks) == 9
    assert processed.blocks[0].normalized_text == "\u0631\u0627\u0647\u0646\u0645\u0627\u06cc \u0622\u0632\u0645\u0627\u06cc\u0634\u06cc \u0633\u0627\u0645\u0627\u0646\u0647 \u062e\u062f\u0645\u0627\u062a \u2014 \u0645\u062a\u0646 \u0633\u0627\u062f\u0647"
    assert "https://" not in processed.blocks[1].normalized_text
    assert chr(0) not in processed.blocks[6].normalized_text
    assert chr(0) in parsed.blocks[6].text
    assert processed.blocks[7].normalized_text.startswith("# ")
    assert processed.blocks[7].normalized_text.count("**") == 2
    assert "\t" in processed.blocks[4].normalized_text
    assert not any(block.block_type == "table" for block in processed.blocks)
    assert "123 / \u06f1\u06f2\u06f3 / \u0661\u0662\u0663" in processed.blocks[1].normalized_text
    assert processed.metadata["original_content"] == path.read_text(encoding="utf-8")
    assert processed.metadata["source_file"] == str(path)
    assert processed.source == parsed.source
    assert all(block.location.file_path == str(path) for block in processed.blocks)

    snapshot = OUTPUTS / "sample_txt_processed.json"
    expected = json.loads(snapshot.read_text(encoding="utf-8"))
    assert _snapshot_data(processed, path, PATH_MARKERS["txt"]) == expected
