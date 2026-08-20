"""Platform and organization administration endpoints."""

from __future__ import annotations

import re
from uuid import UUID

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from outbound_ai.api.auth import Principal, require_principal, tenant_context
from outbound_ai.config.settings import get_settings
from outbound_ai.db.connection import get_database

router = APIRouter()
_SLUG = re.compile(r"[^a-z0-9-]+")


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=80)


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(default="AGENT", pattern="^(ORG_ADMIN|AGENT)$")


def _require_platform(principal: Principal) -> None:
    if not principal.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform administrator permission required")


def _supabase_headers(server_key: str) -> dict[str, str]:
    """Build headers for legacy service_role JWTs and new sb_secret keys."""

    headers = {"apikey": server_key, "Content-Type": "application/json"}
    if not server_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {server_key}"
    return headers


def _safe_provider_detail(response: requests.Response) -> str:
    try:
        body = response.json()
        message = body.get("msg") or body.get("message") or body.get("error_description") or body.get("error")
        if message:
            return str(message)[:240]
    except ValueError:
        pass
    return f"HTTP {response.status_code} from Supabase Auth"


@router.post("/organizations")
def create_organization(
    request: OrganizationCreateRequest,
    principal: Principal = Depends(require_principal),
) -> dict:
    _require_platform(principal)
    slug = _SLUG.sub("-", request.slug.lower()).strip("-")
    database = get_database()
    with database.trusted_transaction() as connection:
        row = connection.execute(
            "insert into public.organizations (name, slug) values (%s, %s) returning id, name, slug, is_active",
            (request.name.strip(), slug),
        ).fetchone()
    return dict(row)


@router.get("/{organization_id}/members")
def list_members(
    organization_id: UUID,
    principal: Principal = Depends(require_principal),
) -> list[dict]:
    context = tenant_context(principal, organization_id)
    if context.actor_role not in {"PLATFORM_ADMIN", "ORG_ADMIN"}:
        raise HTTPException(status_code=403, detail="Organization administrator permission required")
    with get_database().transaction(context) as connection:
        rows = connection.execute(
            """
            select m.user_id, p.full_name, p.phone, m.role, m.is_active, m.created_at
            from public.organization_memberships m
            left join public.profiles p on p.id = m.user_id
            where m.organization_id = %s order by m.created_at
            """,
            (organization_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/{organization_id}/invite")
def invite_member(
    organization_id: UUID,
    request: InviteRequest,
    principal: Principal = Depends(require_principal),
) -> dict:
    context = tenant_context(principal, organization_id)
    if context.actor_role not in {"PLATFORM_ADMIN", "ORG_ADMIN"}:
        raise HTTPException(status_code=403, detail="Organization administrator permission required")
    if context.actor_role != "PLATFORM_ADMIN" and request.role == "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Only platform administrators can create organization admins")

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=503, detail="Supabase server key configuration is missing")
    server_key = settings.supabase_service_role_key.get_secret_value()
    redirect_to = settings.auth_redirect_url.strip()
    if not redirect_to:
        raise HTTPException(
            status_code=503,
            detail="AUTH_REDIRECT_URL must be set to the public API password page before inviting users",
        )
    payload = {"email": request.email.strip(), "redirect_to": redirect_to}
    response = requests.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/invite",
        headers=_supabase_headers(server_key),
        json=payload,
        timeout=30,
    )
    if response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Supabase user invitation failed: {_safe_provider_detail(response)}",
        )
    try:
        user = response.json()
        user_id = UUID(str(user["id"]))
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Supabase returned no valid invited-user ID") from exc

    with get_database().transaction(context) as connection:
        connection.execute(
            """
            insert into public.organization_memberships (organization_id, user_id, role)
            values (%s, %s, %s::public.organization_member_role)
            on conflict (organization_id, user_id) do update set role = excluded.role, is_active = true
            """,
            (organization_id, user_id, request.role),
        )
    return {
        "user_id": str(user_id),
        "organization_id": str(organization_id),
        "role": request.role,
        "redirect_to": redirect_to,
    }
