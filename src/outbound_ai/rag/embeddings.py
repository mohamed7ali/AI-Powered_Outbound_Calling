"""Embedding ports for production and offline RAG tests."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
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
    """Production adapter for OpenAI embeddings."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings")
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


class DeterministicEmbeddings:
    """Stable hash vectors for tests; never use these for production retrieval."""

    def __init__(self, dimension: int = 3072) -> None:
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
