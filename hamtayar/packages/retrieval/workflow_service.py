"""Async orchestration adapters around the existing permissioned search functions."""

import asyncio
from collections import defaultdict

from packages.access.authorization import reauthorize_results
from packages.access.scope import build_access_scope
from packages.contracts.retrieval import RetrievalResponse
from packages.retrieval import search
from packages.retrieval.query_text import normalize_query


def identity(result):
    source = result.source
    return (
        source.source.knowledge_space_id,
        source.source.source_type,
        source.source.source_id,
        source.version,
        result.generation_id,
    )


class RetrievalWorkflowService:
    def __init__(
        self, *, catalog, authorization, normalizer, storage_config, embed_query=None
    ):
        self.catalog, self.authorization = catalog, authorization
        self.normalizer, self.storage_config, self.embed_query = (
            normalizer,
            storage_config,
            embed_query,
        )

    async def prefilter(self, *, request, context):
        scope = build_access_scope(context, request.source_ids)
        active = await self.catalog.active_generations(scope=scope)
        return scope, active

    def normalize(self, query):
        return normalize_query(query, normalizer=self.normalizer)

    async def retrieve(self, *, request, scope, active):
        if not active:
            return RetrievalResponse()
        kwargs = {
            "scope": scope,
            "config": self.storage_config,
            "limit": request.top_k,
            "generation_ids": list({item.generation_id for item in active}),
            "requested_source_ids": request.source_ids,
        }
        responses = []
        if request.mode in ("semantic", "hybrid"):
            if self.embed_query is None:
                raise ValueError("Query embedding provider is required")
            vector = await asyncio.to_thread(self.embed_query, request.query)
            responses.append(
                await asyncio.to_thread(search.search_semantic, vector, **kwargs)
            )
        if request.mode in ("keyword", "hybrid"):
            responses.append(
                await asyncio.to_thread(
                    search.search_lexical_bm25,
                    request.query,
                    normalizer=self.normalizer,
                    **kwargs,
                )
            )
        if request.mode == "code":
            raise ValueError("Code retrieval is outside the document pipeline")
        allowed = {
            (
                a.source.source.knowledge_space_id,
                a.source.source.source_type,
                a.source.source.source_id,
                a.source.version,
                a.generation_id,
            )
            for a in active
        }
        scores, unique = defaultdict(float), {}
        for response in responses:
            for rank, result in enumerate(response.results, 1):
                if identity(result) not in allowed:
                    continue
                key = (*identity(result), result.evidence_id)
                unique[key] = result
                scores[key] += 1 / (60 + rank)
        ordered = sorted(unique, key=lambda key: -scores[key])
        return RetrievalResponse(
            results=[
                unique[key].model_copy(
                    update={
                        "score": scores[key],
                        "retrieval_method": "hybrid",
                    }
                )
                if request.mode == "hybrid"
                else unique[key]
                for key in ordered[: request.top_k]
            ],
            partial=any(r.partial for r in responses),
            warnings=[w for r in responses for w in r.warnings],
        )

    async def reauthorize(self, *, results, context):
        # Re-read publication and permissions immediately before context construction.
        scope = build_access_scope(context)
        active = await self.catalog.active_generations(scope=scope)
        allowed = {
            (
                a.source.source.knowledge_space_id,
                a.source.source.source_type,
                a.source.source.source_id,
                a.source.version,
                a.generation_id,
            )
            for a in active
        }
        current = [r for r in results if identity(r) in allowed]
        return await reauthorize_results(current, context, self.authorization)
