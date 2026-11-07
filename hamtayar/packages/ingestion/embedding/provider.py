"""Sentence-Transformers adapter for dense Hamtayar embeddings."""

import math

from packages.knowledge.configuration import KnowledgeConfiguration


class SentenceTransformerEmbeddingProvider:
    """Encode document texts and queries using the configured dense model.

    Document vectors are raw; ingestion.embedding.service handles normalization.
    Query vectors are normalized here when configured, for retrieval consistency.
    """

    def __init__(
        self,
        configuration: KnowledgeConfiguration,
        *,
        local_files_only: bool = False,
        device: str | None = None,
        batch_size: int = 32,
    ) -> None:
        if not isinstance(configuration, KnowledgeConfiguration):
            raise TypeError("configuration must be KnowledgeConfiguration")

        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size < 1
        ):
            raise ValueError("batch_size must be a positive integer")

        settings = configuration.embedding

        if settings.output_mode != "dense":
            raise ValueError("Only dense embeddings are supported")

        if settings.tokenizer_id != settings.model_id:
            raise ValueError("This provider requires tokenizer_id to equal model_id")

        if settings.tokenizer_revision != settings.model_revision:
            raise ValueError(
                "This provider requires matching model/tokenizer revisions"
            )

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required; install it with "
                "pip install sentence-transformers"
            ) from exc

        self._model = SentenceTransformer(
            settings.model_id,
            revision=settings.model_revision,
            local_files_only=local_files_only,
            trust_remote_code=False,
            device=device,
        )

        actual_dimensions = self._model.get_sentence_embedding_dimension()

        if actual_dimensions != settings.dimensions:
            raise ValueError(
                f"Embedding model has {actual_dimensions} dimensions; "
                f"configuration requires {settings.dimensions}"
            )

        self._dimensions = settings.dimensions
        self._normalize = settings.normalize_embeddings
        self._batch_size = batch_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Produce raw vectors; embed_chunks handles document normalization."""

        if not isinstance(texts, list) or any(
            not isinstance(text, str) for text in texts
        ):
            raise TypeError("texts must be a list of strings")

        if not texts:
            return []

        if any(not text.strip() for text in texts):
            raise ValueError("Cannot embed empty or whitespace-only text")

        embeddings = self._model.encode(
            texts,
            batch_size=self._batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )

        vectors = embeddings.tolist()

        if len(vectors) != len(texts):
            raise RuntimeError(
                "Embedding model returned an unexpected number of vectors"
            )

        for vector in vectors:
            if len(vector) != self._dimensions or not all(
                math.isfinite(float(v)) for v in vector
            ):
                raise ValueError("Embedding model returned an invalid vector")

        return vectors

    def embed_query(self, query: str) -> list[float]:
        """Encode one query using the same normalization as indexed chunks."""

        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        vector = self.embed_texts([query])[0]

        if self._normalize:
            norm = math.sqrt(math.fsum(value * value for value in vector))

            if not math.isfinite(norm) or norm == 0:
                raise ValueError("Query embedding has an invalid norm")

            vector = [value / norm for value in vector]

        return vector

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """Allow this provider to be used as an embed_texts callback."""
        return self.embed_texts(texts)


class AsyncEmbeddingAdapter:
    """Adapt an existing synchronous provider to the workflow's async contract."""

    def __init__(self, provider, *, model_id: str):
        self.provider, self.model_id = provider, model_id

    async def embed_texts(self, texts, *, model_id):
        import asyncio

        if model_id != self.model_id:
            raise ValueError("Embedding model mismatch")
        return await asyncio.to_thread(self.provider.embed_texts, list(texts))
