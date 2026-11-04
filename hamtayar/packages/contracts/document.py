from typing import Literal

from pydantic import Field, model_validator

from .common import (
    ContentRef,
    ContractModel,
    SourceLocation,
    SourceVersion,
)

DocumentBlockType = Literal["heading", "paragraph", "table", "code", "list", "quote"]


class DocumentInput(ContractModel):
    """Input contract for document processing."""

    source: SourceVersion
    content: ContentRef


class ProtectedSpan(ContractModel):
    """Protected range in the block's effective text.

    Offsets are zero-based Python Unicode code-point positions with an exclusive
    end. In processed documents they address ``normalized_text``; they are not
    original-source citation offsets (those are represented by ``location``).
    """

    start: int = Field(strict=True, ge=0)
    end: int = Field(strict=True, gt=0)
    kind: Literal[
        "inline_code",
        "code_payload",
        "link_destination",
        "url",
        "email",
        "path",
        "technical_expression",
        "technical_identifier",
        "list_marker",
    ]

    @model_validator(mode="after")
    def validate_span(self):
        if self.end <= self.start:
            raise ValueError("Protected span end must be greater than start")
        return self


class DocumentBlock(ContractModel):
    """Format-neutral source block and its processed view.

    ``text`` is extracted text. ``normalized_text`` is the cleaned/normalized
    text and, on processed documents, is always populated (even when empty).
    ``protected_spans`` address that processed text, or ``text`` before processing.
    ``location`` addresses the original decoded source, never transformed text.
    Block IDs are local to a source identity and version, not stable across versions.
    """

    block_type: DocumentBlockType
    text: str
    location: SourceLocation | None = None
    normalized_text: str | None = None
    block_id: str | None = Field(default=None, min_length=1)
    heading_level: int | None = Field(default=None, ge=1, le=6)
    code_language: str | None = None
    protected_spans: list[ProtectedSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_structure_and_spans(self):
        if self.heading_level is not None and self.block_type != "heading":
            raise ValueError("heading_level is only valid for heading blocks")
        if self.code_language is not None and self.block_type != "code":
            raise ValueError("code_language is only valid for code blocks")
        current_text = self.effective_text
        previous_end = 0
        for span in self.protected_spans:
            if span.end > len(current_text):
                raise ValueError("Protected span exceeds the current block text view")
            if span.start < previous_end:
                raise ValueError("Protected spans must be sorted and non-overlapping")
            previous_end = span.end
        return self

    @property
    def effective_text(self) -> str:
        """Text for downstream processing: normalized view if present, else source text."""
        return self.normalized_text if self.normalized_text is not None else self.text


class ParsedDocument(ContractModel):
    """Ordered format-neutral document.

    A block is identified by ``(source.source.source_id,
    source.source.knowledge_space_id, source.version, block_id)``. IDs are
    document-local; empty processed blocks remain for traceability and should be
    omitted by future chunkers without falling back to extracted ``text``.
    """

    source: SourceVersion
    blocks: list[DocumentBlock] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_block_ids(self):
        ids = [block.block_id for block in self.blocks if block.block_id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("block_id values must be unique within a document")
        return self
