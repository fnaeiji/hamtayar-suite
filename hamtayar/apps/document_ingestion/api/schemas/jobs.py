"""Typed HTTP and executor-facing schemas for synchronous Document Ingestion MVP.

The request's form fields are untrusted metadata. Access grants and ACLs must
come from a future trusted authorization dependency, never these form values.
"""
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.contracts.document import DocumentInput


class DocumentUploadRequest(BaseModel):
    """Metadata sent as form fields alongside a multipart file."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    knowledge_space_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    version: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    processing_profile: str = Field(default="default", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class DocumentExecutionRequest:
    """Private, staged input for the Graph adapter. Never sent to API callers."""

    document: DocumentInput
    filename: str
    content_type: str
    size_bytes: int
    processing_profile: str

    @property
    def local_file_ref(self) -> str:
        """URI to a controlled, request-scoped staging file."""
        return self.document.content.uri


@dataclass(frozen=True)
class DocumentExecutionResult:
    """A fully completed (not merely queued) ingestion result."""

    chunks_indexed: int | None = None


class DocumentUploadResponse(BaseModel):
    """HTTP 200 means that execution completed before the response was sent."""

    status: Literal["completed"] = "completed"
    source_id: str
    version: str
    chunks_indexed: int | None = Field(default=None, ge=0)
    request_id: str | None = None
