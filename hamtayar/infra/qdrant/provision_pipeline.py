"""Create/validate a disposable document-pipeline collection; never delete data."""

import argparse

from infra.qdrant.provision_search_indexes import (
    guard_collection_name,
    provision,
    report,
)
from packages.knowledge.configuration import load_knowledge_configuration
from qdrant_client import QdrantClient, models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:6333")
    parser.add_argument("--collection", default="hamtayar_search_pipeline")
    parser.add_argument("--config", default="config/knowledge.toml")
    parser.add_argument("--vector-name", default="dense")
    args = parser.parse_args()
    guard_collection_name(args.collection)
    size = load_knowledge_configuration(args.config).embedding.dimensions
    with QdrantClient(url=args.url, timeout=30, check_compatibility=False) as client:
        if not client.collection_exists(args.collection):
            client.create_collection(
                args.collection,
                vectors_config={
                    args.vector_name: models.VectorParams(
                        size=size, distance=models.Distance.COSINE
                    )
                },
            )
        vectors = client.get_collection(args.collection).config.params.vectors
        profile = vectors.get(args.vector_name) if isinstance(vectors, dict) else None
        if (
            profile is None
            or profile.size != size
            or profile.distance != models.Distance.COSINE
        ):
            raise ValueError(
                "Collection vector profile differs from configuration; use a separate development collection"
            )
        provision(client, args.collection)
        client.create_payload_index(
            args.collection, "generation_id", models.PayloadSchemaType.KEYWORD
        )
        report(client, args.collection)


if __name__ == "__main__":
    main()
