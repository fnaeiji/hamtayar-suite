
from enum import Enum

from pydantic import Field

from .common import ContractModel


class ErrorCode(str, Enum):
    """Standard error codes used across Hamtayar."""

    VALIDATION_ERROR = "validation_error"
    ACCESS_DENIED = "access_denied"
    SOURCE_NOT_FOUND = "source_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    PROVIDER_ERROR = "provider_error"
    STORAGE_ERROR = "storage_error"
    PROCESSING_FAILED = "processing_failed"


class ErrorDetail(ContractModel):
    """Standard structure for reporting errors."""

    code: ErrorCode
    message: str = Field(min_length=1)
    retryable: bool = False
