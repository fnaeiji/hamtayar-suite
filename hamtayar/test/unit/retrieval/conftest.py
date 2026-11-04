"""Fake storage-search seam for retrieval unit tests (no Qdrant involvement).

Retrieval unit tests must never need the engine: they install a fake that records the query it was
given and returns prepared `SearchHit` objects (or raises a prepared error).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from packages.storage.service import SearchHit


def a_hit(
    chunk_id: str = "c1", *, score: float | None = 0.5, **overrides: Any
) -> SearchHit:
    payload = {
        "point_id": uuid4(),
        "chunk_id": chunk_id,
        "text": f"text of {chunk_id}",
        "source_id": "doc-1",
        "version": "v1",
        "generation_id": "gen-1",
        "knowledge_space_id": "ks-1",
        "source_type": "document",
        "kind": "document",
        "location": None,
        "score": score,
    }
    payload.update(overrides)
    return SearchHit(**payload)


@dataclass
class FakeStorageSearch:
    """Stands in for the four storage search functions; records every call."""

    hits: tuple[SearchHit, ...] = ()
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def _record(self, operation: str, **kwargs: Any) -> tuple[SearchHit, ...]:
        self.calls.append({"operation": operation, **kwargs})
        if self.error is not None:
            raise self.error
        return self.hits

    def search_semantic(self, query_vector, *, search_filter, limit, config):
        return self._record(
            "semantic",
            query_vector=list(query_vector),
            search_filter=search_filter,
            limit=limit,
            config=config,
        )

    def search_lexical_filter(self, query_text, *, search_filter, limit, config):
        return self._record(
            "filter",
            query_text=query_text,
            search_filter=search_filter,
            limit=limit,
            config=config,
        )

    def search_lexical_phrase(self, phrase, *, search_filter, limit, config):
        return self._record(
            "phrase",
            phrase=phrase,
            search_filter=search_filter,
            limit=limit,
            config=config,
        )

    def search_lexical_bm25(self, query_text, *, search_filter, limit, config):
        return self._record(
            "bm25",
            query_text=query_text,
            search_filter=search_filter,
            limit=limit,
            config=config,
        )


@pytest.fixture
def storage_search_seam() -> FakeStorageSearch:
    """Install-free fake: pass it to the code under test, or patch a module attribute with it."""
    return FakeStorageSearch()


@pytest.fixture
def install_search_seam(monkeypatch):
    """Patch a module's storage-search attributes with a fake (used by retrieval tests).

    Only names the target module actually defines are patched, so the same fixture works for the
    semantic module (which aliases storage as `search_storage_semantic`) and for the later lexical
    modules.
    """

    def install(module: Any, fake: FakeStorageSearch) -> FakeStorageSearch:
        """Patch only the module's *storage* aliases, never the retrieval functions themselves."""
        patched = []
        for name in dir(module):
            if not name.startswith("search_storage_"):
                continue
            fake_method = getattr(
                fake, f"search_{name.removeprefix('search_storage_')}", None
            )
            if fake_method is not None:
                monkeypatch.setattr(module, name, fake_method)
                patched.append(name)
        assert patched, f"{module.__name__} exposes no search_storage_* alias to fake"
        return fake

    return install
