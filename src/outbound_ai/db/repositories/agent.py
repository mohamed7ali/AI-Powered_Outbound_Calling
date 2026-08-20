"""Persistence for the human-agent knowledge assistant."""

from __future__ import annotations

import json
from uuid import UUID

from psycopg import Connection


def create_conversation(
    connection: Connection,
    *,
    organization_id: UUID,
    user_id: UUID,
    title: str | None = None,
) -> UUID:
    row = connection.execute(
        """
        insert into public.agent_conversations (organization_id, user_id, title)
        values (%s, %s, %s)
        returning id
        """,
        (organization_id, user_id, title),
    ).fetchone()
    if row is None:
        raise RuntimeError("Conversation was not created")
    return row["id"]


def conversation_belongs_to_actor(
    connection: Connection,
    *,
    conversation_id: UUID,
    organization_id: UUID,
    user_id: UUID,
) -> bool:
    row = connection.execute(
        """
        select 1
        from public.agent_conversations
        where id = %s and organization_id = %s and user_id = %s
        """,
        (conversation_id, organization_id, user_id),
    ).fetchone()
    return row is not None


def append_message(
    connection: Connection,
    *,
    organization_id: UUID,
    conversation_id: UUID,
    role: str,
    content: str,
    citations: list[dict] | None = None,
) -> UUID:
    if role not in {"user", "assistant", "system"}:
        raise ValueError("Unsupported message role")
    row = connection.execute(
        """
        insert into public.agent_messages
          (organization_id, conversation_id, role, content, citations)
        values (%s, %s, %s, %s, %s::jsonb)
        returning id
        """,
        (organization_id, conversation_id, role, content, json.dumps(citations or [])),
    ).fetchone()
    if row is None:
        raise RuntimeError("Message was not created")
    return row["id"]


def write_audit_event(
    connection: Connection,
    *,
    organization_id: UUID,
    actor_id: UUID,
    event_type: str,
    resource_type: str,
    resource_id: UUID | None,
    metadata: dict,
) -> UUID:
    row = connection.execute(
        """
        insert into public.audit_events
          (organization_id, actor_id, event_type, resource_type, resource_id, metadata)
        values (%s, %s, %s, %s, %s, %s::jsonb)
        returning id
        """,
        (
            organization_id,
            actor_id,
            event_type,
            resource_type,
            resource_id,
            json.dumps(metadata),
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("Audit event was not created")
    return row["id"]
