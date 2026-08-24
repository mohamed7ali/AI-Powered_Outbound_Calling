from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from threading import RLock
from typing import Protocol

from outbound_ai.config.settings import Settings, get_settings


class EmbeddingPort(Protocol):
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text."""


def vector_literal(vector: Sequence[float]) -> str:
    """Format a vector for the PostgreSQL pgvector cast."""

    return "[" + ",".join(f"{float(value):.10g}" for value in vector) + "]"


class OpenAIEmbeddings:
    """Adapter for an OpenAI-compatible embedding endpoint."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings")
        if self.settings.openai_embedding_dim != self.settings.rag_embedding_dim:
            raise ValueError(
                "OPENAI_EMBEDDING_DIM must equal RAG_EMBEDDING_DIM "
                f"({self.settings.rag_embedding_dim}) for the current database schema"
            )
        from openai import OpenAI

        self.client = OpenAI(api_key=self.settings.openai_api_key.get_secret_value())
        self.dimension = self.settings.openai_embedding_dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=list(texts),
            dimensions=self.dimension,
        )
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if any(len(vector) != self.dimension for vector in vectors):
            raise ValueError("Embedding provider returned an unexpected vector dimension")
        return vectors


class SentenceTransformerEmbeddings:
    """Local Arabic Sentence Transformer adapter for semantic RAG retrieval.

    The model is loaded lazily by this class, not at module import time, so API
    startup and unit tests do not download a model unexpectedly. The selected
    model is normalized for cosine similarity and must match the database vector
    dimension configured by ``RAG_EMBEDDING_DIM``.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for RAG_EMBEDDING_PROVIDER="
                "sentence_transformers; install the project dependencies first"
            ) from exc

        self.model_name = self.settings.sentence_transformer_model
        self.dimension = self.settings.rag_embedding_dim
        self.model = SentenceTransformer(
            self.model_name,
            device=self.settings.sentence_transformer_device,
            trust_remote_code=False,
        )
        model_dimension = self.model.get_sentence_embedding_dimension()
        if model_dimension != self.dimension:
            raise ValueError(
                f"Sentence Transformer {self.model_name!r} returns {model_dimension} dimensions, "
                f"but RAG_EMBEDDING_DIM is {self.dimension}; create a migration before changing it"
            )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        encoded = self.model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = [[float(value) for value in row] for row in encoded]
        if len(vectors) != len(texts) or any(len(vector) != self.dimension for vector in vectors):
            raise ValueError("Sentence Transformer returned an unexpected vector shape")
        return vectors


_PROVIDER_CACHE: dict[tuple[object, ...], EmbeddingPort] = {}
_PROVIDER_CACHE_LOCK = RLock()


def clear_embedding_cache() -> None:
    """Clear cached providers for tests or an explicit model reload."""

    with _PROVIDER_CACHE_LOCK:
        _PROVIDER_CACHE.clear()


class DeterministicEmbeddings:
    """Stable hash vectors for tests and emergency offline demos only."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            for offset in range(0, len(digest), 2):
                index = int.from_bytes(digest[offset : offset + 2], "big") % self.dimension
                vector[index] += (digest[offset] / 255.0) - 0.5
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


def build_embeddings(settings: Settings | None = None) -> EmbeddingPort:
    """Build and cache the provider shared by ingestion and question retrieval."""

    settings = settings or get_settings()
    if settings.rag_embedding_provider == "sentence_transformers":
        cache_key = (
            "sentence_transformers",
            settings.sentence_transformer_model,
            settings.sentence_transformer_device,
            settings.rag_embedding_dim,
        )
        factory = lambda: SentenceTransformerEmbeddings(settings)
    elif settings.rag_embedding_provider == "deterministic":
        cache_key = ("deterministic", settings.rag_embedding_dim)
        factory = lambda: DeterministicEmbeddings(settings.rag_embedding_dim)
    elif settings.rag_embedding_provider == "openai":
        cache_key = (
            "openai",
            settings.openai_embedding_model,
            settings.openai_embedding_dim,
            settings.rag_embedding_dim,
        )
        factory = lambda: OpenAIEmbeddings(settings)
    else:
        raise ValueError(f"Unsupported RAG embedding provider: {settings.rag_embedding_provider}")

    with _PROVIDER_CACHE_LOCK:
        provider = _PROVIDER_CACHE.get(cache_key)
        if provider is None:
            provider = factory()
            _PROVIDER_CACHE[cache_key] = provider
        return provider
