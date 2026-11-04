"""T015: semantic search against a real, disposable Qdrant collection.

Isolation: the `search_collection` fixture (test/integration/search_fixtures.py) creates a uniquely
named `hamtayar_search_<hex>` collection, provisions the search indexes, seeds it through the existing
`store_chunks`, and deletes it afterwards. Shared and production collections are never touched.
"""

from __future__ import annotations

import statistics
import time

import pytest

from packages.contracts.access import AccessMetadata, AccessScope
from packages.contracts.chunks import Chunk
from packages.contracts.common import SourceLocation, SourceRef, SourceVersion
from packages.contracts.indexing import EmbeddingRecord, IndexingRequest
from packages.documents.normalization.service import PersianNormalizer
from packages.retrieval.exceptions import (
    SearchEngineError,
    SearchScopeRequiredError,
    SearchValidationError,
)
from packages.retrieval.search import (
    search_lexical_bm25,
    search_lexical_filter,
    search_lexical_phrase,
    search_semantic,
)
from packages.storage.qdrant.config import StorageConfig
from packages.storage.service import store_chunks
from test.integration.search_fixtures import (  # noqa: F401 - imported so pytest registers them
    point_id_for_chunk,
    search_collection,
    search_config,
    search_point_count,
    search_url,
)

GENERATION = "gen-1"

# Distinct vectors so ranking is unambiguous (cosine distance to the query below).
#   q = [1, 0, 0, 0]
#   near = [1, 0, 0, 0]        -> identical      (score 1.0)
#   mid  = [1, 1, 0, 0]        -> 45 degrees     (~0.7071)
#   far  = [0, 1, 0, 0]        -> orthogonal     (0.0)
QUERY = [1.0, 0.0, 0.0, 0.0]
VECTORS = {
    "near": [1.0, 0.0, 0.0, 0.0],
    "mid": [1.0, 1.0, 0.0, 0.0],
    "far": [0.0, 1.0, 0.0, 0.0],
}

# chunk_id -> (vector key, tenant, principals, source_id, generation_id)
DOCS = {
    "near": ("near", "tenant-A", ["finance"], "doc-1", GENERATION),
    "mid": ("mid", "tenant-A", ["finance"], "doc-1", GENERATION),
    "far": ("far", "tenant-A", ["finance"], "doc-1", GENERATION),
    "other-tenant": ("near", "tenant-B", ["finance"], "doc-2", GENERATION),
    "other-acl": ("near", "tenant-A", ["engineering"], "doc-3", GENERATION),
    "other-generation": ("near", "tenant-A", ["finance"], "doc-4", "gen-2"),
    "other-source": ("mid", "tenant-A", ["finance"], "doc-5", GENERATION),
}


def _source(source_id: str) -> SourceVersion:
    return SourceVersion(
        source=SourceRef(
            source_id=source_id, knowledge_space_id="ks-1", source_type="document"
        ),
        version="v1",
    )


@pytest.fixture
def seeded(search_config: StorageConfig):  # noqa: F811 - intentional fixture dependency shadow
    """Seed the disposable collection through the existing storage write path."""
    chunks, embeddings = [], []
    for chunk_id, (
        vector_key,
        tenant,
        principals,
        source_id,
        generation_id,
    ) in DOCS.items():
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                source=_source(source_id),
                kind="document",
                text=f"متن {chunk_id} English text",
                access=AccessMetadata(tenant_id=tenant, acl_principals=principals),
                location=SourceLocation(page=1),
            )
        )
        embeddings.append(
            EmbeddingRecord(
                chunk_id=chunk_id, model_id="embed-4d", vector=VECTORS[vector_key]
            )
        )

    # Generation is per-point in the seeded payload, so each generation family is written separately.
    for generation_id in {sample[4] for sample in DOCS.values()}:
        family = [chunk for chunk in chunks if DOCS[chunk.chunk_id][4] == generation_id]
        family_ids = {chunk.chunk_id for chunk in family}
        request = IndexingRequest(
            source=_source(DOCS[family[0].chunk_id][3]),
            generation_id=generation_id,
            chunks=family,
            embeddings=[emb for emb in embeddings if emb.chunk_id in family_ids],
        )
        result = store_chunks(request, config=search_config)
        assert result.validated is True
    return search_config


SCOPE = AccessScope(tenant_id="tenant-A", principals=["finance"])


