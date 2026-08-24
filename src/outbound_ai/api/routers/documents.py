"""Authenticated organization document ingestion endpoint."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from outbound_ai.api.auth import Principal, require_principal, tenant_context
from outbound_ai.config.settings import get_settings
from outbound_ai.rag.embeddings import build_embeddings
from outbound_ai.rag.upload import upload_private_document

router = APIRouter()
_ALLOWED = {".pdf", ".docx", ".txt", ".md", ".csv", ".json"}
_MAX_BYTES = 25 * 1024 * 1024


@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> dict:
    context = tenant_context(principal, organization_id)
    if context.actor_role not in {"PLATFORM_ADMIN", "ORG_ADMIN"}:
        raise HTTPException(status_code=403, detail="Organization administrator permission required")
    filename = Path(file.filename or "document").name
    if Path(filename).suffix.lower() not in _ALLOWED:
        raise HTTPException(status_code=415, detail="Only PDF, DOCX, TXT, MD, CSV, and JSON are supported")
    content = file.file.read(_MAX_BYTES + 1)
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 25 MB limit")
    with tempfile.TemporaryDirectory(prefix="arabic-kb-") as temp_dir:
        path = Path(temp_dir) / filename
        path.write_bytes(content)
        settings = get_settings()
        embeddings = build_embeddings(settings)
        try:
            result = upload_private_document(
                context=context,
                uploaded_by=principal.user_id,
                file_path=path,
                embeddings=embeddings,
                settings=settings,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"document_id": str(result.document_id), "chunk_count": result.chunk_count, "status": "READY"}


@router.get("")
def list_documents(
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> list[dict]:
    context = tenant_context(principal, organization_id)
    from outbound_ai.db.connection import get_database

    with get_database().transaction(context) as connection:
        rows = connection.execute(
            """
            select id, title, mime_type, language, status, checksum, created_at, updated_at
            from public.knowledge_documents
            where organization_id = %s
            order by created_at desc limit 500
            """,
            (context.organization_id,),
        ).fetchall()
    return [dict(row) for row in rows]
