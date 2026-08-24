"""Vonage Voice API answer, input, and event webhooks."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from outbound_ai.common.arabic import normalize_arabic
from outbound_ai.config.settings import get_settings
from outbound_ai.db.connection import get_database
from outbound_ai.db.repositories.calls import (
    find_call_by_id,
    mark_case_resolved_from_call,
    next_turn_number,
    record_call_turn,
    record_escalation,
    record_gather_turn,
    record_provider_event,
    update_call_outcome,
    update_call_status,
)
from outbound_ai.db.repositories.followups import settle_followup_after_call
from outbound_ai.telephony.local_voice import (
    audio_file_path,
    recording_file_path,
    synthesize_arabic,
    transcribe_arabic,
)
from outbound_ai.telephony.routing import FollowUpAction, decide_follow_up
from outbound_ai.telephony.vonage import VonageTelephony
from outbound_ai.telephony.prompts import (
    GREETING_TEXT,
    HANDOFF_TEXT,
    PROCESSING_TEXT,
    RESOLVED_TEXT,
    UNRESOLVED_TEXT,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_callback(request: Request, payload: dict) -> None:
    """Verify a signed Vonage callback using the account API signature secret.

    Vonage uses the application private key/public key pair for authenticating our
    outbound calls. Signed inbound webhooks use a separate account API signature
    secret and an HS256 JWT. Confusing these two credentials causes every callback
    to return 403, leaving calls stuck in INITIATED/PENDING.
    """

    settings = get_settings()
    if not settings.vonage_verify_webhooks:
        return
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Missing Vonage webhook signature")
    signature_secret = settings.vonage_signature_secret
    if signature_secret is None or not signature_secret.get_secret_value().strip():
        raise HTTPException(status_code=503, detail="VONAGE_SIGNATURE_SECRET is not configured")
    try:
        claims = jwt.decode(
            header.removeprefix("Bearer ").strip(),
            signature_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer="Vonage",
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


def _vonage_talk_action(text: str) -> dict:
    """Return a provider-managed Arabic TTS action with no local media dependency."""
    return {"action": "talk", "text": text, "language": "ar"}


def _talk_action(text: str) -> dict:
    """Return local streamed audio when enabled, otherwise Vonage TTS."""
    settings = get_settings()
    if settings.local_tts_enabled:
        audio_path = synthesize_arabic(text)
        base = (settings.local_voice_public_base_url or settings.public_webhook_base_url).rstrip("/")
        if not base.startswith("https://"):
            raise HTTPException(
                status_code=503,
                detail="LOCAL_VOICE_PUBLIC_BASE_URL or PUBLIC_WEBHOOK_BASE_URL must be HTTPS when local TTS is enabled",
            )
        return {
            "action": "stream",
            "streamUrl": [f"{base}/vonage/audio/{audio_path.name}"],
        }
    return {"action": "talk", "text": text, "language": "ar"}


def _speech_input_action(call_id: UUID) -> dict:
    settings = get_settings()
    return {
        "action": "input",
        "eventUrl": [f"{settings.public_webhook_base_url.rstrip('/')}/vonage/input/{call_id}"],
        "eventMethod": "POST",
        "type": ["speech"],
        "speech": {
            "language": "ar-EG",
            "endOnSilence": 1,
            "startTimeout": 10,
        },
    }


def _input_ncco(call_id: UUID) -> list[dict]:
    # Use the same native Arabic voice for retries in the non-local-STT path.
    return [_vonage_talk_action(UNRESOLVED_TEXT), _speech_input_action(call_id)]


def _recording_action(call_id: UUID) -> dict:
    settings = get_settings()
    base = settings.public_webhook_base_url.rstrip("/")
    return {
        "action": "record",
        "format": "wav",
        "endOnSilence": 5,
        "timeOut": 30,
        "beepStart": True,
        "eventUrl": [f"{base}/vonage/recording/{call_id}"],
        "eventMethod": "POST",
    }


def _answer_ncco(call_id: UUID) -> list[dict]:
    settings = get_settings()
    # Always use provider-managed TTS for the first greeting. The answer
    # webhook must return a playable action without waiting for local model
    # inference or depending on a locally generated WAV stream. Local TTS
    # remains available for later response audio after the customer speaks.
    greeting_action = _vonage_talk_action(GREETING_TEXT)
    if settings.local_stt_enabled:
        # Local Whisper needs the customer's audio recording, not Vonage ASR.
        return [
            greeting_action,
            _recording_action(call_id),
            {"action": "wait", "duration": 180},
        ]
    return [greeting_action, _speech_input_action(call_id)]


def _process_local_recording(call_id: UUID, payload: dict) -> None:
    """Download, transcribe, persist, and continue a local-STT call turn."""
    settings = get_settings()
    recording_url = str(payload.get("recording_url") or "").strip()
    if not recording_url:
        logger.warning("local_recording_missing_url call_id=%s", call_id)
        return
    try:
        call_database = get_database()
        with call_database.trusted_transaction() as connection:
            call = find_call_by_id(connection, call_id=call_id)
        if call is None or call["provider"] != "vonage":
            logger.warning("local_recording_call_not_found call_id=%s", call_id)
            return

        provider = VonageTelephony(settings)
        audio_path = recording_file_path(str(call_id))
        audio_path.write_bytes(provider.download_recording(recording_url))
        transcript = transcribe_arabic(audio_path)
        digits = ""
        speech = transcript.strip()
        raw_text = speech or "[NO_INPUT]"
        decision = decide_follow_up(digits=digits, speech=speech)

        with call_database.trusted_transaction() as connection:
            current_call = find_call_by_id(connection, call_id=call_id)
            if current_call is None:
                return
            turn_number = next_turn_number(connection, call_id=call_id)
            record_gather_turn(
                connection,
                organization_id=current_call["organization_id"],
                call_id=call_id,
                text_raw=raw_text,
                text_norm=normalize_arabic(speech) if speech else None,
                turn_number=turn_number,
                stt_model=f"faster-whisper:{settings.local_stt_model}",
                language="ar-EG",
                audio_path=audio_path.name,
            )
            ai_turn_number = turn_number + 1
            if decision.action == FollowUpAction.RESOLVED:
                response_text = RESOLVED_TEXT
                update_call_outcome(connection, call_id=call_id, outcome="ANSWERED_RESOLVED")
                mark_case_resolved_from_call(
                    connection, call_id=call_id, resolved_at=datetime.now(UTC)
                )
            else:
                response_text = HANDOFF_TEXT if decision.action == FollowUpAction.HUMAN_TASK else UNRESOLVED_TEXT
                update_call_outcome(connection, call_id=call_id, outcome="ESCALATED")
                record_escalation(
                    connection,
                    organization_id=current_call["organization_id"],
                    call_id=call_id,
                    reason=decision.reason,
                )
            record_call_turn(
                connection,
                organization_id=current_call["organization_id"],
                call_id=call_id,
                speaker="AI",
                text_raw=response_text,
                turn_number=ai_turn_number,
                language="ar-EG",
            )

        # Keep the same provider-managed voice as the greeting. Local MMS
        # audio remains available for offline testing, but is not used in the
        # live call path because it produced the inconsistent male voice.
        provider.modify_call(
            str(call["provider_call_id"]),
            [_vonage_talk_action(response_text)],
            region_url=str(payload.get("region_url") or "") or None,
        )
    except Exception:
        logger.exception("local_recording_processing_failed call_id=%s", call_id)


@router.get("/audio/{filename}")
def local_audio(filename: str) -> FileResponse:
    settings = get_settings()
    if not settings.local_tts_enabled:
        raise HTTPException(status_code=404, detail="Local TTS is disabled")
    try:
        path = audio_file_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid audio filename") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


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
    return JSONResponse(content=_answer_ncco(call_id))


@router.post("/recording/{call_id}")
async def recording_webhook(
    call_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
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
            provider_event_id=_event_id("recording", payload),
            event_type="RECORDING",
            payload=payload,
        )
    if get_settings().local_stt_enabled and payload.get("recording_url"):
        # The recording callback can arrive while the original wait action is
        # still active. Extend that window before starting CPU-bound Whisper
        # inference, otherwise the provider can end the call mid-processing.
        try:
            provider = VonageTelephony(get_settings())
            provider.modify_call(
                str(call["provider_call_id"]),
                [_vonage_talk_action(PROCESSING_TEXT), {"action": "wait", "duration": 180}],
                region_url=str(payload.get("region_url") or "") or None,
            )
        except Exception:
            logger.exception("local_recording_keepalive_failed call_id=%s", call_id)
        background_tasks.add_task(_process_local_recording, call_id, payload)
    return Response(status_code=204)


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
            mark_case_resolved_from_call(
                connection, call_id=call_id, resolved_at=datetime.now(UTC)
            )
            record_call_turn(
                connection,
                organization_id=call["organization_id"], call_id=call_id, speaker="AI",
                text_raw=RESOLVED_TEXT, turn_number=ai_turn_number, language="ar-EG",
            )
            return JSONResponse(content=[{"action": "talk", "text": RESOLVED_TEXT, "language": "ar"}])
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
            return JSONResponse(content=[{"action": "talk", "text": HANDOFF_TEXT, "language": "ar"}])
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