def test_semantic_results_are_ranked_by_similarity(seeded):
    """Authorized decoys share vectors with the trio, so assert relative order, not absolute slots."""
    response = search_semantic(QUERY, scope=SCOPE, limit=10, config=seeded)

    ids = [result.evidence_id for result in response.results]
    scores = [result.score for result in response.results]

    assert ids.index("near") < ids.index("mid") < ids.index("far"), (
        f"unexpected order: {ids}"
    )
    assert scores == sorted(scores, reverse=True), f"not descending: {scores}"
    near_score = response.results[ids.index("near")].score
    mid_score = response.results[ids.index("mid")].score
    far_score = response.results[ids.index("far")].score
    assert near_score == pytest.approx(1.0, abs=1e-4)
    assert mid_score == pytest.approx(0.7071, abs=1e-3)
    assert far_score == pytest.approx(0.0, abs=1e-4)
    assert near_score > mid_score > far_score


def test_tenant_isolation_excludes_other_tenants(seeded):
    response = search_semantic(QUERY, scope=SCOPE, limit=10, config=seeded)

    assert "other-tenant" not in [result.evidence_id for result in response.results]


def test_acl_isolation_excludes_other_principals(seeded):
    response = search_semantic(QUERY, scope=SCOPE, limit=10, config=seeded)

    assert "other-acl" not in [result.evidence_id for result in response.results]


def test_generation_filter_restricts_results(seeded):
    response = search_semantic(
        QUERY, scope=SCOPE, limit=10, config=seeded, generation_ids=[GENERATION]
    )

    ids = [result.evidence_id for result in response.results]
    assert "other-generation" not in ids
    assert "near" in ids


def test_source_restriction_narrows_within_the_scope(seeded):
    response = search_semantic(
        QUERY, scope=SCOPE, limit=10, config=seeded, requested_source_ids=["doc-5"]
    )

    assert [result.evidence_id for result in response.results] == ["other-source"]


def test_non_intersecting_source_restriction_returns_empty(seeded):
    scope = AccessScope(
        tenant_id="tenant-A", principals=["finance"], source_ids=["doc-1"]
    )

    response = search_semantic(
        QUERY, scope=scope, limit=10, config=seeded, requested_source_ids=["doc-5"]
    )

    assert response.results == []


def test_limit_is_respected(seeded):
    response = search_semantic(QUERY, scope=SCOPE, limit=1, config=seeded)

    assert len(response.results) == 1


def test_no_match_returns_empty_result(seeded):
    scope = AccessScope(tenant_id="tenant-missing", principals=["finance"])

    response = search_semantic(QUERY, scope=scope, limit=10, config=seeded)

    assert response.results == []


def test_wrong_dimension_vector_is_rejected(seeded):
    with pytest.raises(SearchValidationError):
        search_semantic([1.0, 0.0], scope=SCOPE, limit=10, config=seeded)


def test_missing_scope_fails_closed(seeded):
    with pytest.raises(SearchScopeRequiredError):
        search_semantic(QUERY, scope=None, limit=10, config=seeded)


def test_unreachable_engine_raises_explicitly(tmp_path):
    unreachable = StorageConfig(
        url="http://127.0.0.1:6399",
        collection_name="does_not_exist",
        max_retries=0,
        timeout_seconds=1,
        sleep=lambda _s: None,
    )

    with pytest.raises(SearchEngineError):
        search_semantic(QUERY, scope=SCOPE, limit=10, config=unreachable)


def test_authorization_is_not_applied_after_retrieval(seeded, monkeypatch):
    """The engine is asked with the filter; no result is filtered afterwards."""
    import packages.retrieval.search as module

    captured = {}
    real = module.search_storage_semantic

    def spy(query_vector, *, search_filter, limit, config):
        captured["filter"] = search_filter
        return real(
            query_vector, search_filter=search_filter, limit=limit, config=config
        )

    monkeypatch.setattr(module, "search_storage_semantic", spy)
    response = search_semantic(QUERY, scope=SCOPE, limit=10, config=seeded)

    assert captured["filter"].tenant_id == "tenant-A"
    assert captured["filter"].principals == ("finance",)
    assert all(result.evidence_id != "other-tenant" for result in response.results)


# =====================================================================================
# T024: native BM25 against the same disposable, provisioned collection.
#
# Controlled dataset: every text is written by this test, term frequencies and lengths are
# explicit, so a ranking assertion is explainable rather than dependent on unrelated data.
# =====================================================================================

