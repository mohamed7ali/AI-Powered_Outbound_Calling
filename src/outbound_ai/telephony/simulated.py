"""Deterministic local telephony adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from outbound_ai.telephony.base import OutboundCallRequest, OutboundCallResult


class SimulatedTelephony:
    """Creates fake call IDs without contacting a carrier."""

    def create_outbound_call(self, request: OutboundCallRequest) -> OutboundCallResult:
        return OutboundCallResult(
            provider="simulated",
            provider_call_id=f"SIM-{request.case_id}",
            status="QUEUED",
            created_at=datetime.now(UTC),
        )

    def build_voice_webhook_url(self, call_id: UUID) -> str:
        return f"/vonage/answer/{call_id}"
