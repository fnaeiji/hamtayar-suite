"""Small graph-state updates only; no document processing or external I/O."""

from typing import Any

from packages.contracts.access import AccessMetadata
from packages.contracts.common import ContentRef
from packages.contracts.document_ingestion import ArtifactOutcome, ChunkArtifactOutcome

from ..state import DocumentIngestionState, Stage


def trusted_access(runtime: Any) -> AccessMetadata | None:
    context = getattr(runtime, "context", None)
    if not isinstance(context, dict):
        return None
    access = context.get("access")
    return access if isinstance(access, AccessMetadata) else None


def denied(step: Stage) -> dict[str, Any]:
    return {
        "status": "failed",
        "error_code": "access_denied",
        "error_step": step,
        "last_step": step,
    }


def artifact_update(step: Stage, result: ArtifactOutcome, field: str) -> dict[str, Any]:
    if not isinstance(result, ArtifactOutcome):
        raise TypeError(f"{step} returned the wrong package contract")
    if result.error is not None:
        return {
            "status": "failed",
            "error_code": result.error.code.value,
            "error_step": step,
            "last_step": step,
            "retryable": result.error.retryable,
        }
    assert result.ref is not None
    if (
        not result.ref.uri
        or len(result.ref.uri) > 4096
        or result.ref.uri.startswith("data:")
    ):
        return {
            "status": "failed",
            "error_code": "validation_error",
            "error_step": step,
            "last_step": step,
        }
    updates: dict[str, Any] = {
        "status": "running",
        "last_step": step,
        field: result.ref.uri,
    }
    if step == "chunk":
        if not isinstance(result, ChunkArtifactOutcome):
            raise TypeError("chunk returned the wrong package contract")
        if result.count == 0:
            return {
                "status": "failed",
                "error_code": "validation_error",
                "error_step": step,
                "last_step": step,
            }
        updates["chunk_count"] = result.count
    return updates


def ref_from_state(state: DocumentIngestionState, key: str) -> ContentRef:
    ref = state.get(key)
    if (
        not isinstance(ref, str)
        or not ref
        or len(ref) > 4096
        or ref.startswith("data:")
    ):
        raise ValueError(f"Missing {key} in document workflow state")
    return ContentRef(uri=ref)