BM25_NORMALIZER = PersianNormalizer()

_BM25_VECTOR = [0.1, 0.2, 0.3, 0.4]

# chunk_id -> (text, tenant, principals, source_id, generation_id)
BM25_DOCS = {
    # term frequency at equal length: 3x vs 1x
    "tf-three": (
        "search search search alpha",
        "tenant-A",
        ["finance"],
        "doc-1",
        GENERATION,
    ),
    "tf-one": ("search alpha beta gamma", "tenant-A", ["finance"], "doc-1", GENERATION),
    # length at equal term frequency: short vs long
    "short": ("search alpha", "tenant-A", ["finance"], "doc-2", GENERATION),
    "long": (
        "search " + " ".join(f"filler{i}" for i in range(40)),
        "tenant-A",
        ["finance"],
        "doc-2",
        GENERATION,
    ),
    # unrelated
    "cooking": ("cooking recipes", "tenant-A", ["finance"], "doc-3", GENERATION),
    # multi-word (OR-like) partners
    "semantic-only": (
        "semantic alpha beta",
        "tenant-A",
        ["finance"],
        "doc-3",
        GENERATION,
    ),
    "cooking-only": (
        "cooking alpha beta",
        "tenant-A",
        ["finance"],
        "doc-3",
        GENERATION,
    ),
    # Persian and mixed
    "fa": (
        "جستجوی معنایی در پایگاه داده",
        "tenant-A",
        ["finance"],
        "doc-4",
        GENERATION,
    ),
    "fa-arabic": (
        "جستجوي معنايي در پايگاه",
        "tenant-A",
        ["finance"],
        "doc-5",
        GENERATION,
    ),
    "mixed": (
        "Hamtayar همتایار semantic search جستجو",
        "tenant-A",
        ["finance"],
        "doc-6",
        GENERATION,
    ),
    # unauthorized documents that would otherwise outrank everything (search x6)
    "other-tenant": (
        "search search search search search search",
        "tenant-B",
        ["finance"],
        "doc-7",
        GENERATION,
    ),
    "other-acl": (
        "search search search search search search",
        "tenant-A",
        ["engineering"],
        "doc-8",
        GENERATION,
    ),
    # authorized in the default scope (no generation/source restriction requested) so they must not
    # be used as exclusion evidence; kept at low term frequency so the decoy above really is the best.
    "other-generation": (
        "search alpha beta gamma delta",
        "tenant-A",
        ["finance"],
        "doc-9",
        "gen-2",
    ),
    "other-source": (
        "search alpha beta gamma delta",
        "tenant-A",
        ["finance"],
        "doc-10",
        GENERATION,
    ),
}


@pytest.fixture
def bm25_seeded(search_config: StorageConfig):  # noqa: F811 - intentional fixture dependency shadow
    """Seed the disposable collection through the existing storage write path."""
    chunks = {
        chunk_id: Chunk(
            chunk_id=chunk_id,
            source=_source(source_id),
            kind="document",
            text=text,
            access=AccessMetadata(tenant_id=tenant, acl_principals=principals),
        )
        for chunk_id, (
            text,
            tenant,
            principals,
            source_id,
            _generation,
        ) in BM25_DOCS.items()
    }
    embeddings = {
        chunk_id: EmbeddingRecord(
            chunk_id=chunk_id, model_id="embed-4d", vector=_BM25_VECTOR
        )
        for chunk_id in BM25_DOCS
    }
    for generation_id in {sample[4] for sample in BM25_DOCS.values()}:
        family = [
            chunk_id
            for chunk_id, sample in BM25_DOCS.items()
            if sample[4] == generation_id
        ]
        request = IndexingRequest(
            source=_source(BM25_DOCS[family[0]][3]),
            generation_id=generation_id,
            chunks=[chunks[chunk_id] for chunk_id in family],
            embeddings=[embeddings[chunk_id] for chunk_id in family],
        )
        assert store_chunks(request, config=search_config).validated is True
    return search_config


def _bm25(config, text, scope=SCOPE, limit=10, **kwargs):
    return search_lexical_bm25(
        text,
        scope=scope,
        config=config,
        normalizer=BM25_NORMALIZER,
        limit=limit,
        **kwargs,
    )


def _bm25_ids(response) -> list[str]:
    return [result.evidence_id for result in response.results]


