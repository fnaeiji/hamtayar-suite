"""Explicit service composition; no HTTP server, queue, or implicit access grants."""

from dataclasses import dataclass

from packages.contracts.document_ingestion import EmbeddingProfile, IndexProfile
from packages.ingestion.chunking.service import DocumentChunkingService
from packages.ingestion.loader import DocumentLoader
from packages.ingestion.normalize_service import DocumentNormalizationService
from packages.ingestion.parser_dispatch import DocumentParserDispatcher
from packages.integrations.embedding.service import EmbeddingService
from packages.knowledge.ingestion.facade import DefaultDocumentWorkflowPorts
from packages.knowledge.ingestion.index_service import DocumentIndexService
from packages.knowledge.publication.service import DocumentPublicationService
from packages.retrieval.workflow_service import RetrievalWorkflowService

from apps.document_ingestion.workflows.document_ingestion.graph import (
    build_document_ingestion_graph,
)
from apps.retrieval.workflows.answer.graph import build_answer_graph


@dataclass
class PipelineRuntime:
    ingestion: object
    retrieval: object
    authorization: object
    artifacts: object
    catalog: object


def build_pipelines(
    *,
    configuration,
    artifacts,
    catalog,
    storage_config,
    authorization,
    count_tokens,
    embedding_provider,
    embed_query,
    query_normalizer,
    checkpointer,
    generator=None,
    reranker=None,
    binary_parsers=None,
    normalizer_profiles=None,
    ingestion_breakpoints=(),
    retrieval_breakpoints=(),
    max_context_tokens=6000,
    store=None,
):
    """Caller owns resource lifetimes and supplies verified authorization integration."""
    spec = EmbeddingProfile(
        configuration.embedding.model_id, configuration.embedding.dimensions
    )
    ports = DefaultDocumentWorkflowPorts(
        loader=DocumentLoader(artifacts=artifacts),
        parser=DocumentParserDispatcher(
            artifacts=artifacts, binary_parsers=binary_parsers
        ),
        normalizer=DocumentNormalizationService(
            artifacts=artifacts, profiles=normalizer_profiles
        ),
        chunker=DocumentChunkingService(
            artifacts=artifacts, count_tokens=count_tokens, configuration=configuration
        ),
        embedder=EmbeddingService(
            artifacts=artifacts,
            provider=embedding_provider,
            spec=spec,
            batch_size=32,
            normalize_embeddings=configuration.embedding.normalize_embeddings,
        ),
        indexer=DocumentIndexService(
            artifacts=artifacts,
            catalog=catalog,
            config=storage_config,
            profile=IndexProfile(
                spec, configuration.chunking.profile, "document-pipeline-v1"
            ),
            store=store,
        ),
        publisher=DocumentPublicationService(catalog=catalog),
    )
    service = RetrievalWorkflowService(
        catalog=catalog,
        authorization=authorization,
        normalizer=query_normalizer,
        storage_config=storage_config,
        embed_query=embed_query,
    )
    return PipelineRuntime(
        ingestion=build_document_ingestion_graph(
            ports, checkpointer=checkpointer, interrupt_after=ingestion_breakpoints
        ),
        retrieval=build_answer_graph(
            service=service,
            count_tokens=count_tokens,
            generator=generator,
            reranker=reranker,
            checkpointer=checkpointer,
            interrupt_after=retrieval_breakpoints,
            max_context_tokens=max_context_tokens,
        ),
        authorization=authorization,
        artifacts=artifacts,
        catalog=catalog,
    )
