"""Serializable references in checkpoints; trusted access is supplied at runtime."""

from typing import Literal, TypedDict

from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceVersion

Stage = Literal[
    "load_document", "parse", "normalize", "chunk", "embed", "index", "activate"
]
STAGES: tuple[Stage, ...] = (
    "load_document",
    "parse",
    "normalize",
    "chunk",
    "embed",
    "index",
    "activate",
)


class IngestionRuntimeContext(TypedDict):
    access: AccessMetadata


class DocumentIngestionState(TypedDict, total=False):
    _context_fingerprint: str
    source: dict
    content_ref: str
    filename: str
    content_type: str
    processing_profile: str
    loaded_ref: str
    parsed_ref: str
    normalized_ref: str
    chunks_ref: str
    embeddings_ref: str
    chunk_count: int
    indexed_count: int
    generation_id: str
    index_validated: bool
    published: bool
    status: str
    last_step: Stage
    error_code: str
    error_step: Stage
    retryable: bool


def source_from_state(state: DocumentIngestionState) -> SourceVersion:
    return SourceVersion.model_validate(state["source"])


def initial_state(
    document, *, filename: str, content_type: str, profile: str = "default"
) -> DocumentIngestionState:
    return {
        "source": document.source.model_dump(mode="json"),
        "content_ref": document.content.uri,
        "filename": filename,
        "content_type": content_type,
        "processing_profile": profile,
        "status": "pending",
        "published": False,
        "index_validated": False,
    }