def _score_of(response, chunk_id: str) -> float:
    for result in response.results:
        if result.evidence_id == chunk_id:
            return result.score
    raise AssertionError(f"{chunk_id} not in {_bm25_ids(response)}")


# ---- native execution and score shape


def test_bm25_returns_real_numeric_scores(bm25_seeded):
    response = _bm25(bm25_seeded, "search alpha")

    assert response.results, "expected BM25 matches"
    for result in response.results:
        assert isinstance(result.score, float)
        assert result.score > 0.0
        assert result.retrieval_method == "keyword"


def test_bm25_scores_are_strictly_descending(bm25_seeded):
    scores = [result.score for result in _bm25(bm25_seeded, "search alpha").results]

    assert scores == sorted(scores, reverse=True), (
        f"engine order not descending: {scores}"
    )


def test_bm25_term_frequency_increases_score(bm25_seeded):
    """Equal document length, 3 occurrences vs 1: only the frequency differs."""
    response = _bm25(bm25_seeded, "search")

    three, one = _score_of(response, "tf-three"), _score_of(response, "tf-one")
    assert three > one, f"tf effect missing: 3x={three} 1x={one}"


def test_bm25_shorter_document_ranks_higher_at_equal_frequency(bm25_seeded):
    response = _bm25(bm25_seeded, "search")

    short, long = _score_of(response, "short"), _score_of(response, "long")
    assert short > long, f"length effect missing: short={short} long={long}"


def test_bm25_multi_word_query_is_or_like(bm25_seeded):
    """Measured: `TextQuery` (BM25) matches documents holding any of the terms, unlike
    `MatchText` in a filter, which is AND."""
    ids = set(_bm25_ids(_bm25(bm25_seeded, "semantic cooking")))

    assert {"semantic-only", "cooking-only"} <= ids, f"OR semantics missing, got {ids}"


def test_bm25_no_match_returns_a_valid_empty_result(bm25_seeded):
    response = _bm25(bm25_seeded, "zzz-absent-term")

    assert response.results == []
    assert response.partial is False


def test_bm25_respects_the_limit(bm25_seeded):
    assert len(_bm25(bm25_seeded, "search", limit=2).results) == 2


# ---- Persian / mixed language


def test_bm25_persian_query_is_normalized(bm25_seeded):
    persian = set(_bm25_ids(_bm25(bm25_seeded, "جستجوی")))
    arabic = set(_bm25_ids(_bm25(bm25_seeded, "جستجوي")))

    assert persian == arabic, (
        "the injected normalizer must fold Arabic yeh for BM25 as well"
    )
    assert "fa" in persian


def test_bm25_does_not_reach_unnormalized_stored_text(bm25_seeded):
    """The index does not fold variants; normalized storage text is a prerequisite (documented gap)."""
    assert "fa-arabic" not in set(_bm25_ids(_bm25(bm25_seeded, "جستجوی")))


def test_bm25_mixed_persian_english_query(bm25_seeded):
    ids = set(_bm25_ids(_bm25(bm25_seeded, "search جستجو")))

    assert "mixed" in ids
    assert ids - {"mixed"}, "the English term must still match the English documents"


# ---- access control


def test_bm25_excludes_higher_scoring_unauthorized_documents(bm25_seeded):
    """The tenant-B / other-ACL decoys contain `search` six times, so one of them would rank first.

    Note: without an explicit `generation_ids` request no generation filter is applied (documented
    behaviour), so `other-generation` and `other-source` are authorized here and are checked by
    their own restriction tests instead.
    """
    response = _bm25(bm25_seeded, "search")

    ids = set(_bm25_ids(response))
    assert not {"other-tenant", "other-acl"} & ids, (
        f"unauthorized document leaked: {ids}"
    )

    unauthorized_best = search_lexical_bm25(
        "search",
        scope=AccessScope(tenant_id="tenant-B", principals=["finance"]),
        config=bm25_seeded,
        normalizer=BM25_NORMALIZER,
        limit=1,
    )
    assert _bm25_ids(unauthorized_best) == ["other-tenant"]
    best_authorized = max(result.score for result in response.results)
    assert unauthorized_best.results[0].score > best_authorized, (
        f"the excluded document ({unauthorized_best.results[0].score}) must outrank every "
        f"authorized result (best {best_authorized}) - otherwise this test proves nothing"
    )


def test_bm25_acl_isolation(bm25_seeded):
    other = AccessScope(tenant_id="tenant-A", principals=["engineering"])

    assert _bm25_ids(_bm25(bm25_seeded, "search", scope=other)) == ["other-acl"]


