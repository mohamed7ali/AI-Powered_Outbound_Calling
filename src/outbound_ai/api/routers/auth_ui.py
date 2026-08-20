"""Browser-facing invitation acceptance and password setup page."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from outbound_ai.api.auth import Principal, require_principal
from outbound_ai.config.settings import get_settings
from outbound_ai.db.connection import get_database

router = APIRouter()


class PasswordSetupRequest(BaseModel):
    # Token length is provider-dependent; Supabase validates the token below.
    # Keep only a non-empty constraint here so provider changes do not produce
    # an opaque FastAPI 422 before the real Auth error is returned.
    access_token: str = Field(min_length=1, max_length=10000)
    refresh_token: str = Field(min_length=1, max_length=10000)
    password: str = Field(min_length=8, max_length=128)


@router.get("/session")
def session_info(principal: Principal = Depends(require_principal)) -> dict:
    """Return the organizations visible to the authenticated principal."""

    with get_database().trusted_transaction() as connection:
        if principal.is_platform_admin:
            rows = connection.execute(
                """
                select id, name, slug, 'PLATFORM_ADMIN'::text as role
                from public.organizations where is_active = true order by name
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                select o.id, o.name, o.slug, m.role::text as role
                from public.organization_memberships m
                join public.organizations o on o.id = m.organization_id
                where m.user_id = %s and m.is_active = true and o.is_active = true
                order by o.name
                """,
                (principal.user_id,),
            ).fetchall()
    return {
        "user_id": str(principal.user_id),
        "is_platform_admin": principal.is_platform_admin,
        "memberships": [
            {"id": str(row["id"]), "name": row["name"], "slug": row["slug"], "role": row["role"]}
            for row in rows
        ],
    }


@router.get("/invite", response_class=HTMLResponse)
def invitation_page() -> str:
    """Render a minimal branded page; the access token stays in the URL fragment."""

    return """
    <!doctype html>
    <html lang="ar" dir="rtl">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>إكمال حسابك | منصة المتابعة الذكية</title>
      <style>
        :root { color-scheme: dark; font-family: Cairo, Arial, sans-serif; }
        body { margin: 0; min-height: 100vh; display: grid; place-items: center;
               background: #08111f; color: #e8eef7; }
        main { width: min(92vw, 460px); padding: 34px; border: 1px solid #26364e;
                border-radius: 20px; background: #101c2e; box-shadow: 0 20px 70px #0005; }
        h1 { margin: 0 0 10px; font-size: 26px; }
        p { color: #9fb0c7; line-height: 1.8; }
        label { display: block; margin-top: 18px; color: #c8d5e6; }
        input { box-sizing: border-box; width: 100%; margin-top: 7px; padding: 13px;
                border: 1px solid #38506f; border-radius: 10px; background: #0b1524;
                color: #fff; font-size: 16px; }
        button { width: 100%; margin-top: 24px; padding: 13px; border: 0; border-radius: 10px;
                 background: #38bdf8; color: #062033; font-weight: 700; font-size: 16px; cursor: pointer; }
        #status { min-height: 28px; margin-top: 18px; }
        .ok { color: #65e6a5; } .error { color: #ff8f9c; }
      </style>
    </head>
    <body>
      <main>
        <h1>إكمال حسابك</h1>
        <p>أنشئ كلمة مرور لحسابك ثم افتح مكتب خدمة العملاء باللغة العربية.</p>
        <form id="form">
          <label>كلمة المرور الجديدة
            <input id="password" type="password" minlength="8" required autocomplete="new-password" />
          </label>
          <label>تأكيد كلمة المرور
            <input id="confirm" type="password" minlength="8" required autocomplete="new-password" />
          </label>
          <button type="submit">حفظ كلمة المرور</button>
        </form>
        <div id="status"></div>
      </main>
      <script>
        const status = document.getElementById('status');
        const params = new URLSearchParams(window.location.search);
        const hash = new URLSearchParams(window.location.hash.slice(1));
        // Supabase normally returns tokens in the URL fragment. Some email clients
        // or redirect layers preserve them as query parameters instead, so accept
        // either location while still requiring both tokens for password setup.
        const token = (name) => hash.get(name) || params.get(name) || '';
        const accessToken = token('access_token');
        const refreshToken = token('refresh_token');
        const redirectError = token('error');
        const redirectErrorCode = token('error_code');
        const redirectErrorDescription = token('error_description');
        const supabaseUrl = window.__SUPABASE_URL__ || '';
        const form = document.getElementById('form');
        if (redirectError || redirectErrorCode || redirectErrorDescription) {
          status.className = 'error';
          const description = redirectErrorDescription || 'تعذر قبول رابط الدعوة.';
          status.textContent = `${description} (${redirectErrorCode || redirectError || 'auth_error'}). الرابط أحادي الاستخدام وقد انتهت صلاحيته أو تم فتحه مسبقاً.`;
          form.style.display = 'none';
        } else if (!accessToken || !refreshToken) {
          status.className = 'error';
          status.textContent = 'لم تصل رموز جلسة الدعوة إلى الصفحة. افتح رابط قبول الدعوة من البريد مباشرة، ولا تفتح صفحة /auth/invite يدوياً.';
          form.style.display = 'none';
        }
        form.addEventListener('submit', async (event) => {
          event.preventDefault();
          const password = document.getElementById('password').value;
          const confirm = document.getElementById('confirm').value;
          if (password !== confirm) { status.className = 'error'; status.textContent = 'كلمتا المرور غير متطابقتين.'; return; }
          if (password.length < 8) { status.className = 'error'; status.textContent = 'كلمة المرور يجب أن تحتوي على 8 أحرف على الأقل.'; return; }
          try {
            const response = await fetch('/auth/invite/password', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({access_token: accessToken, refresh_token: refreshToken, password})
            });
            const body = await response.json();
            if (!response.ok) {
              const detail = body && body.detail;
              const message = typeof detail === 'string'
                ? detail
                : Array.isArray(detail)
                  ? detail.map((item) => {
                      const location = Array.isArray(item && item.loc) ? item.loc.join('.') : '';
                      const reason = item && (item.msg || item.message) || 'بيانات غير صالحة';
                      return location ? `${location}: ${reason}` : reason;
                    }).join('؛ ')
                  : (detail && (detail.message || detail.msg || detail.error_description))
                    || 'تعذر حفظ كلمة المرور';
              throw new Error(message);
            }
            status.className = 'ok';
            status.textContent = 'تم إنشاء كلمة المرور والتحقق منها بنجاح. يمكنك الآن تسجيل الدخول من واجهة المنصة.';
            form.style.display = 'none';
          } catch (error) {
            status.className = 'error';
            status.textContent = error && error.message ? error.message : 'تعذر حفظ كلمة المرور';
          }
        });
      </script>
    </body>
    </html>
    """


def _provider_detail(response: requests.Response, fallback: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return fallback
    if isinstance(body, dict):
        value = body.get("msg") or body.get("message") or body.get("error_description") or body.get("error")
        if value:
            return str(value)[:240]
    return fallback


@router.post("/invite/password")
def set_invitation_password(request: PasswordSetupRequest) -> dict[str, str]:
    """Set and verify the invited user's password using the invitation session."""

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=503, detail="Supabase Auth configuration is missing")
    supabase_url = settings.supabase_url.rstrip("/")
    anon_key = settings.supabase_anon_key.get_secret_value()
    auth_headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {request.access_token}",
        "Content-Type": "application/json",
    }

    user_response = requests.get(
        f"{supabase_url}/auth/v1/user",
        headers=auth_headers,
        timeout=30,
    )
    if user_response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Invitation session is invalid or expired: {_provider_detail(user_response, 'invalid session')}",
        )
    try:
        user = user_response.json()
        email = str(user.get("email") or "").strip()
    except ValueError:
        email = ""
    if not email:
        raise HTTPException(status_code=502, detail="Supabase did not return the invited email")

    update_response = requests.put(
        f"{supabase_url}/auth/v1/user",
        headers=auth_headers,
        json={"password": request.password},
        timeout=30,
    )
    if update_response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Password update failed: {_provider_detail(update_response, 'password update rejected')}",
        )

    verify_response = requests.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": email, "password": request.password},
        timeout=30,
    )
    if verify_response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Password was not verified: {_provider_detail(verify_response, 'login verification rejected')}",
        )
    return {"status": "password_updated_and_verified", "email": email}
