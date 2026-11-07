"""Explicitly opted-in, single-user local development wiring. Never used by API."""

import os
from pathlib import Path

from packages.contracts.access import AccessMetadata, TrustedAccessContext
from packages.documents.normalization.service import PersianNormalizer
from packages.ingestion.embedding.provider import (
    AsyncEmbeddingAdapter,
    SentenceTransformerEmbeddingProvider,
)
from packages.knowledge.configuration import load_knowledge_configuration
from packages.knowledge.publication.catalog import LocalSqliteGenerationCatalog
from packages.knowledge.tokenizer import HuggingFaceTokenizer
from packages.storage.service import LocalArtifactRepository, StorageConfig

from apps.pipelines.runtime import build_pipelines


class LocalDevelopmentAuthorization:
    """CLI operator explicitly grants local access; this does not impersonate Padeen."""

    def __init__(self, context):
        self.context = context

    async def authorize_action(self, *, context, source, action):
        if context != self.context or action not in ("ingest", "publish"):
            raise PermissionError("Local context mismatch")
        return AccessMetadata(
            tenant_id=context.tenant_id, acl_principals=context.principals
        )

    async def authorize_sources(self, context, sources):
        if context != self.context:
            raise PermissionError("Local context mismatch")
        return sources


def local_context(args):
    return TrustedAccessContext(
        subject_id=args.subject,
        tenant_id=args.tenant,
        principals=args.principal or ["user:local"],
    )


def build_local_runtime(args, checkpointer):
    if not args.local_access:
        raise ValueError(
            "Choose --local-access for single-user development or supply --factory for trusted authorization"
        )
    context = local_context(args)
    authorization = LocalDevelopmentAuthorization(context)
    configuration = load_knowledge_configuration(args.config)
    tokenizer = HuggingFaceTokenizer(configuration.embedding)
    count_tokens = lambda text: tokenizer.count_tokens(
        text, include_special_tokens=configuration.embedding.include_special_tokens
    )
    provider = SentenceTransformerEmbeddingProvider(
        configuration,
        local_files_only=configuration.embedding.tokenizer_local_files_only,
    )
    root = Path(args.work_dir).resolve()
    artifacts = LocalArtifactRepository(
        root=root / "artifacts",
        allowed_roots=[Path(p) for p in args.allowed_root],
        max_raw_bytes=args.max_bytes,
        tenant_id=context.tenant_id,
    )
    catalog = LocalSqliteGenerationCatalog(database_path=root / "catalog.sqlite")
    storage_config = StorageConfig(
        url=args.qdrant_url,
        collection_name=args.collection,
        vector_name=args.vector_name,
        vector_size=configuration.embedding.dimensions,
    )
    generator = None
    if os.environ.get("HAMTAYAR_LLM_BASE_URL") and os.environ.get("HAMTAYAR_LLM_MODEL"):
        from packages.integrations.chat import ChatAnswerGenerator

        generator = ChatAnswerGenerator(
            base_url=os.environ["HAMTAYAR_LLM_BASE_URL"],
            model=os.environ["HAMTAYAR_LLM_MODEL"],
            api_key=os.environ.get("HAMTAYAR_LLM_API_KEY"),
        )
    runtime = build_pipelines(
        configuration=configuration,
        artifacts=artifacts,
        catalog=catalog,
        storage_config=storage_config,
        authorization=authorization,
        count_tokens=count_tokens,
        embedding_provider=AsyncEmbeddingAdapter(
            provider, model_id=configuration.embedding.model_id
        ),
        embed_query=provider.embed_query,
        query_normalizer=PersianNormalizer,
        checkpointer=checkpointer,
        generator=generator,
        ingestion_breakpoints=tuple(args.pause_after)
        if args.workflow == "ingestion"
        else (),
        retrieval_breakpoints=tuple(args.pause_after)
        if args.workflow == "retrieval"
        else (),
    )
    return runtime, context
