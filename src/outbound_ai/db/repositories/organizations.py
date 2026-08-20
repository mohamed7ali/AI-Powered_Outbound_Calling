"""Organization and membership queries.

These functions are intentionally small. They are the only application layer that
should issue SQL for organization hierarchy operations. Higher layers pass a
TenantContext and do not build SQL strings themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from psycopg import Connection

from outbound_ai.db.connection import TenantContext


@dataclass(frozen=True, slots=True)
class Organization:
    id: UUID
    name: str
    slug: str
    is_active: bool


def list_visible_organizations(connection: Connection) -> list[Organization]:
    """Return only organizations allowed by the current actor's RLS context."""

    rows = connection.execute(
        """
        select id, name, slug, is_active
        from public.organizations
        where is_active = true
        order by name
        """
    ).fetchall()
    return [Organization(**row) for row in rows]


def create_organization(
    connection: Connection,
    *,
    name: str,
    slug: str,
) -> Organization:
    """Create an organization; RLS permits this only for platform admins."""

    row = connection.execute(
        """
        insert into public.organizations (name, slug)
        values (%s, %s)
        returning id, name, slug, is_active
        """,
        (name.strip(), slug.strip().lower()),
    ).fetchone()
    if row is None:
        raise RuntimeError("Organization was not created")
    return Organization(**row)


def add_membership(
    connection: Connection,
    *,
    organization_id: UUID,
    user_id: UUID,
    role: str,
) -> None:
    """Add an admin or agent; RLS limits who may assign each role."""

    connection.execute(
        """
        insert into public.organization_memberships (organization_id, user_id, role)
        values (%s, %s, %s::public.organization_member_role)
        on conflict (organization_id, user_id)
        do update set role = excluded.role, is_active = true
        """,
        (organization_id, user_id, role),
    )
