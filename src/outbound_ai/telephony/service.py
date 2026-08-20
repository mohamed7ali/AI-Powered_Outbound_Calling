"""Application service for starting outbound follow-up calls."""

from __future__ import annotations

from uuid import UUID

from outbound_ai.config.settings import Settings, get_settings
from outbound_ai.db.connection import TenantContext, get_database
from outbound_ai.db.repositories.calls import attach_provider_call_id, create_call
from outbound_ai.telephony.base import OutboundCallRequest, OutboundCallResult
from outbound_ai.telephony.simulated import SimulatedTelephony
from outbound_ai.telephony.vonage import VonageTelephony


def telephony_for_settings(settings: Settings):
    if settings.telephony_provider == "simulated":
        return SimulatedTelephony()
    if settings.telephony_provider == "vonage":
        return VonageTelephony(settings)
    raise ValueError(f"Unsupported telephony provider: {settings.telephony_provider}")


def start_follow_up_call(
    *,
    context: TenantContext,
    case_id: UUID,
    to_phone_e164: str,
    greeting: str,
    follow_up_task_id: UUID | None = None,
    settings: Settings | None = None,
) -> tuple[UUID, OutboundCallResult]:
    """Persist a call, originate it, and attach the provider call ID.

    The caller must already be authorized to place a call for the active tenant.
    The database transaction is committed before the external API call so a
    callback can always resolve the internal call row.
    """

    settings = settings or get_settings()
    database = get_database()
    with database.transaction(context) as connection:
        call_id = create_call(
            connection,
            organization_id=context.organization_id,
            case_id=case_id,
            follow_up_task_id=follow_up_task_id,
            provider=settings.telephony_provider,
        )

    provider = telephony_for_settings(settings)
    result = provider.create_outbound_call(
        OutboundCallRequest(
            organization_id=context.organization_id,
            case_id=case_id,
            call_id=call_id,
            to_phone_e164=to_phone_e164,
            greeting=greeting,
        )
    )

    with database.trusted_transaction() as connection:
        attach_provider_call_id(
            connection,
            call_id=call_id,
            provider_call_id=result.provider_call_id,
        )
    return call_id, result
