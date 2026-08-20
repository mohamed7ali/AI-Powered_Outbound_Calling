"""Internal API endpoint for the human-agent RAG copilot."""

from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from outbound_ai.agents.kb_assist import answer_question
from outbound_ai.api.auth import require_principal, tenant_context
from outbound_ai.config.settings import get_settings
from outbound_ai.db.connection import TenantContext, get_database
from outbound_ai.db.repositories.escalations import (
    close_escalation,
    list_open_escalations,
    serialize_escalation,
)

router = APIRouter()


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    conversation_id: UUID | None = None


class EscalationResolveRequest(BaseModel):
    escalation_id: UUID


@router.get("/escalations")
def pending_escalations(
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> list[dict]:
    """List unresolved call escalations visible to the selected organization."""

    context = tenant_context(principal, organization_id)
    with get_database().transaction(context) as connection:
        rows = list_open_escalations(
            connection,
            organization_id=context.organization_id,
        )
    return [serialize_escalation(row) for row in rows]


@router.post("/escalations/resolve")
def resolve_escalation(
    request: EscalationResolveRequest,
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> dict[str, bool]:
    """Close one pending escalation without allowing cross-organization updates."""

    context = tenant_context(principal, organization_id)
    with get_database().transaction(context) as connection:
        updated = close_escalation(
            connection,
            escalation_id=request.escalation_id,
            organization_id=context.organization_id,
            assigned_human_id=context.actor_id,
        )
    if not updated:
        raise HTTPException(status_code=404, detail="Escalation not found or already resolved")
    return {"resolved": True}


@router.post("/query")
def query_agent(
    body: AgentQueryRequest,
    x_agent_token: str | None = Header(default=None),
    x_actor_id: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """Answer a question for an authenticated internal agent service.

    The current repository has not yet connected Supabase JWT middleware. Until
    that is added, this endpoint is intentionally disabled unless
    AGENT_INTERNAL_TOKEN is configured. Headers are therefore not a substitute
    for production Supabase Auth; they are a server-to-server integration seam.
    """

    settings = get_settings()
    if authorization and authorization.startswith("Bearer "):
        try:
            principal = require_principal(authorization)
            context = tenant_context(
                principal,
                UUID(x_organization_id) if x_organization_id else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid organization UUID") from exc
    else:
        if settings.agent_internal_token is None:
            raise HTTPException(status_code=503, detail="Agent API authentication is not configured")
        if not x_agent_token or not secrets.compare_digest(
            x_agent_token, settings.agent_internal_token.get_secret_value()
        ):
            raise HTTPException(status_code=401, detail="Invalid agent API token")
        if not x_actor_id or not x_organization_id:
            raise HTTPException(status_code=400, detail="Actor and organization context are required")
        try:
            context = TenantContext(
                actor_id=UUID(x_actor_id),
                organization_id=UUID(x_organization_id),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid actor or organization UUID") from exc

    result = answer_question(
        context=context,
        question=body.question,
        conversation_id=body.conversation_id,
        settings=settings,
    )
    return {
        "conversation_id": str(result.conversation_id),
        "answer": result.answer,
        "grounded": result.grounded,
        "used_llm": result.used_llm,
        "citations": [citation.as_dict() for citation in result.citations],
    }
