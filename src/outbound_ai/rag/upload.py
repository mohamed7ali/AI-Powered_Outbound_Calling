"""Private Supabase Storage upload and ingestion orchestration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import requests

from outbound_ai.config.settings import Settings, get_settings
from outbound_ai.db.connection import TenantContext
from outbound_ai.rag.embeddings import EmbeddingPort
from outbound_ai.rag.ingestion import IngestionResult, ingest_text
from outbound_ai.rag.loaders import extract_text


def upload_private_document(
    *,
    context: TenantContext,
    uploaded_by: UUID,
    file_path: str | Path,
    embeddings: EmbeddingPort,
    settings: Settings | None = None,
) -> IngestionResult:
    """Upload, extract, embed, and persist a document under the active tenant."""

    if context.organization_id is None:
        raise ValueError("An organization context is required")
    settings = settings or get_settings()
    local_path = Path(file_path)
    content = local_path.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    extracted = extract_text(local_path)
    suffix = local_path.suffix.lower()
    safe_suffix = "".join(ch for ch in suffix if ch.isascii() and (ch.isalnum() or ch == "."))
    if not safe_suffix.startswith("."):
        safe_suffix = ".bin"
    # Storage object keys are ASCII-safe; preserve the original Arabic filename
    # separately in source_metadata below for display and citation purposes.
    storage_path = f"{context.organization_id}/{checksum}-document{safe_suffix}"
    _upload_to_storage(
        settings=settings,
        bucket=settings.document_storage_bucket,
        storage_path=storage_path,
        content=content,
        content_type=extracted.mime_type,
    )
    database = __import__("outbound_ai.db.connection", fromlist=["get_database"]).get_database()
    with database.transaction(context) as connection:
        result = ingest_text(
            connection,
            context=context,
            uploaded_by=uploaded_by,
            title=extracted.title,
            storage_path=storage_path,
            mime_type=extracted.mime_type,
            text=extracted.text,
            embeddings=embeddings,
        )
        connection.execute(
            """
            update public.knowledge_documents
            set checksum = %s, source_metadata = %s::jsonb, status = 'READY', updated_at = now()
            where id = %s and organization_id = %s
            """,
            (
                checksum,
                __import__("json").dumps({"page_count": extracted.page_count, "filename": local_path.name}),
                result.document_id,
                context.organization_id,
            ),
        )
    return result


def _upload_to_storage(
    *,
    settings: Settings,
    bucket: str,
    storage_path: str,
    content: bytes,
    content_type: str,
) -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase Storage service-role configuration is missing")
    server_key = settings.supabase_service_role_key.get_secret_value()
    encoded_bucket = quote(bucket, safe="")
    encoded_path = quote(storage_path, safe="/-_.")
    headers = {
        "apikey": server_key,
        "Content-Type": content_type or "application/octet-stream",
        # The checksum path makes retries idempotent after a partial ingestion.
        "x-upsert": "true",
    }
    # Legacy service_role values are JWTs. New sb_secret_ values are not JWTs
    # and must not be sent as Authorization Bearer tokens.
    if not server_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {server_key}"
    response = requests.post(
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{encoded_bucket}/{encoded_path}",
        headers=headers,
        data=content,
        timeout=60,
    )
    if response.status_code not in {200, 201}:
        try:
            body = response.json()
            detail = body.get("message") or body.get("error") or body.get("code") or "request rejected"
        except ValueError:
            detail = response.text[:240] or "request rejected"
        raise RuntimeError(
            f"Supabase Storage upload failed with HTTP {response.status_code}: {str(detail)[:240]}"
        )
