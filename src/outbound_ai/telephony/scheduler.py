"""Background scheduler for post-call follow-up campaigns."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from outbound_ai.config.settings import get_settings
from outbound_ai.db.connection import get_database
from outbound_ai.db.repositories.calls import attach_provider_call_id, create_call
from outbound_ai.db.repositories.followups import (
    claim_due_followups,
    retry_followup,
)
from outbound_ai.observability.logging import log_event
from outbound_ai.telephony.base import OutboundCallRequest
from outbound_ai.telephony.service import telephony_for_settings

logger = logging.getLogger(__name__)


def run_follow_up_cycle(*, limit: int = 20) -> dict[str, int]:
    """Run one bounded scheduler cycle; invoke repeatedly from a worker process."""

    settings = get_settings()
    database = get_database()
    with database.trusted_transaction() as connection:
        tasks = claim_due_followups(connection, limit=limit)

    dispatched = 0
    retried = 0
    failed = 0
    provider = telephony_for_settings(settings)
    for task in tasks:
        try:
            with database.trusted_transaction() as connection:
                call_id = create_call(
                    connection,
                    organization_id=task.organization_id,
                    case_id=task.case_id,
                    follow_up_task_id=task.id,
                    provider=settings.telephony_provider,
                )
            result = provider.create_outbound_call(
                OutboundCallRequest(
                    organization_id=task.organization_id,
                    case_id=task.case_id,
                    call_id=call_id,
                    to_phone_e164=task.phone_e164,
                    greeting=(
                        f"مرحباً. نتابع مع حضرتك بخصوص {task.subject}. "
                        "هل تم حل المشكلة؟"
                    ),
                )
            )
            with database.trusted_transaction() as connection:
                attach_provider_call_id(
                    connection,
                    call_id=call_id,
                    provider_call_id=result.provider_call_id,
                )
            # The task remains IN_PROGRESS until Vonage sends a terminal status
            # callback. This is essential for NO_ANSWER/BUSY retry handling.
            dispatched += 1
        except Exception as exc:  # provider failures must not kill the worker
            logger.exception("follow_up_dispatch_failed", extra={"task_id": str(task.id)})
            with database.trusted_transaction() as connection:
                retry_followup(
                    connection,
                    task_id=task.id,
                    attempt_number=task.attempt_number,
                )
            if task.attempt_number >= 3:
                failed += 1
            else:
                retried += 1
            log_event(
                logger,
                "follow_up_dispatch_failed",
                organization_id=str(task.organization_id),
                task_id=str(task.id),
                error_type=type(exc).__name__,
            )
    return {
        "claimed": len(tasks),
        "dispatched": dispatched,
        "completed": 0,
        "retried": retried,
        "failed": failed,
    }
