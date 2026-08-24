"""Vonage Voice API outbound-call adapter.

The adapter creates the call only. Vonage retrieves the NCCO from the answer URL,
posts input events to the input URL, and posts lifecycle events to the event URL.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import urljoin

import httpx
import jwt

from outbound_ai.config.settings import PROJECT_ROOT, Settings, get_settings
from outbound_ai.telephony.base import OutboundCallRequest, OutboundCallResult


class VonageConfigurationError(RuntimeError):
    """Raised when Vonage live calling is requested without valid configuration."""


def _phone_number(value: str) -> str:
    """Vonage examples use E.164 digits without the leading plus sign."""

    normalized = value.strip().replace(" ", "").replace("-", "")
    if normalized.startswith("+"):
        normalized = normalized[1:]
    if not normalized.isdigit():
        raise ValueError("Vonage phone numbers must be E.164 digits")
    return normalized


class VonageTelephony:
    provider_name = "vonage"
    api_url = "https://api.nexmo.com/v1/calls"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.vonage_application_id:
            raise VonageConfigurationError("VONAGE_APPLICATION_ID is required")
        if not self.settings.vonage_from_number:
            raise VonageConfigurationError("VONAGE_FROM_NUMBER is required")
        if not self.settings.public_webhook_base_url.startswith("https://"):
            raise VonageConfigurationError(
                "PUBLIC_WEBHOOK_BASE_URL must be an absolute HTTPS URL for live Vonage callbacks"
            )
        self.private_key_path = self._resolve_path(self.settings.vonage_private_key_path)
        if not self.private_key_path.is_file():
            raise VonageConfigurationError(
                f"VONAGE_PRIVATE_KEY_PATH does not point to a readable file: {self.private_key_path}"
            )

    @property
    def base_url(self) -> str:
        return self.settings.public_webhook_base_url.rstrip("/") + "/"

    def _resolve_path(self, value: Path) -> Path:
        path = value
        if str(path) in {"", "."}:
            return PROJECT_ROOT / "private.key"
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def _jwt(self) -> str:
        now = int(time.time())
        claims = {
            "application_id": self.settings.vonage_application_id,
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid4()),
        }
        return jwt.encode(
            claims,
            self.private_key_path.read_text(encoding="utf-8"),
            algorithm="RS256",
        )

    def build_voice_webhook_url(self, call_id: UUID) -> str:
        return urljoin(self.base_url, f"vonage/answer/{call_id}")

    def build_input_webhook_url(self, call_id: UUID) -> str:
        return urljoin(self.base_url, f"vonage/input/{call_id}")

    def build_event_webhook_url(self, call_id: UUID) -> str:
        return urljoin(self.base_url, f"vonage/event/{call_id}")

    def modify_call(
        self,
        provider_call_id: str,
        ncco: list[dict],
        *,
        region_url: str | None = None,
    ) -> None:
        """Replace the NCCO of an active call with a new NCCO sequence."""
        base = (region_url or "https://api.nexmo.com").rstrip("/")
        url = f"{base}/v1/calls/{provider_call_id}"
        response = httpx.put(
            url,
            headers={"Authorization": f"Bearer {self._jwt()}"},
            json={
                "action": "transfer",
                "destination": {"type": "ncco", "ncco": ncco},
            },
            timeout=20.0,
        )
        if response.is_error:
            raise RuntimeError(
                f"Vonage call update failed with HTTP {response.status_code}: {response.text[:500]}"
            )

    def download_recording(self, recording_url: str) -> bytes:
        """Download a Vonage recording using the application JWT."""
        response = httpx.get(
            recording_url,
            headers={"Authorization": f"Bearer {self._jwt()}"},
            timeout=60.0,
        )
        if response.is_error:
            raise RuntimeError(
                f"Vonage recording download failed with HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )
        return response.content

    def create_outbound_call(self, request: OutboundCallRequest) -> OutboundCallResult:
        payload = {
            "to": [{"type": "phone", "number": _phone_number(request.to_phone_e164)}],
            "from": {"type": "phone", "number": _phone_number(self.settings.vonage_from_number)},
            "answer_url": [self.build_voice_webhook_url(request.call_id)],
            "answer_method": "POST",
            "event_url": [self.build_event_webhook_url(request.call_id)],
            "event_method": "POST",
        }
        response = httpx.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self._jwt()}"},
            json=payload,
            timeout=20.0,
        )
        if response.is_error:
            raise RuntimeError(
                f"Vonage outbound call failed with HTTP {response.status_code}: {response.text[:500]}"
            )
        body = response.json()
        call_uuid = body.get("uuid")
        if not call_uuid:
            raise RuntimeError("Vonage response did not include a call UUID")
        return OutboundCallResult(
            provider=self.provider_name,
            provider_call_id=str(call_uuid),
            status="QUEUED",
            created_at=datetime.now(UTC),
        )
