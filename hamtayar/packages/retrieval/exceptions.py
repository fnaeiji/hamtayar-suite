"""Package-local, typed retrieval failures (T009).

Contracts keep the shared vocabulary only (`ErrorCode`); the operational error types live with the
layer that raises them, mirroring `packages/storage/exceptions.py`. No shared contract is modified and
no HTTP mapping happens here — that belongs to the application layer.

Three types only, because there are three genuinely different situations:

* `SearchValidationError` — the caller's search input is invalid (vector, limit, query text).
* `SearchScopeRequiredError` — the trusted access scope is missing or unusable → fail closed.
* `SearchMappingError` — the engine answered, but a stored record cannot be mapped to the contract.
"""

from packages.contracts.errors import ErrorCode

__all__ = [
    "SearchEngineError",
    "SearchError",
    "SearchMappingError",
    "SearchScopeRequiredError",
    "SearchValidationError",
]


class SearchError(Exception):
    """Base class: a message plus the shared error code the application layer maps to HTTP."""

    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)


class SearchValidationError(SearchError):
    """Invalid search input (empty/oversized vector, wrong dimension, invalid limit, empty query)."""

    error_code = ErrorCode.VALIDATION_ERROR


class SearchScopeRequiredError(SearchError):
    """No usable trusted access scope was supplied: the search is refused (fail closed)."""

    error_code = ErrorCode.ACCESS_DENIED


class SearchMappingError(SearchError):
    """A retrieved record could not be mapped onto the shared retrieval contracts."""

    error_code = ErrorCode.PROCESSING_FAILED


class SearchEngineError(SearchError):
    """The engine could not answer (timeout, unavailable, or a rejected query).

    Raised when a storage-level engine failure would otherwise leak an internal type to callers.
    """

    error_code = ErrorCode.STORAGE_ERROR
