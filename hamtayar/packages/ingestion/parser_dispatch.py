"""Reuse installed parsers without embedding parsing logic in graph nodes."""

import asyncio
from pathlib import Path
from typing import Protocol

from packages.contracts.artifacts import ArtifactRepository
from packages.contracts.common import ContentRef, SourceVersion
from packages.contracts.document import ParsedDocument
from packages.contracts.document_ingestion import ArtifactOutcome
from packages.contracts.errors import ErrorCode, ErrorDetail


class BinaryDocumentParser(Protocol):
    async def parse(
        self, *, file: Path, source: SourceVersion, filename: str
    ) -> ParsedDocument: ...


class DocumentParserDispatcher:
    def __init__(
        self,
        *,
        artifacts: ArtifactRepository,
        binary_parsers: dict[str, BinaryDocumentParser] | None = None,
    ) -> None:
        self.artifacts = artifacts
        # No PDF/DOCX parser is assumed; explicit adapter registration is required.
        self.binary_parsers = dict(binary_parsers or {})

    async def parse(
        self,
        *,
        source: SourceVersion,
        loaded: ContentRef,
        filename: str,
        content_type: str,
    ) -> ArtifactOutcome:
        extension = Path(filename).suffix.lower()
        mime = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        if content_type == "application/octet-stream" or (
            extension == ".md" and content_type == "text/plain"
        ):
            content_type = mime.get(extension, "")
        if not content_type or mime.get(extension) != content_type:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.UNSUPPORTED_FORMAT,
                    message="Unsupported or mismatched file type",
                )
            )
        if extension in {".pdf", ".docx"} and extension not in self.binary_parsers:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.UNSUPPORTED_FORMAT,
                    message="No parser configured for this file type",
                )
            )
        try:
            async with self.artifacts.materialize_raw(ref=loaded, source=source) as raw:
                if extension in (".txt", ".md"):
                    # Work with the original filename for source provenance, not
                    # the internal content-addressed storage filename.
                    text = await asyncio.to_thread(raw.read_text, encoding="utf-8")
                    if extension == ".txt":
                        from packages.ingestion.txt.parser import TxtParser

                        result = await asyncio.to_thread(
                            TxtParser.parse_content, text, source, file_path=filename
                        )
                    else:
                        from packages.ingestion.markdown.parser import MarkdownParser

                        result = await asyncio.to_thread(
                            MarkdownParser.parse_content,
                            text,
                            source,
                            file_path=filename,
                        )
                else:
                    result = await self.binary_parsers[extension].parse(
                        file=raw, source=source, filename=filename
                    )
            if not isinstance(result, ParsedDocument) or result.source != source:
                raise ValueError("Parser returned a source mismatch")
            reference = await self.artifacts.put_parsed(
                source=source, document=result, stage="parsed"
            )
        except (UnicodeError, ValueError):
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Malformed document content",
                )
            )
        except FileNotFoundError:
            return ArtifactOutcome(
                error=ErrorDetail(
                    code=ErrorCode.SOURCE_NOT_FOUND, message="Raw document unavailable"
                )
            )
        return ArtifactOutcome(ref=reference)
