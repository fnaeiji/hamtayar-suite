from enum import Enum

from pydantic import Field

from .access import AccessMetadata
from .common import ContractModel, ContentRef, SourceVersion
from .errors import ErrorDetail


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionRequest(ContractModel):
    source: SourceVersion
    content: ContentRef
    access: AccessMetadata
    idempotency_key: str = Field(min_length=1)
    processing_profile: str = "default"
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestionResponse(ContractModel):
    job_id: str
    status: JobState = JobState.PENDING


class JobStatus(ContractModel):
    job_id: str
    status: JobState
    error: ErrorDetail | None = None