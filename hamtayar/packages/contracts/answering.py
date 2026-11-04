
from typing import Literal

from pydantic import Field

from .common import ContractModel, SourceLocation, SourceVersion
from .retrieval import SearchResult


class AnswerRequest(ContractModel):
    """Input contract for generating an answer."""

    question: str = Field(min_length=1)
    evidence: list[SearchResult] = Field(default_factory=list)


class Citation(ContractModel):
    """Reference to evidence used in an answer."""

    evidence_id: str = Field(min_length=1)
    source: SourceVersion
    location: SourceLocation | None = None


class AnswerResponse(ContractModel):
    """Standard response of the answering module."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    status: Literal["completed", "no_evidence", "failed"]
