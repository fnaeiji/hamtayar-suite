"""Local-only test collection setup for S-02 (dev/test support, never production).

Idempotent: safe to run any number of times. It only creates or recreates the configured test
collection and prints the profile read back from Qdrant.

    uv run python infra/qdrant/create_test_collection.py
    uv run python infra/qdrant/create_test_collection.py --recreate
"""

from __future__ import annotations

import argparse
import sys

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest


class TestCollectionConfig:
    """Local test profile. Defaults match the S-02 development environment."""

    url: str = "http://127.0.0.1:6333"
    collection_name: str = "hamtayar_test_chunks"
    vector_name: str = "dense"
    vector_size: int = 4
    distance: str = "Cosine"


def _distance(name: str) -> rest.Distance:
    mapping = {
        "Cosine": rest.Distance.COSINE,
        "Dot": rest.Distance.DOT,
        "Euclid": rest.Distance.EUCLID,
        "Manhattan": rest.Distance.MANHATTAN,
    }
    return mapping[name]


def ensure_collection(config: TestCollectionConfig, recreate: bool = False) -> None:
    client = QdrantClient(url=config.url, timeout=10)
    try:
        exists = client.collection_exists(config.collection_name)
        if exists and recreate:
            client.delete_collection(config.collection_name)
            exists = False
            print(f"recreated: deleted existing collection {config.collection_name}")
        if not exists:
            client.create_collection(
                collection_name=config.collection_name,
                vectors_config={
                    config.vector_name: rest.VectorParams(
                        size=config.vector_size, distance=_distance(config.distance)
                    )
                },
            )
            print(f"created collection {config.collection_name}")
        else:
            print(f"collection {config.collection_name} already exists (no change)")

        info = client.get_collection(config.collection_name)
        vectors = info.config.params.vectors
        params = vectors[config.vector_name] if isinstance(vectors, dict) else vectors
        print(
            f"verified collection: name={config.collection_name} "
            f"vector={config.vector_name} size={params.size} distance={params.distance}"
        )
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=TestCollectionConfig.url)
    parser.add_argument("--collection", default=TestCollectionConfig.collection_name)
    parser.add_argument("--vector-name", default=TestCollectionConfig.vector_name)
    parser.add_argument("--vector-size", type=int, default=TestCollectionConfig.vector_size)
    parser.add_argument("--distance", default=TestCollectionConfig.distance)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="delete and recreate the collection (local test collection only)",
    )
    args = parser.parse_args(argv)

    config = TestCollectionConfig()
    config.url = args.url
    config.collection_name = args.collection
    config.vector_name = args.vector_name
    config.vector_size = args.vector_size
    config.distance = args.distance

    try:
        ensure_collection(config, recreate=args.recreate)
    except Exception as exc:  # noqa: BLE001 - report, do not pretend success
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
