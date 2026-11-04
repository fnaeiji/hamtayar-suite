"""Plain, SDK-free data types for the storage search surface.

Retrieval builds a `SearchFilter` and calls one of the four public search functions in
`packages/storage/service.py`; the engine adapter turns these plain values into native queries.
Nothing here imports the Qdrant SDK — the architecture test requires the SDK to stay inside
`packages/storage/qdrant/adapter.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

__all__ = ["SearchFilter", "SearchHit", "SearchMode", "SearchQuery"]


class SearchMode(str, Enum):
    """Which lexical behaviour to execute. Semantic search has its own entry point."""

    FILTER = "filter"  # unranked full-text match (no score)
    PHRASE = "phrase"  # order-sensitive full-text match
    BM25 = "bm25"  # native BM25 relevance ranking (real scores)


@dataclass(frozen=True)
class SearchFilter:
    """Authorized search boundary: tenant and principals are mandatory, the rest narrow it."""

    tenant_id: str
    principals: tuple[str, ...]
    source_ids: tuple[str, ...] | None = None
    generation_ids: tuple[str, ...] | None = None


@dataclass(frozen=True)
class SearchQuery:
    """One engine query. `vector` is used for semantic search, `text` for the lexical modes."""

    mode: SearchMode | None
    limit: int
    vector: Sequence[float] | None = None
    text: str | None = None


@dataclass(frozen=True)
class SearchHit:
    """One retrieved chunk. `score` is None for unranked full-text filtering."""

    point_id: UUID
    chunk_id: str | None
    text: str | None
    source_id: str | None
    version: str | None
    generation_id: str | None
    knowledge_space_id: str | None
    source_type: str | None
    kind: str | None
    location: dict[str, Any] | None
    score: float | None
