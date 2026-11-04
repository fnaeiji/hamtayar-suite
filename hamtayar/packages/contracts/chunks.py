from typing import Literal

from pydantic import Field, model_validator

from .access import AccessMetadata
from .common import ContractModel, SourceLocation, SourceVersion
from .document import DocumentBlockType, ProtectedSpan

ContentKind = Literal["document", "code"]


class ChunkingItem(ContractModel):
    """A content unit prepared for chunking."""

    text: str
    location: SourceLocation | None = None
    symbol_id: str | None = None
    block_id: str | None = Field(default=None, min_length=1)
    block_type: DocumentBlockType | None = None
    heading_level: int | None = Field(default=None, ge=1, le=6)
    code_language: str | None = None
    protected_spans: list[ProtectedSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_document_structure(self):
        if self.heading_level is not None and self.block_type != "heading":
            raise ValueError("heading_level is only valid for heading blocks")
        if self.code_language is not None and self.block_type != "code":
            raise ValueError("code_language is only valid for code blocks")
        previous_end = 0
        for span in self.protected_spans:
            if span.end > len(self.text):
                raise ValueError("Protected span exceeds the chunking item text")
            if span.start < previous_end:
                raise ValueError("Protected spans must be sorted and non-overlapping")
            previous_end = span.end
        return self


class ChunkingRequest(ContractModel):
    """Input contract for the chunking process."""

    source: SourceVersion
    kind: ContentKind
    items: list[ChunkingItem]
    access: AccessMetadata
    processing_profile: str = "default"

    @model_validator(mode="after")
    def validate_unique_document_block_ids(self):
        if self.kind == "document":
            ids = [item.block_id for item in self.items if item.block_id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError(
                    "block_id values must be unique within a document request"
                )
        return self


class Chunk(ContractModel):
    """A retrievable unit of document or code content."""

    chunk_id: str = Field(min_length=1)
    source: SourceVersion
    kind: ContentKind
    text: str = Field(min_length=1)
    access: AccessMetadata
    location: SourceLocation | None = None
    symbol_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ChunkingResult(ContractModel):
    """Standard output of the chunking process."""

    chunks: list[Chunk] = Field(default_factory=list)
