"""Storage-specific Python exceptions.

`packages/contracts/errors.py` owns the shared error vocabulary (`ErrorCode`) and the
application-facing error data (`ErrorDetail`). This module owns the Python exceptions the storage
layer raises: operational outcomes (validation, collection mismatch, write, timeout, read-back).

Each exception carries the operation's `StoreResult` detail and an `ErrorCode` from the shared
vocabulary, so the application boundary can build `ErrorDetail(code, message, retryable)` without
touching Contracts.

Retryability is operation-level and derived from the real classification of the failures that
actually reached the target (categories `write` and `timeout`): unattempted points and non-target
failures never make an operation retryable, and a mixture containing a permanent failure is not
retryable.
"""

from packages.contracts.errors import ErrorCode
from packages.contracts.storage import FailureCategory, StoreResult

_TARGET_FAILURE_CATEGORIES = frozenset({FailureCategory.WRITE, FailureCategory.TIMEOUT})


class _StorageError(Exception):
    """Base class: message, the operation's failure detail, and an operation-level retry verdict."""

    error_code: ErrorCode = ErrorCode.STORAGE_ERROR

    def __init__(self, message: str, *, result: StoreResult) -> None:
        super().__init__(message)
        self.result = result

    @property
    def retryable(self) -> bool:
        """True only when every failure attributable to the target was classified transient.

        `any(failure.retryable)` would be wrong for a partial write: the unattempted points are
        normal failures with `retryable=False`, and one permanent point in a batch means a retry
        cannot succeed.
        """
        attempted = [
            failure
            for failure in self.result.failures
            if failure.category in _TARGET_FAILURE_CATEGORIES
        ]
        return bool(attempted) and all(failure.retryable for failure in attempted)


class ChunkValidationError(_StorageError):
    """Chunks and embeddings could not be reconciled, or a contract field was invalid."""

    error_code = ErrorCode.VALIDATION_ERROR


class CollectionMismatchError(_StorageError):
    """The target collection profile does not match the configured profile."""


class StoreWriteError(_StorageError):
    """A write failed permanently or exhausted its retries."""


class StoreTimeoutError(_StorageError):
    """The target was unavailable or timed out."""


class ReadBackMismatchError(_StorageError):
    """Stored data is missing, unreadable, or does not match what was submitted."""


__all__ = [
    "ChunkValidationError",
    "CollectionMismatchError",
    "ReadBackMismatchError",
    "StoreTimeoutError",
    "StoreWriteError",
]
