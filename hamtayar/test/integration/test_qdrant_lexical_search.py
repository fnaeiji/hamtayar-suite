"""T020: lexical filtering and phrase search against a real, disposable Qdrant collection.

Reuses the shared search fixtures: a uniquely named `hamtayar_search_<hex>` collection, provisioned
with the text index (phrase matching + BM25 scoring) and deleted by the fixture.
"""

from __future__ import annotations

import pytest

from packages.contracts.access import AccessMetadata, AccessScope
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest
from packages.documents.normalization.service import PersianNormalizer
from packages.retrieval.exceptions import SearchEngineError, SearchValidationError
from packages.retrieval.search import search_lexical_filter, search_lexical_phrase
from packages.storage.qdrant.config import StorageConfig
from packages.storage.service import store_chunks
from test.integration.search_fixtures import (  # noqa: F401 - imported so pytest registers them
    search_collection,
    search_config,
    search_point_count,
    search_url,
)

VECTOR = [0.1, 0.2, 0.3, 0.4]
NORMALIZER = PersianNormalizer()

# chunk_id -> (text, tenant, principals, source_id, generation_id)
DOCS = {
    "en1": ("semantic search engine", "tenant-A", ["finance"], "doc-1", "gen-1"),
    "en2": ("search search search vector", "tenant-A", ["finance"], "doc-1", "gen-1"),
    "en3": ("cooking recipes", "tenant-A", ["finance"], "doc-1", "gen-1"),
    "fa1": ("جستجوی معنایی جستجوی برداری", "tenant-A", ["finance"], "doc-2", "gen-1"),
    "fa2-arabic": (
        "جستجوي معنايي در پايگاه داده",
        "tenant-A",
        ["finance"],
        "doc-3",
        "gen-1",
    ),
    "zwnj": ("می\u200cتوان جستجو", "tenant-A", ["finance"], "doc-4", "gen-1"),
    "space": ("می توان تست", "tenant-A", ["finance"], "doc-5", "gen-1"),
    "mixed": (
        "Hamtayar همتایار semantic search جستجو",
        "tenant-A",
        ["finance"],
        "doc-6",
        "gen-1",
    ),
    "other-tenant": (
        "semantic search engine",
        "tenant-B",
        ["finance"],
        "doc-7",
        "gen-1",
    ),
    "other-acl": (
        "semantic search engine",
        "tenant-A",
        ["engineering"],
        "doc-8",
        "gen-1",
    ),
    "other-gen": ("semantic search engine", "tenant-A", ["finance"], "doc-9", "gen-2"),
}

SCOPE = AccessScope(tenant_id="tenant-A", principals=["finance"])


def _source(source_id: str) -> SourceVersion:
    return SourceVersion(
        source=SourceRef(
            source_id=source_id, knowledge_space_id="ks-1", source_type="document"
        ),
        version="v1",
    )


@pytest.fixture
def seeded(search_config: StorageConfig):  # noqa: F811 - intentional fixture dependency shadow
    """Seed through the real storage write path, one request per generation."""
    chunks = {
        chunk_id: Chunk(
            chunk_id=chunk_id,
            source=_source(source_id),
            kind="document",
            text=text,
            access=AccessMetadata(tenant_id=tenant, acl_principals=principals),
        )
        for chunk_id, (text, tenant, principals, source_id, _generation) in DOCS.items()
    }
    embeddings = {
        chunk_id: EmbeddingRecord(chunk_id=chunk_id, model_id="embed-4d", vector=VECTOR)
        for chunk_id in DOCS
    }
    for generation_id in ("gen-1", "gen-2"):
        family = [cid for cid, doc in DOCS.items() if doc[4] == generation_id]
        request = IndexingRequest(
            source=_source(DOCS[family[0]][3]),
            generation_id=generation_id,
            chunks=[chunks[cid] for cid in family],
            embeddings=[embeddings[cid] for cid in family],
        )
        assert store_chunks(request, config=search_config).validated is True
    return search_config


def _ids(response) -> list[str]:
    return [result.evidence_id for result in response.results]


def _filter(config, text, scope=SCOPE, **kwargs):
    return search_lexical_filter(
        text, scope=scope, config=config, normalizer=NORMALIZER, **kwargs
    )


def _phrase(config, text, scope=SCOPE, **kwargs):
    return search_lexical_phrase(
        text, scope=scope, config=config, normalizer=NORMALIZER, **kwargs
    )


# ---- lexical matching


def test_single_word_match(seeded):
    response = _filter(seeded, "vector")

    assert _ids(response) == ["en2"]
    assert response.results[0].score is None, (
        "unranked filtering must not fabricate a score"
    )
    assert response.results[0].retrieval_method == "keyword"


