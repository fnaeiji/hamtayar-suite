"""HTTP wire schemas and a private execution request for TASK-05.

Never accept a user-provided access scope, identity, evidence or citations.
Those fields must come from a trusted authentication/retrieval boundary.
"""
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.contracts.access import AccessScope, TrustedAccessContext
from packages.contracts.answering import Citation as DomainCitation
from packages.contracts.answering import AnswerResponse as DomainAnswerResponse
from packages.contracts.common import SourceLocation

MAX_QUESTION_LENGTH = 4096


class AnswerRequest(BaseModel):
    """Untrusted public API input; only the question is accepted."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description="Question for evidence-grounded answering (1–4096 characters)",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Question must contain printable content")
        return value


class CitationDTO(BaseModel):
    """Public evidence provenance, not the original retrieved text."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_id: str
    knowledge_space_id: str
    version: str
    location: SourceLocation | None = None

    @classmethod
    def from_contract(cls, citation: DomainCitation) -> "CitationDTO":
        return cls(
            evidence_id=citation.evidence_id,
            source_id=citation.source.source.source_id,
            knowledge_space_id=citation.source.source.knowledge_space_id,
            version=citation.source.version,
            location=citation.location,
        )


class AnswerResponse(BaseModel):
    """The HTTP response; request_id mirrors the X-Request-ID header."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "no_evidence"]
    answer: str
    citations: list[CitationDTO]
    request_id: str


@dataclass(frozen=True)
class AnswerExecutionRequest:
    """Trusted internal request passed to the graph executor adapter."""

    question: str
    auth_context: TrustedAccessContext
    access_scope: AccessScope
    request_id: str


# Documented explicit boundary between domain and HTTP response types.
GraphResult = DomainAnswerResponse
