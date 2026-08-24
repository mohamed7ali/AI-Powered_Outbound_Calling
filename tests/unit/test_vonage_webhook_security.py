from __future__ import annotations

from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from outbound_ai.api.routers import vonage
from outbound_ai.config.settings import Settings


def _request_with_authorization(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/vonage/event/test",
            "headers": [(b"authorization", f"Bearer {token}".encode("ascii"))],
        }
    )


def test_signed_vonage_callback_uses_signature_secret(monkeypatch) -> None:
    secret = "test-vonage-signature-secret-32-bytes-minimum"
    application_id = str(uuid4())
    settings = Settings(
        vonage_verify_webhooks=True,
        vonage_signature_secret=secret,
        vonage_application_id=application_id,
    )
    token = jwt.encode(
        {
            "iss": "Vonage",
            "iat": 1_700_000_000,
            "jti": str(uuid4()),
            "api_key": "test-api-key",
            "application_id": application_id,
        },
        secret,
        algorithm="HS256",
    )
    monkeypatch.setattr(vonage, "get_settings", lambda: settings)

    vonage._verify_callback(_request_with_authorization(token), {"status": "started"})


def test_signed_vonage_callback_requires_signature_secret(monkeypatch) -> None:
    settings = Settings(vonage_verify_webhooks=True, vonage_signature_secret=None)
    token = jwt.encode({"iss": "Vonage"}, "unused-vonage-signature-secret-32-bytes", algorithm="HS256")
    monkeypatch.setattr(vonage, "get_settings", lambda: settings)

    with pytest.raises(HTTPException) as exc_info:
        vonage._verify_callback(_request_with_authorization(token), {})

    assert exc_info.value.status_code == 503
    assert "VONAGE_SIGNATURE_SECRET" in str(exc_info.value.detail)
