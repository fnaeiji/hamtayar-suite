
from typing import Literal

from pydantic import Field

from .access import AccessScope
from .common import ContractModel, SourceLocation, SourceVersion


SearchMode = Literal["keyword", "semantic", "hybrid", "code"]


class SearchRequest(ContractModel):
    """Public request for searching organizational knowledge."""

    query: str = Field(min_length=1)
    mode: SearchMode = "hybrid"
    top_k: int = Field(default=10, ge=1, le=100)
    source_ids: list[str] | None = None


class RetrievalQuery(ContractModel):
    """Internal search request with authorized scope."""

    request: SearchRequest
    scope: AccessScope
    generation_ids: list[str] = Field(min_length=1)


class SearchResult(ContractModel):
    """A single piece of retrieved evidence."""

    evidence_id: str
    source: SourceVersion
    generation_id: str
    retrieval_method: SearchMode
    text: str | None = None
    location: SourceLocation | None = None
    score: float | None = None


class RetrievalResponse(ContractModel):
    """Standard response returned by the retrieval module."""

    results: list[SearchResult] = Field(default_factory=list)
    partial: bool = False
    warnings: list[str] = Field(default_factory=list)
