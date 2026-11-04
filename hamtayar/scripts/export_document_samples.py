"""Regenerate processed-document and prepared chunking-request review samples."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceRef, SourceVersion
from packages.documents.cleaning import DocumentCleaner
from packages.documents.normalization import PersianNormalizer
from packages.ingestion.markdown import MarkdownParser
from packages.ingestion.txt import TxtParser
from packages.knowledge.service import (
    count_prepared_request,
    create_tokenizer,
    load_configuration,
    prepare_chunking_request,
)


def export_samples(*, include_token_counts: bool = False) -> list[Path]:
    """Run both format pipelines and write stable UTF-8 JSON contract views."""
    outputs = ROOT / "test" / "outputs" / "documents"
    outputs.mkdir(parents=True, exist_ok=True)
    artifacts: list[Path] = []
    configuration = load_configuration()
    tokenizer = create_tokenizer(configuration) if include_token_counts else None
    token_diagnostics: list[dict[str, object]] = []

    for file_type, extension, parser, source_id in (
        ("markdown", "md", MarkdownParser, "sample-document-markdown"),
        ("txt", "txt", TxtParser, "sample-document-txt"),
    ):
        relative_path = (
            Path("test") / "fixtures" / file_type / f"sample_document.{extension}"
        )
        absolute_path = ROOT / relative_path
        source = SourceVersion(
            source=SourceRef(
                source_id=source_id,
                knowledge_space_id="integration-tests",
                source_type="document",
            ),
            version="v1",
        )
        parsed = parser.parse_file(absolute_path, source)
        cleaned = DocumentCleaner.clean_document(parsed)
        processed = PersianNormalizer.normalize_document(cleaned)

        data = processed.model_dump(mode="json")
        stable_path = relative_path.as_posix()
        data["metadata"]["source_file"] = stable_path
        for block in data["blocks"]:
            location = block["location"]
            if location is not None and location["file_path"] == str(absolute_path):
                location["file_path"] = stable_path

        output = outputs / f"sample_{file_type}_processed.json"
        output.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        artifacts.append(output)

        access = AccessMetadata(
            tenant_id="sample-tenant",
            acl_principals=["sample-review-principal"],
        )
        request = prepare_chunking_request(
            processed,
            access=access,
            configuration=configuration,
        )
        request_data = request.model_dump(mode="json")
        for item in request_data["items"]:
            location = item["location"]
            if location is not None and location["file_path"] == str(absolute_path):
                location["file_path"] = stable_path
        request_output = outputs / f"sample_{file_type}_chunking_request.json"
        request_output.write_text(
            json.dumps(request_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        artifacts.append(request_output)

        if tokenizer is not None:
            report = count_prepared_request(
                request, configuration=configuration, tokenizer=tokenizer
            )
            token_diagnostics.append(
                {
                    "source_id": source_id,
                    "artifact_type": "prepared_request_per_item_token_diagnostics",
                    "tokenizer": asdict(report.tokenizer),
                    "include_special_tokens": report.include_special_tokens,
                    "chunk_budget": report.chunk_budget,
                    "items": [asdict(item) for item in report.items],
                }
            )

    if include_token_counts:
        diagnostics_output = outputs / "sample_chunking_token_counts.json"
        diagnostics_output.write_text(
            json.dumps(token_diagnostics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        artifacts.append(diagnostics_output)
    return artifacts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-token-counts",
        action="store_true",
        help="count prepared items with the configured tokenizer (may download artifacts)",
    )
    args = parser.parse_args()
    for artifact in export_samples(include_token_counts=args.with_token_counts):
        print(artifact.relative_to(ROOT).as_posix())
