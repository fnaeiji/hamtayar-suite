"""Application-level translation of storage failures into the shared error contract.

`packages/storage` owns the operational failures; the application owns turning them into the
application-facing `ErrorDetail` (`packages/contracts/errors.py`). Nothing here knows about Qdrant:
the adapter errors never leave `packages/storage`.

Kept out of `apps/core/exceptions.py` on purpose: that module is owned by the HTTP/API layer
(MCPJSOFT11-79) and must stay byte-identical to its committed version.
"""

from __future__ import annotations

from packages.contracts.errors import ErrorDetail
from packages.storage.service import (
    ChunkValidationError,
    CollectionMismatchError,
    ReadBackMismatchError,
    StoreTimeoutError,
    StoreWriteError,
)

#: The public storage failures an application boundary may catch. Everything else is a programming
#: error and must propagate untouched.
STORAGE_ERROR_TYPES = (
    ChunkValidationError,
    CollectionMismatchError,
    StoreWriteError,
    StoreTimeoutError,
    ReadBackMismatchError,
)

_MAX_FAILURES_IN_MESSAGE = 3
_MAX_MESSAGE_LENGTH = 500


def to_error_detail(exc: Exception) -> ErrorDetail:
    """Map a storage failure onto the shared `ErrorDetail` without losing its diagnostics.

    `code` and `retryable` come from the exception itself (operation-level retry verdict); the
    bounded `message` carries the counts plus the first few per-point reasons. The complete
    `StoreResult` stays available on the exception for callers that need full detail.
    """
    result = getattr(exc, "result", None)
    code = getattr(exc, "error_code")
    retryable = bool(getattr(exc, "retryable"))

    parts = [f"{type(exc).__name__}: {exc}"]
    if result is not None:
        parts.append(f"requested={result.requested} stored={result.stored} failed={result.failed}")
        examples = []
        for failure in result.failures[:_MAX_FAILURES_IN_MESSAGE]:
            identity = failure.chunk_id or failure.point_id
            examples.append(f"{identity}: {failure.reason}")
        if examples:
            parts.append("causes: " + "; ".join(examples))

    message = " | ".join(parts)
    if len(message) > _MAX_MESSAGE_LENGTH:
        message = message[: _MAX_MESSAGE_LENGTH - 3] + "..."
    return ErrorDetail(code=code, message=message, retryable=retryable)
