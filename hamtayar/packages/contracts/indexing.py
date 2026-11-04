
from pydantic import Field

from .chunks import Chunk
from .common import ContractModel, SourceVersion


class EmbeddingRecord(ContractModel):
    """Embedding vector associated with a chunk."""

    chunk_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    vector: list[float] = Field(min_length=1)


class IndexingRequest(ContractModel):
    """Input contract for building an index generation."""

    source: SourceVersion
    generation_id: str = Field(min_length=1)
    chunks: list[Chunk]
    embeddings: list[EmbeddingRecord] = Field(default_factory=list)


class IndexingResult(ContractModel):
    """Result of an indexing operation."""

    generation_id: str
    indexed_count: int = Field(ge=0)
    validated: bool = False


class PublicationRequest(ContractModel):
    """Request to publish an index generation."""

    source: SourceVersion
    generation_id: str = Field(min_length=1)


class PublicationResult(ContractModel):
    """Result of an index publication operation."""

    generation_id: str
    published: bool
