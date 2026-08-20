"""Supabase JWT verification and hierarchy-aware tenant resolution."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException, status

from outbound_ai.config.settings import get_settings
from outbound_ai.db.connection import TenantContext, get_database


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    is_platform_admin: bool
    role: str | None


def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        import jwt
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=500, detail="JWT verification dependency is unavailable") from exc

    options = {"verify_aud": bool(settings.supabase_jwt_audience)}
    if settings.supabase_jwt_secret:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else None,
            options=options,
        )
    if not settings.supabase_url:
        raise HTTPException(status_code=500, detail="Supabase JWT verification is not configured")
    jwks_client = jwt.PyJWKClient(f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=settings.supabase_jwt_audience,
        issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
        options=options,
    )


def require_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        claims = _decode_token(authorization.removeprefix("Bearer ").strip())
        user_id = UUID(str(claims["sub"]))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    database = get_database()
    with database.trusted_transaction() as connection:
        platform_row = connection.execute(
            "select 1 from public.platform_admins where user_id = %s",
            (user_id,),
        ).fetchone()
        membership = connection.execute(
            """
            select organization_id, role::text as role
            from public.organization_memberships
            where user_id = %s and is_active = true
            order by created_at
            limit 1
            """,
            (user_id,),
        ).fetchone()
    return Principal(
        user_id=user_id,
        is_platform_admin=platform_row is not None,
        role=membership["role"] if membership else None,
    )


def tenant_context(principal: Principal, organization_id: UUID | None) -> TenantContext:
    """Resolve the requested org only after checking membership or platform-admin status."""

    if organization_id is None:
        raise HTTPException(status_code=400, detail="X-Organization-Id is required")
    database = get_database()
    active_role = "PLATFORM_ADMIN" if principal.is_platform_admin else None
    with database.trusted_transaction() as connection:
        if principal.is_platform_admin:
            exists = connection.execute(
                "select 1 from public.organizations where id = %s and is_active = true",
                (organization_id,),
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="Organization not found")
        else:
            membership = connection.execute(
                """
                select role::text as role from public.organization_memberships
                where organization_id = %s and user_id = %s and is_active = true
                """,
                (organization_id, principal.user_id),
            ).fetchone()
            if membership is None:
                raise HTTPException(status_code=403, detail="Not a member of this organization")
            active_role = membership["role"]
    return TenantContext(
        actor_id=principal.user_id,
        organization_id=organization_id,
        actor_role=active_role,
    )