def test_multi_word_filter_requires_every_token(seeded):
    """Measured behaviour (Qdrant 1.20.0): `MatchText` in a filter is AND over the query tokens,
    unlike `TextQuery` (BM25), which is OR-like. This asymmetry is asserted, not assumed."""
    both = set(_ids(_filter(seeded, "semantic search")))
    assert {"en1", "mixed"} <= both

    assert _filter(seeded, "semantic cooking").results == [], (
        "AND semantics: mixed terms match nothing"
    )


def test_no_match_returns_empty(seeded):
    assert _filter(seeded, "zzz-absent-term").results == []


def test_limit_is_respected(seeded):
    response = _filter(seeded, "search", limit=1)

    assert len(response.results) == 1


# ---- phrase behaviour


def test_phrase_matches_only_in_order(seeded):
    ids = set(_ids(_phrase(seeded, "semantic search")))

    assert {"en1", "mixed"} <= ids
    assert (
        "en2" not in ids
    )  # contains "search" and "semantic" but not in this order/adjacency


def test_reversed_phrase_matches_nothing(seeded):
    assert _phrase(seeded, "search semantic").results == []


# ---- Persian normalisation


def test_persian_query_is_normalized_before_search(seeded):
    persian = set(_ids(_filter(seeded, "جستجوی")))
    arabic = set(_ids(_filter(seeded, "جستجوي")))

    assert persian == arabic, (
        "the injected normalizer must fold Arabic yeh into Persian yeh"
    )
    assert "fa1" in persian


def test_arabic_yeh_document_is_not_reachable_without_normalized_storage(seeded):
    """Documents must be stored normalized; the index does not fold variants (documented gap)."""
    assert "fa2-arabic" not in set(_ids(_filter(seeded, "جستجوی")))


def test_zwnj_and_space_are_equivalent_at_token_level(seeded):
    space_query = set(_ids(_filter(seeded, "می توان")))
    zwnj_query = set(_ids(_filter(seeded, "می\u200cتوان")))

    assert space_query == zwnj_query
    assert {"zwnj", "space"} <= space_query


def test_mixed_persian_english_query(seeded):
    ids = set(_ids(_filter(seeded, "search جستجو")))

    assert "mixed" in ids


# ---- access restrictions


def test_tenant_isolation(seeded):
    other = AccessScope(tenant_id="tenant-B", principals=["finance"])

    assert _ids(_filter(seeded, "semantic", scope=other)) == ["other-tenant"]


def test_acl_isolation(seeded):
    other = AccessScope(tenant_id="tenant-A", principals=["engineering"])

    assert set(_ids(_filter(seeded, "semantic", scope=other))) == {"other-acl"}


def test_source_restriction_narrows_results(seeded):
    ids = set(_ids(_filter(seeded, "search", requested_source_ids=["doc-1"])))

    assert ids == {"en1", "en2"}


def test_generation_filter_restricts_results(seeded):
    ids = set(_ids(_filter(seeded, "semantic", generation_ids=["gen-2"])))

    assert ids == {"other-gen"}


def test_empty_source_intersection_returns_empty_without_engine_call():
    """A deny must short-circuit: the unreachable URL proves no query is attempted."""
    unreachable = StorageConfig(
        url="http://127.0.0.1:6399",
        collection_name="no_such",
        max_retries=0,
        timeout_seconds=1,
    )
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1"]
    )

    response = search_lexical_filter(
        "search",
        scope=scope,
        config=unreachable,
        normalizer=NORMALIZER,
        requested_source_ids=["doc-9"],
    )

    assert response.results == []


# ---- validation and engine failures


@pytest.mark.parametrize("query", ["", "   "])
def test_blank_query_is_rejected(seeded, query):
    with pytest.raises(SearchValidationError):
        _filter(seeded, query)


def test_missing_scope_fails_closed(seeded):
    from packages.retrieval.exceptions import SearchScopeRequiredError

    with pytest.raises(SearchScopeRequiredError):
        search_lexical_filter(
            "search", scope=None, config=seeded, normalizer=NORMALIZER
        )


def test_unreachable_engine_raises_explicitly():
    unreachable = StorageConfig(
        url="http://127.0.0.1:6399",
        collection_name="no_such",
        max_retries=0,
        timeout_seconds=1,
    )

    with pytest.raises(SearchEngineError):
        search_lexical_filter(
            "search", scope=SCOPE, config=unreachable, normalizer=NORMALIZER
        )


def test_rejected_rest_phrase_response_is_an_engine_error(search_config):  # noqa: F811 - fixture dependency
    """The phrase path is REST: a 404 collection must surface as a typed failure, not an empty list."""
    missing = StorageConfig(
        url=search_config.url,
        collection_name="hamtayar_search_does_not_exist",
        max_retries=0,
        timeout_seconds=5,
    )

    with pytest.raises(SearchEngineError):
        search_lexical_phrase(
            "semantic search", scope=SCOPE, config=missing, normalizer=NORMALIZER
        )
