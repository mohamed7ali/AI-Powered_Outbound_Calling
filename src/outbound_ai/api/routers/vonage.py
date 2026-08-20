"""Vonage Voice API answer, input, and event webhooks."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from outbound_ai.common.arabic import normalize_arabic
from outbound_ai.config.settings import PROJECT_ROOT, get_settings
from outbound_ai.db.connection import get_database
from outbound_ai.db.repositories.calls import (
    find_call_by_id,
    next_turn_number,
    record_call_turn,
    record_escalation,
    record_gather_turn,
    record_provider_event,
    update_call_outcome,
    update_call_status,
)
from outbound_ai.db.repositories.followups import settle_followup_after_call
from outbound_ai.telephony.routing import FollowUpAction, decide_follow_up
from outbound_ai.telephony.prompts import (
    GREETING_TEXT,
    HANDOFF_TEXT,
    RESOLVED_TEXT,
    UNRESOLVED_TEXT,
)

router = APIRouter()


def _public_key_path() -> Path:
    value = get_settings().vonage_public_key_path
    if not str(value):
        return PROJECT_ROOT / "public.key"
    return value if value.is_absolute() else PROJECT_ROOT / value


def _verify_callback(request: Request, payload: dict) -> None:
    settings = get_settings()
    if not settings.vonage_verify_webhooks:
        return
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Missing Vonage webhook signature")
    public_key = _public_key_path()
    if not public_key.is_file():
        raise HTTPException(status_code=503, detail="VONAGE_PUBLIC_KEY_PATH is not configured")
    try:
        claims = jwt.decode(
            header.removeprefix("Bearer ").strip(),
            public_key.read_text(encoding="utf-8"),
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=403, detail="Invalid Vonage webhook signature") from exc
    application_id = claims.get("application_id")
    if application_id and application_id != settings.vonage_application_id:
        raise HTTPException(status_code=403, detail="Vonage webhook application mismatch")


def _event_id(kind: str, payload: dict) -> str:
    provider_uuid = str(payload.get("uuid") or payload.get("conversation_uuid") or "unknown")
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:24]
    return f"{kind}:{provider_uuid}:{digest}"


def _json_payload(request: Request, payload: dict):
    return JSONResponse(content=payload)


async def _read_payload(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    form = await request.form()
    return dict(form)


def _input_text(payload: dict) -> tuple[str, str]:
    dtmf = payload.get("dtmf") or {}
    if isinstance(dtmf, dict):
        digits = str(dtmf.get("digits") or "").strip()
    else:
        digits = str(dtmf).strip()
    speech_obj = payload.get("speech") or {}
    speech = ""
    if isinstance(speech_obj, dict):
        results = speech_obj.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                speech = str(first.get("text") or first.get("transcript") or "").strip()
        if not speech:
            speech = str(speech_obj.get("text") or speech_obj.get("transcript") or "").strip()
    else:
        speech = str(speech_obj).strip()
    return digits, speech


def _input_ncco(call_id: UUID) -> list[dict]:
    settings = get_settings()
    base = settings.public_webhook_base_url.rstrip("/")
    input_url = f"{base}/vonage/input/{call_id}"
    return [
        {
            "action": "talk",
            "text": UNRESOLVED_TEXT,
            "language": "ar-EG",
        },
        {
            "action": "input",
            "eventUrl": [input_url],
            "eventMethod": "POST",
            "type": ["dtmf", "speech"],
            "dtmf": {"maxDigits": 1, "timeOut": 5},
            "speech": {"language": "ar-EG", "endOnSilence": 1},
        },
    ]


@router.post("/answer/{call_id}")
async def answer_webhook(call_id: UUID, request: Request) -> JSONResponse:
    payload = await _read_payload(request)
    _verify_callback(request, payload)
    database = get_database()
    with database.trusted_transaction() as connection:
        call = find_call_by_id(connection, call_id=call_id)
        if call is None or call["provider"] != "vonage":
            raise HTTPException(status_code=404, detail="Call not found")
        record_provider_event(
            connection,
            organization_id=call["organization_id"],
            call_id=call_id,
            provider="vonage",
            provider_event_id=_event_id("answer", payload),
            event_type="ANSWER",
            payload=payload,
        )
        record_call_turn(
            connection,
            organization_id=call["organization_id"],
            call_id=call_id,
            speaker="AI",
            text_raw=GREETING_TEXT,
            turn_number=0,
            language="ar-EG",
        )
    return JSONResponse(
        content=[
            {"action": "talk", "text": GREETING_TEXT, "language": "ar-EG"},
            {
                "action": "input",
                "eventUrl": [f"{get_settings().public_webhook_base_url.rstrip('/')}/vonage/input/{call_id}"],
                "eventMethod": "POST",
                "type": ["dtmf", "speech"],
                "dtmf": {"maxDigits": 1, "timeOut": 5},
                "speech": {"language": "ar-EG", "endOnSilence": 1},
            },
        ]
    )


@router.post("/input/{call_id}")
async def input_webhook(call_id: UUID, request: Request) -> JSONResponse:
    payload = await _read_payload(request)
    _verify_callback(request, payload)
    digits, speech = _input_text(payload)
    database = get_database()
    with database.trusted_transaction() as connection:
        call = find_call_by_id(connection, call_id=call_id)
        provider_uuid = str(payload.get("uuid") or "")
        if call is None or call["provider"] != "vonage":
            raise HTTPException(status_code=404, detail="Call not found")
        if provider_uuid and call["provider_call_id"] != provider_uuid:
            raise HTTPException(status_code=404, detail="Call provider ID mismatch")
        turn_number = next_turn_number(connection, call_id=call_id)
        raw_text = speech or (f"DTMF:{digits}" if digits else "")
        if record_provider_event(
            connection,
            organization_id=call["organization_id"],
            call_id=call_id,
            provider="vonage",
            provider_event_id=_event_id("input", payload),
            event_type="INPUT",
            payload=payload,
        ):
            record_gather_turn(
                connection,
                organization_id=call["organization_id"],
                call_id=call_id,
                text_raw=raw_text or "[NO_INPUT]",
                text_norm=normalize_arabic(raw_text) if raw_text else None,
                turn_number=turn_number,
            )
        decision = decide_follow_up(digits=digits, speech=speech)
        ai_turn_number = turn_number + 1
        if decision.action == FollowUpAction.RESOLVED:
            update_call_outcome(connection, call_id=call_id, outcome="ANSWERED_RESOLVED")
            record_call_turn(
                connection,
                organization_id=call["organization_id"], call_id=call_id, speaker="AI",
                text_raw=RESOLVED_TEXT, turn_number=ai_turn_number, language="ar-EG",
            )
            return JSONResponse(content=[{"action": "talk", "text": RESOLVED_TEXT, "language": "ar-EG"}])
        update_call_outcome(connection, call_id=call_id, outcome="ESCALATED")
        record_escalation(
            connection,
            organization_id=call["organization_id"], call_id=call_id, reason=decision.reason,
        )
        response_text = HANDOFF_TEXT if decision.action == FollowUpAction.HUMAN_TASK else UNRESOLVED_TEXT
        record_call_turn(
            connection,
            organization_id=call["organization_id"], call_id=call_id, speaker="AI",
            text_raw=response_text, turn_number=ai_turn_number, language="ar-EG",
        )
        if decision.action == FollowUpAction.HUMAN_TASK:
            return JSONResponse(content=[{"action": "talk", "text": HANDOFF_TEXT, "language": "ar-EG"}])
    return JSONResponse(content=_input_ncco(call_id))


@router.post("/event/{call_id}")
async def event_webhook(call_id: UUID, request: Request) -> JSONResponse:
    payload = await _read_payload(request)
    _verify_callback(request, payload)
    status = str(payload.get("status") or "").strip().lower()
    if not status:
        return JSONResponse(content={"ok": True})
    status_map = {
        "started": "INITIATED",
        "ringing": "RINGING",
        "answered": "ANSWERED",
        "completed": "COMPLETED",
        "disconnected": "COMPLETED",
        "busy": "BUSY",
        "unanswered": "NO_ANSWER",
        "timeout": "NO_ANSWER",
        "failed": "FAILED",
        "rejected": "FAILED",
        "cancelled": "CANCELED",
    }
    internal_status = status_map.get(status, status.upper())
    database = get_database()
    now = datetime.now(UTC)
    with database.trusted_transaction() as connection:
        call = find_call_by_id(connection, call_id=call_id)
        provider_uuid = str(payload.get("uuid") or "")
        if call is None or call["provider"] != "vonage":
            raise HTTPException(status_code=404, detail="Call not found")
        if provider_uuid and call["provider_call_id"] != provider_uuid:
            raise HTTPException(status_code=404, detail="Call provider ID mismatch")
        if not record_provider_event(
            connection,
            organization_id=call["organization_id"], call_id=call_id, provider="vonage",
            provider_event_id=_event_id("event", payload), event_type=status.upper(), payload=payload,
        ):
            return JSONResponse(content={"ok": True, "duplicate": True})
        duration_value = payload.get("duration")
        duration = int(duration_value) if str(duration_value or "").isdigit() else None
        update_call_status(
            connection,
            call_id=call_id,
            status=internal_status,
            started_at=now if internal_status in {"INITIATED", "RINGING", "ANSWERED"} else None,
            ended_at=now if internal_status in {"COMPLETED", "BUSY", "NO_ANSWER", "FAILED", "CANCELED"} else None,
            duration_seconds=duration,
        )
        outcome = {"NO_ANSWER": "NO_ANSWER", "BUSY": "BUSY", "FAILED": "FAILED"}.get(internal_status)
        if outcome:
            update_call_outcome(connection, call_id=call_id, outcome=outcome)
            settle_followup_after_call(connection, task_id=call.get("follow_up_task_id"), outcome=outcome)
        elif internal_status == "COMPLETED" and call.get("outcome") in {"ANSWERED_RESOLVED", "ESCALATED"}:
            settle_followup_after_call(
                connection, task_id=call.get("follow_up_task_id"), outcome=str(call["outcome"])
            )
    return JSONResponse(content={"ok": True})
