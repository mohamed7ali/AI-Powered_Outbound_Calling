"""Call and provider-event persistence used by telephony adapters."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from psycopg import Connection


_TERMINAL_STATUSES = {"COMPLETED", "BUSY", "NO_ANSWER", "FAILED", "CANCELED"}


def create_call(
    connection: Connection,
    *,
    organization_id: UUID,
    case_id: UUID,
    follow_up_task_id: UUID | None,
    provider: str,
) -> UUID:
    """Create a queued call row; the caller must set the tenant context."""

    row = connection.execute(
        """
        insert into public.calls
          (organization_id, case_id, follow_up_task_id, provider)
        values (%s, %s, %s, %s)
        returning id
        """,
        (organization_id, case_id, follow_up_task_id, provider),
    ).fetchone()
    if row is None:
        raise RuntimeError("Call was not created")
    return row["id"]


def attach_provider_call_id(
    connection: Connection,
    *,
    call_id: UUID,
    provider_call_id: str,
) -> None:
    connection.execute(
        """
        update public.calls
        set provider_call_id = %s, status = 'INITIATED'
        where id = %s
        """,
        (provider_call_id, call_id),
    )


def find_call_by_id(connection: Connection, *, call_id: UUID) -> dict | None:
    return connection.execute(
        """
        select id, organization_id, case_id, follow_up_task_id, provider,
               provider_call_id, status, outcome
        from public.calls
        where id = %s
        limit 1
        """,
        (call_id,),
    ).fetchone()


def find_call_by_provider_id(
    connection: Connection,
    *,
    provider: str,
    provider_call_id: str,
) -> dict | None:
    """Resolve the internal call and organization from provider data only."""

    return connection.execute(
        """
        select id, organization_id, case_id, follow_up_task_id, provider,
               provider_call_id, status, outcome
        from public.calls
        where provider = %s and provider_call_id = %s
        limit 1
        """,
        (provider, provider_call_id),
    ).fetchone()


def record_provider_event(
    connection: Connection,
    *,
    organization_id: UUID,
    call_id: UUID,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload: dict,
) -> bool:
    """Insert a provider event once; return false for a duplicate callback."""

    row = connection.execute(
        """
        insert into public.call_events
          (organization_id, call_id, provider, provider_event_id, event_type, payload)
        values (%s, %s, %s, %s, %s, %s::jsonb)
        on conflict (provider, provider_event_id) do nothing
        returning id
        """,
        (
            organization_id,
            call_id,
            provider,
            provider_event_id,
            event_type,
            __import__("json").dumps(payload),
        ),
    ).fetchone()
    return row is not None


def update_call_status(
    connection: Connection,
    *,
    call_id: UUID,
    status: str,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    duration_seconds: int | None = None,
) -> None:
    """Update lifecycle timestamps; terminal callbacks are safe to repeat."""

    connection.execute(
        """
        update public.calls
        set status = %s,
            started_at = coalesce(started_at, %s),
            ended_at = coalesce(%s, ended_at),
            duration_seconds = coalesce(%s, duration_seconds)
        where id = %s
        """,
        (status, started_at, ended_at, duration_seconds, call_id),
    )


def update_call_outcome(connection: Connection, *, call_id: UUID, outcome: str) -> None:
    connection.execute(
        "update public.calls set outcome = %s::public.call_outcome where id = %s",
        (outcome, call_id),
    )


def mark_case_resolved_from_call(connection: Connection, *, call_id: UUID, resolved_at: datetime) -> None:
    """Mark the linked support case resolved after a confirmed resolved call."""
    connection.execute(
        """
        update public.support_cases as sc
        set status = 'RESOLVED'::public.case_status,
            resolved_at = coalesce(sc.resolved_at, %s),
            updated_at = %s
        from public.calls as c
        where c.id = %s and sc.id = c.case_id
        """,
        (resolved_at, resolved_at, call_id),
    )


def next_turn_number(connection: Connection, *, call_id: UUID) -> int:
    row = connection.execute(
        "select coalesce(max(turn_number) + 1, 0) as next_turn from public.call_turns where call_id = %s",
        (call_id,),
    ).fetchone()
    return int(row["next_turn"] if row else 0)


def record_escalation(
    connection: Connection,
    *,
    organization_id: UUID,
    call_id: UUID,
    reason: str,
) -> None:
    connection.execute(
        """
        insert into public.escalations (organization_id, call_id, reason)
        values (%s, %s, %s)
        """,
        (organization_id, call_id, reason),
    )


def record_call_turn(
    connection: Connection,
    *,
    organization_id: UUID,
    call_id: UUID,
    speaker: str,
    text_raw: str,
    text_norm: str | None = None,
    turn_number: int,
    language: str = "ar",
    stt_model: str | None = None,
) -> None:
    """Persist one AI or customer turn without retaining audio by default."""

    connection.execute(
        """
        insert into public.call_turns
          (organization_id, call_id, turn_number, speaker, text_raw, text_norm,
           language, stt_model)
        values (%s, %s, %s, %s::public.call_speaker, %s, %s, %s, %s)
        on conflict (call_id, turn_number) do update set
          speaker = excluded.speaker,
          text_raw = excluded.text_raw,
          text_norm = excluded.text_norm,
          language = excluded.language,
          stt_model = excluded.stt_model
        """,
        (
            organization_id,
            call_id,
            turn_number,
            speaker,
            text_raw,
            text_norm,
            language,
            stt_model,
        ),
    )


def record_gather_turn(
    connection: Connection,
    *,
    organization_id: UUID,
    call_id: UUID,
    text_raw: str,
    text_norm: str | None,
    turn_number: int,
    stt_model: str = "vonage-asr",
    language: str = "ar",
    audio_path: str | None = None,
) -> None:
    connection.execute(
        """
        insert into public.call_turns
          (organization_id, call_id, turn_number, speaker, text_raw, text_norm,
           language, stt_model, audio_path, audio_retained)
        values (%s, %s, %s, 'CUSTOMER', %s, %s, %s, %s, %s, %s)
        on conflict (call_id, turn_number) do update set
          text_raw = excluded.text_raw,
          text_norm = excluded.text_norm,
          language = excluded.language,
          stt_model = excluded.stt_model,
          audio_path = excluded.audio_path,
          audio_retained = excluded.audio_retained
        """,
        (
            organization_id,
            call_id,
            turn_number,
            text_raw,
            text_norm,
            language,
            stt_model,
            audio_path,
            bool(audio_path),
        ),
    )
