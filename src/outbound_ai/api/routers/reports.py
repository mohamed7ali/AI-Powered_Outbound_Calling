"""Authenticated organization-scoped reporting endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from outbound_ai.api.auth import Principal, require_principal, tenant_context
from outbound_ai.db.connection import TenantContext
from outbound_ai.reports.agent import generate_reporting_article

router = APIRouter()


class FcrReportRequest(BaseModel):
    period_start: date
    period_end: date


@router.post("/fcr")
def fcr_report(
    request: FcrReportRequest,
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> dict:
    context: TenantContext = tenant_context(principal, organization_id)
    if context.actor_role not in {"PLATFORM_ADMIN", "ORG_ADMIN"}:
        raise HTTPException(status_code=403, detail="Organization administrator permission required")
    return generate_reporting_article(
        context=context,
        period_start=request.period_start,
        period_end=request.period_end,
    )
