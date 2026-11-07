"""Explicit offline CLI integration fixture; not a runtime backend for real users."""

from pathlib import Path

from apps.pipelines.local import LocalDevelopmentAuthorization, local_context
from apps.pipelines.runtime import build_pipelines
from packages.documents.normalization.service import PersianNormalizer
from packages.knowledge.configuration import KnowledgeConfiguration
from packages.knowledge.publication.catalog import LocalSqliteGenerationCatalog
from packages.storage import service as storage
from packages.storage.artifacts.repository import LocalArtifactRepository
from packages.storage.qdrant.adapter import QdrantAdapter
from qdrant_client import QdrantClient, models


class FixtureEmbedding:
    async def embed_texts(self, texts, *, model_id):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def build(args, checkpointer):
    context = local_context(args)
    root = Path(args.work_dir).resolve()
    client = QdrantClient(path=str(root / "qdrant-test-only"))
    if not client.collection_exists("cli_test"):
        client.create_collection(
            "cli_test",
            vectors_config={
                "dense": models.VectorParams(size=4, distance=models.Distance.COSINE)
            },
        )
    config = storage.StorageConfig(collection_name="cli_test", vector_size=4)
    storage._adapter = lambda _: QdrantAdapter(config, client=client)
    runtime = build_pipelines(
        configuration=KnowledgeConfiguration(
            embedding={"model_id": "TEST-ONLY", "dimensions": 4}
        ),
        artifacts=LocalArtifactRepository(
            root=root / "artifacts",
            allowed_roots=[root.parent],
            max_raw_bytes=10000,
            tenant_id=context.tenant_id,
        ),
        catalog=LocalSqliteGenerationCatalog(database_path=root / "catalog.sqlite"),
        storage_config=config,
        authorization=LocalDevelopmentAuthorization(context),
        count_tokens=lambda text: len(text.split()),
        embedding_provider=FixtureEmbedding(),
        embed_query=lambda _: [1.0, 0.0, 0.0, 0.0],
        query_normalizer=PersianNormalizer,
        checkpointer=checkpointer,
        ingestion_breakpoints=tuple(args.pause_after)
        if args.workflow == "ingestion"
        else (),
        retrieval_breakpoints=tuple(args.pause_after)
        if args.workflow == "retrieval"
        else (),
    )
    # The process owns this fixture's client; references stay alive until process exit.
    return runtime, context
