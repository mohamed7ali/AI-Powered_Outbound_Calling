from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from outbound_ai.api.routers.vonage import _input_text
from outbound_ai.config.settings import Settings
from outbound_ai.telephony.base import OutboundCallRequest
from outbound_ai.telephony.vonage import VonageTelephony, _phone_number


def test_vonage_phone_number_normalization() -> None:
    assert _phone_number("+44 7348 450153") == "447348450153"
    assert _phone_number("2010-1234-5678") == "201012345678"


def test_vonage_input_parser_supports_dtmf_and_speech() -> None:
    digits, speech = _input_text(
        {
            "dtmf": {"digits": "2", "timed_out": False},
            "speech": {"results": [{"confidence": "0.9", "text": "لسه المشكلة موجودة"}]},
        }
    )
    assert digits == "2"
    assert speech == "لسه المشكلة موجودة"


def test_vonage_provider_creates_nexmo_call(monkeypatch, tmp_path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = tmp_path / "private.key"
    key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    settings = Settings(
        vonage_application_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        vonage_private_key_path=key_path,
        vonage_from_number="+447700900000",
        public_webhook_base_url="https://example.test",
        telephony_provider="vonage",
    )
    captured: dict = {}

    class FakeResponse:
        status_code = 201
        text = '{"uuid":"call-uuid"}'

        is_error = False

        def json(self) -> dict:
            return {"uuid": "call-uuid"}

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("outbound_ai.telephony.vonage.httpx.post", fake_post)
    provider = VonageTelephony(settings)
    call_id = uuid4()
    result = provider.create_outbound_call(
        OutboundCallRequest(
            organization_id=uuid4(),
            case_id=uuid4(),
            call_id=call_id,
            to_phone_e164="+201012345678",
            greeting="مرحباً",
        )
    )
    assert result.provider == "vonage"
    assert result.provider_call_id == "call-uuid"
    assert captured["url"] == "https://api.nexmo.com/v1/calls"
    assert captured["json"]["to"] == [{"type": "phone", "number": "201012345678"}]
    assert captured["json"]["from"] == {"type": "phone", "number": "447700900000"}
    assert captured["json"]["answer_method"] == "POST"
    assert f"/vonage/answer/{call_id}" in captured["json"]["answer_url"][0]
    assert captured["headers"]["Authorization"].startswith("Bearer ")
