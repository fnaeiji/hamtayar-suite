
"""Storage data contracts.

Indexing inputs and successful results are defined in indexing.py.
Payload construction, storage exceptions, retries, and Qdrant operations
belong to packages/storage.
"""

from enum import Enum
from uuid import UUID

from pydantic import Field, model_validator

from .common import ContractModel


class PayloadField:
    """Canonical names of stored payload fields."""

    CHUNK_ID = "chunk_id"
    GENERATION_ID = "generation_id"
    MODEL_ID = "model_id"
    SOURCE_ID = "source_id"
    VERSION = "version"
    KNOWLEDGE_SPACE_ID = "knowledge_space_id"
    SOURCE_TYPE = "source_type"
    KIND = "kind"
    TEXT = "text"
    LOCATION = "location"
    TENANT_ID = "tenant_id"
    ACL_PRINCIPALS = "acl_principals"
    SYMBOL_ID = "symbol_id"
    METADATA = "metadata"

    ALL = (
        CHUNK_ID,
        GENERATION_ID,
        MODEL_ID,
        SOURCE_ID,
        VERSION,
        KNOWLEDGE_SPACE_ID,
        SOURCE_TYPE,
        KIND,
        TEXT,
        LOCATION,
        TENANT_ID,
        ACL_PRINCIPALS,
        SYMBOL_ID,
        METADATA,
    )


class FailureCategory(str, Enum):
    """Reason a point was not verified as stored."""

    VALIDATION = "validation"
    MISMATCH = "mismatch"
    TIMEOUT = "timeout"
    WRITE = "write"
    READ_BACK = "read_back"
    UNATTEMPTED = "unattempted"


class StoreFailure(ContractModel):
    """Failure detail for one point."""

    point_id: UUID | None = None
    chunk_id: str | None = Field(default=None, min_length=1)
    category: FailureCategory
    reason: str = Field(min_length=1)
    retryable: bool = False

    @model_validator(mode="after")
    def validate_identity(self):
        if self.point_id is None and self.chunk_id is None:
            raise ValueError("point_id or chunk_id is required")
        return self


class StoreResult(ContractModel):
    """Point counts and failure details for a storage operation."""

    requested: int = Field(ge=0)
    stored: int = Field(ge=0)
    failed: int = Field(ge=0)
    failures: tuple[StoreFailure, ...] = ()

    @model_validator(mode="after")
    def validate_counts(self):
        if self.failed != len(self.failures):
            raise ValueError("failed must equal len(failures)")
        if self.requested != self.stored + self.failed:
            raise ValueError("requested must equal stored + failed")
        return self
