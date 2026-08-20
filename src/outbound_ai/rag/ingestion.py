"""Organization-scoped document ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from outbound_ai.db.connection import TenantContext
from outbound_ai.db.repositories.knowledge import create_document, insert_chunks
from outbound_ai.rag.chunking import TextChunk, chunk_text
from outbound_ai.rag.embeddings import EmbeddingPort, vector_literal


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: UUID
    chunk_count: int


def ingest_text(
    connection,
    *,
    context: TenantContext,
    uploaded_by: UUID,
    title: str,
    storage_path: str,
    mime_type: str,
    text: str,
    embeddings: EmbeddingPort,
    language: str = "ar",
    max_characters: int = 1200,
    overlap_characters: int = 180,
) -> IngestionResult:
    """Ingest text only after the caller has authenticated and set tenant context."""

    if context.organization_id is None:
        raise ValueError("Document ingestion requires an organization context")
    if not text.strip():
        raise ValueError("Document text cannot be empty")
    chunks = chunk_text(
        text,
        max_characters=max_characters,
        overlap_characters=overlap_characters,
    )
    vectors = embeddings.embed([chunk.content_norm for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("Embedding provider returned the wrong number of vectors")
    if any(len(vector) != embeddings.dimension for vector in vectors):
        raise ValueError("Embedding provider returned the wrong vector dimension")

    document = create_document(
        connection,
        organization_id=context.organization_id,
        uploaded_by=uploaded_by,
        title=title,
        storage_path=storage_path,
        mime_type=mime_type,
        language=language,
    )
    insert_chunks(
        connection,
        organization_id=context.organization_id,
        document_id=document.id,
        chunks=[
            (
                chunk.index,
                chunk.content_raw,
                chunk.content_norm,
                chunk.page_number,
                vector_literal(vector),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )
    return IngestionResult(document_id=document.id, chunk_count=len(chunks))
