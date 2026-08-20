"""Claiming and retrying scheduled follow-up tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from psycopg import Connection


@dataclass(frozen=True, slots=True)
class DueFollowUp:
    id: UUID
    organization_id: UUID
    case_id: UUID
    customer_id: UUID
    phone_e164: str
    subject: str
    description: str
    attempt_number: int


def claim_due_followups(connection: Connection, *, limit: int = 20) -> list[DueFollowUp]:
    """Claim due tasks atomically using row locks and a status transition."""

    rows = connection.execute(
        """
        select f.id, f.organization_id, f.case_id, c.customer_id,
               cu.phone_e164, c.subject, c.description, f.attempt_number
        from public.follow_up_tasks f
        join public.support_cases c on c.id = f.case_id
        join public.customers cu on cu.id = c.customer_id
        where f.status = 'PENDING'
          and f.scheduled_for <= now()
        order by f.scheduled_for, f.created_at
        for update of f skip locked
        limit %s
        """,
        (max(1, min(limit, 100)),),
    ).fetchall()
    if not rows:
        return []
    ids = [row["id"] for row in rows]
    connection.execute(
        "update public.follow_up_tasks set status = 'IN_PROGRESS' where id = any(%s)",
        (ids,),
    )
    return [DueFollowUp(**row) for row in rows]


def complete_followup(connection: Connection, *, task_id: UUID) -> None:
    connection.execute(
        """
        update public.follow_up_tasks
        set status = 'COMPLETED', completed_at = now()
        where id = %s
        """,
        (task_id,),
    )


def settle_followup_after_call(
    connection: Connection,
    *,
    task_id: UUID | None,
    outcome: str,
    max_attempts: int = 3,
) -> str:
    """Settle a dispatched task after its provider outcome is known.

    A task is completed only after a call reaches a meaningful terminal outcome.
    Provider delivery failures and no-answer outcomes remain retryable until the
    configured attempt limit is reached. Repeated callbacks are harmless because
    already terminal task rows are left unchanged.
    """

    if task_id is None:
        return "NO_TASK"
    row = connection.execute(
        """
        select status, attempt_number
        from public.follow_up_tasks
        where id = %s
        for update
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        return "MISSING"
    if row["status"] in {"COMPLETED", "FAILED"}:
        return str(row["status"])
    if outcome in {"NO_ANSWER", "BUSY", "FAILED"}:
        retry_followup(
            connection,
            task_id=task_id,
            attempt_number=int(row["attempt_number"]),
            max_attempts=max_attempts,
        )
        return "FAILED" if int(row["attempt_number"]) >= max_attempts else "PENDING"
    complete_followup(connection, task_id=task_id)
    return "COMPLETED"


def retry_followup(
    connection: Connection,
    *,
    task_id: UUID,
    attempt_number: int,
    max_attempts: int = 3,
) -> None:
    if attempt_number >= max_attempts:
        connection.execute(
            "update public.follow_up_tasks set status = 'FAILED' where id = %s",
            (task_id,),
        )
        return
    delay = timedelta(minutes=15 * (2 ** max(0, attempt_number - 1)))
    connection.execute(
        """
        update public.follow_up_tasks
        set status = 'PENDING', attempt_number = attempt_number + 1,
            scheduled_for = %s
        where id = %s
        """,
        (datetime.now(UTC) + delay, task_id),
    )
