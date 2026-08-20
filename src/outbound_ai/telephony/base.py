"""Provider-neutral telephony contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OutboundCallRequest:
    organization_id: UUID
    case_id: UUID
    call_id: UUID
    to_phone_e164: str
    greeting: str
    language: str = "ar-EG"


@dataclass(frozen=True, slots=True)
class OutboundCallResult:
    provider: str
    provider_call_id: str
    status: str
    created_at: datetime


class TelephonyPort(Protocol):
    """Outbound-call port used by the campaign service and graph."""

    def create_outbound_call(self, request: OutboundCallRequest) -> OutboundCallResult:
        """Start a call and return the provider call identifier."""

    def build_voice_webhook_url(self, call_id: UUID) -> str:
        """Return the absolute answer/TwiML callback URL."""
