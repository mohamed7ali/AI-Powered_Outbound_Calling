"""Tenant-scoped pending escalation queries for the human-agent workspace."""

from __future__ import annotations

from uuid import UUID

from psycopg import Connection


_PENDING_STATUSES = ("PENDING", "IN_PROGRESS")


def list_open_escalations(
    connection: Connection,
    *,
    organization_id: UUID,
    limit: int = 100,
) -> list[dict]:
    """Return actionable unresolved-call escalations for one organization.

    RLS remains the final authorization boundary; the explicit organization
    predicate prevents accidental cross-tenant reads in the application layer.
    """

    rows = connection.execute(
        """
        select e.id as escalation_id,
               e.call_id,
               e.reason,
               e.status as escalation_status,
               e.assigned_human_id,
               e.created_at as escalated_at,
               c.case_id,
               c.outcome as call_outcome,
               c.status as call_status,
               cu.full_name as customer_name,
               cu.phone_e164,
               sc.subject,
               sc.description,
               coalesce(
                 (
                   select ct.text_raw
                   from public.call_turns ct
                   where ct.call_id = e.call_id
                     and ct.organization_id = e.organization_id
                   order by ct.turn_number desc
                   limit 1
                 ),
                 ''
               ) as latest_customer_message
        from public.escalations e
        join public.calls c
          on c.id = e.call_id
         and c.organization_id = e.organization_id
        join public.support_cases sc
          on sc.id = c.case_id
         and sc.organization_id = e.organization_id
        join public.customers cu
          on cu.id = sc.customer_id
         and cu.organization_id = e.organization_id
        where e.organization_id = %s
          and e.status = any(%s)
        order by e.created_at desc
        limit %s
        """,
        (organization_id, list(_PENDING_STATUSES), max(1, min(limit, 500))),
    ).fetchall()
    return [dict(row) for row in rows]


def close_escalation(
    connection: Connection,
    *,
    escalation_id: UUID,
    organization_id: UUID,
    assigned_human_id: UUID,
) -> bool:
    """Mark an escalation handled only within the active organization."""

    row = connection.execute(
        """
        update public.escalations
        set status = 'RESOLVED',
            assigned_human_id = %s,
            resolved_at = now()
        where id = %s
          and organization_id = %s
          and status = any(%s)
        returning id
        """,
        (assigned_human_id, escalation_id, organization_id, list(_PENDING_STATUSES)),
    ).fetchone()
    return row is not None


def serialize_escalation(row: dict) -> dict:
    """Make psycopg UUID/datetime values JSON-safe for API responses."""

    return {
        key: (str(value) if isinstance(value, UUID) else value.isoformat() if hasattr(value, "isoformat") else value)
        for key, value in row.items()
    }


__all__ = ["close_escalation", "list_open_escalations", "serialize_escalation"]