def test_bm25_source_restriction(bm25_seeded):
    ids = set(_bm25_ids(_bm25(bm25_seeded, "search", requested_source_ids=["doc-2"])))

    assert ids == {"short", "long"}


def test_bm25_generation_restriction(bm25_seeded):
    ids = set(_bm25_ids(_bm25(bm25_seeded, "search", generation_ids=["gen-2"])))

    assert ids == {"other-generation"}


def test_bm25_empty_source_intersection_makes_no_engine_call():
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

    response = search_lexical_bm25(
        "search",
        scope=scope,
        config=unreachable,
        normalizer=BM25_NORMALIZER,
        requested_source_ids=["doc-99"],
    )

    assert response.results == []


def test_bm25_missing_scope_fails_closed(bm25_seeded):
    with pytest.raises(SearchScopeRequiredError):
        search_lexical_bm25(
            "search", scope=None, config=bm25_seeded, normalizer=BM25_NORMALIZER
        )


# ---- validation and engine failures


@pytest.mark.parametrize("query", ["", "   "])
def test_bm25_blank_query_is_rejected(bm25_seeded, query):
    with pytest.raises(SearchValidationError):
        _bm25(bm25_seeded, query)


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_bm25_invalid_limit_is_rejected(bm25_seeded, limit):
    with pytest.raises(SearchValidationError):
        _bm25(bm25_seeded, "search", limit=limit)


def test_bm25_unreachable_engine_raises_explicitly():
    unreachable = StorageConfig(
        url="http://127.0.0.1:6399",
        collection_name="no_such",
        max_retries=0,
        timeout_seconds=1,
    )

    with pytest.raises(SearchEngineError):
        search_lexical_bm25(
            "search", scope=SCOPE, config=unreachable, normalizer=BM25_NORMALIZER
        )


# ---- score semantics stay distinct


def test_bm25_scores_are_distinct_from_unranked_filtering(bm25_seeded):
    """Same query, same scope, two operations: `keyword`+score means BM25, `keyword`+None means a match."""
    ranked = _bm25(bm25_seeded, "search")
    unranked = search_lexical_filter(
        "search", scope=SCOPE, config=bm25_seeded, normalizer=BM25_NORMALIZER, limit=10
    )

    assert all(
        result.retrieval_method == "keyword"
        for result in ranked.results + unranked.results
    )
    assert all(isinstance(result.score, float) for result in ranked.results)
    assert all(result.score is None for result in unranked.results)
    assert {result.evidence_id for result in unranked.results} <= {
        r.evidence_id for r in ranked.results
    }


def test_per_method_latency_observations(bm25_seeded, capsys):
    """T027: repeatable small-collection measurements, explicitly not an SLA benchmark."""
    sample_size = 20
    operations = {
        "semantic": lambda: search_semantic(
            [0.1, 0.2, 0.3, 0.4], scope=SCOPE, config=bm25_seeded, limit=10
        ),
        "lexical_filter": lambda: search_lexical_filter(
            "search",
            scope=SCOPE,
            config=bm25_seeded,
            normalizer=BM25_NORMALIZER,
            limit=10,
        ),
        "phrase": lambda: search_lexical_phrase(
            "semantic search",
            scope=SCOPE,
            config=bm25_seeded,
            normalizer=BM25_NORMALIZER,
            limit=10,
        ),
        "bm25": lambda: search_lexical_bm25(
            "search",
            scope=SCOPE,
            config=bm25_seeded,
            normalizer=BM25_NORMALIZER,
            limit=10,
        ),
    }
    observations = {}
    for name, operation in operations.items():
        operation()  # warm-up is excluded from the sample
        durations = []
        for _ in range(sample_size):
            started = time.perf_counter()
            operation()
            durations.append((time.perf_counter() - started) * 1000)
        ordered = sorted(durations)
        observations[name] = {
            "min_ms": round(ordered[0], 3),
            "median_ms": round(statistics.median(ordered), 3),
            "p95_ms": round(ordered[int(0.95 * (sample_size - 1))], 3),
            "max_ms": round(ordered[-1], 3),
        }

    with capsys.disabled():
        print(
            "T027 latency observations (local disposable collection; not production-scale): "
            f"documents={len(BM25_DOCS)}, queries_per_method={sample_size}, "
            f"total_queries={sample_size * len(operations)}, stats={observations}"
        )
