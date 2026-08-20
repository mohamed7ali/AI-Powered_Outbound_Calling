"""Authenticated campaign and follow-up endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from outbound_ai.api.auth import Principal, require_principal, tenant_context
from outbound_ai.config.settings import get_settings
from outbound_ai.db.connection import get_database
from outbound_ai.db.repositories.calls import find_call_by_id, update_call_outcome, update_call_status
from outbound_ai.db.repositories.followups import retry_followup, settle_followup_after_call
from outbound_ai.telephony.service import start_follow_up_call

router = APIRouter()


class FollowUpCreateRequest(BaseModel):
    case_id: UUID
    scheduled_for: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ManualCallRequest(BaseModel):
    greeting: str = "مرحباً، بنتابع مع حضرتك للتأكد إن المشكلة اتحلت."


class SimulatedOutcomeRequest(BaseModel):
    outcome: str = Field(pattern="^(ANSWERED_RESOLVED|ESCALATED|NO_ANSWER|BUSY|FAILED)$")


def _context(principal: Principal, organization_id: UUID | None):
    return tenant_context(principal, organization_id)


@router.get("/customers")
def list_customers(
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> list[dict]:
    context = _context(principal, organization_id)
    with get_database().transaction(context) as connection:
        rows = connection.execute(
            """
            select id, full_name, phone_e164, preferred_language, created_at
            from public.customers where organization_id = %s
            order by created_at desc limit 500
            """,
            (context.organization_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/cases")
def list_cases(
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> list[dict]:
    context = _context(principal, organization_id)
    with get_database().transaction(context) as connection:
        rows = connection.execute(
            """
            select c.id, c.customer_id, cu.full_name as customer_name,
                   cu.phone_e164, c.assigned_agent_id, c.subject, c.description,
                   c.status, c.created_at, c.updated_at
            from public.support_cases c
            join public.customers cu on cu.id = c.customer_id
            where c.organization_id = %s
            order by c.updated_at desc limit 500
            """,
            (context.organization_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/followups")
def create_followup(
    request: FollowUpCreateRequest,
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> dict:
    context = _context(principal, organization_id)
    scheduled_for = request.scheduled_for.astimezone(UTC)
    with get_database().transaction(context) as connection:
        row = connection.execute(
            """
            insert into public.follow_up_tasks (organization_id, case_id, scheduled_for)
            select %s, c.id, %s
            from public.support_cases c
            where c.id = %s and c.organization_id = %s
            returning id, case_id, scheduled_for, status, attempt_number
            """,
            (context.organization_id, scheduled_for, request.case_id, context.organization_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Case not found in this organization")
    return dict(row)


@router.post("/calls/{call_id}/simulate-outcome")
def simulate_outcome(
    call_id: UUID,
    request: SimulatedOutcomeRequest,
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> dict:
    """Development-only terminal callback simulator; never available in Twilio mode."""

    settings = get_settings()
    if settings.telephony_provider != "simulated":
        raise HTTPException(status_code=404, detail="Simulation endpoint is disabled")
    context = _context(principal, organization_id)
    now = datetime.now(UTC)
    status_by_outcome = {
        "ANSWERED_RESOLVED": "COMPLETED",
        "ESCALATED": "COMPLETED",
        "NO_ANSWER": "NO_ANSWER",
        "BUSY": "BUSY",
        "FAILED": "FAILED",
    }
    with get_database().transaction(context) as connection:
        call = find_call_by_id(connection, call_id=call_id)
        if call is None or call["organization_id"] != context.organization_id:
            raise HTTPException(status_code=404, detail="Call not found")
        update_call_status(
            connection,
            call_id=call_id,
            status=status_by_outcome[request.outcome],
            ended_at=now,
        )
        update_call_outcome(connection, call_id=call_id, outcome=request.outcome)
        task_status = settle_followup_after_call(
            connection,
            task_id=call.get("follow_up_task_id"),
            outcome=request.outcome,
        )
    return {"call_id": str(call_id), "outcome": request.outcome, "follow_up_status": task_status}


@router.post("/followups/{task_id}/start")
def start_followup(
    task_id: UUID,
    request: ManualCallRequest,
    principal: Principal = Depends(require_principal),
    organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
) -> dict:
    context = _context(principal, organization_id)
    with get_database().transaction(context) as connection:
        row = connection.execute(
            """
            select f.id, f.case_id, f.status, f.attempt_number, cu.phone_e164, c.subject
            from public.follow_up_tasks f
            join public.support_cases c on c.id = f.case_id
            join public.customers cu on cu.id = c.customer_id
            where f.id = %s and f.organization_id = %s
            """,
            (task_id, context.organization_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Follow-up task not found")
        claimed = connection.execute(
            """
            update public.follow_up_tasks
            set status = 'IN_PROGRESS'
            where id = %s and organization_id = %s and status = 'PENDING'
            returning id
            """,
            (task_id, context.organization_id),
        ).fetchone()
        if claimed is None:
            current_status = str(row["status"])
            raise HTTPException(
                status_code=409,
                detail=f"Follow-up task is not pending; current status is {current_status}",
            )
    try:
        call_id, result = start_follow_up_call(
            context=context,
            case_id=row["case_id"],
            to_phone_e164=row["phone_e164"],
            greeting=request.greeting,
            follow_up_task_id=task_id,
        )
    except Exception as exc:
        with get_database().transaction(context) as connection:
            retry_followup(
                connection,
                task_id=task_id,
                attempt_number=int(row["attempt_number"]),
            )
        raise HTTPException(status_code=502, detail="Outbound call could not be created") from exc
    return {"call_id": str(call_id), "provider_call_id": result.provider_call_id, "status": result.status}
