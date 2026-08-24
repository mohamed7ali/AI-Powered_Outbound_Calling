"""Polished Arabic operations console for authenticated organization members."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import gradio as gr
import requests
from dotenv import load_dotenv

load_dotenv()
DEFAULT_API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DISPLAY_TIMEZONE = os.getenv("UI_TIMEZONE", "Africa/Cairo")
_ARABIC_MONTHS = (
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
)

_CSS = """
body { background: #07111f; }
.gradio-container { max-width: 1400px !important; margin: auto; }
.hero { padding: 28px 32px; border-radius: 20px; background: linear-gradient(135deg,#112844,#0b172a); border: 1px solid #243b5a; margin-bottom: 18px; }
.hero h1 { color: #f2f7ff; margin: 0 0 6px; font-size: 30px; }
.hero p { color: #a9bdd5; margin: 0; font-size: 15px; }
.auth-card, .surface { border: 1px solid #243b5a; border-radius: 16px; padding: 18px; background: #0d1a2c; }
.status { color: #9fb5cf; }
.small-note { color: #8da4bf; font-size: 13px; }
"""


def _headers(token: str | None, organization_id: str | None = "") -> dict[str, str]:
    headers: dict[str, str] = {}
    token = token or ""
    organization_id = organization_id or ""
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    if organization_id.strip():
        headers["X-Organization-Id"] = organization_id.strip()
    return headers


def _request(method: str, path: str, *, token: str | None = "", organization_id: str | None = "", **kwargs: Any) -> Any:
    headers = {**_headers(token, organization_id), **kwargs.pop("headers", {})}
    response = requests.request(
        method,
        f"{DEFAULT_API_URL.rstrip('/')}{path}",
        headers=headers,
        timeout=90,
        **kwargs,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text}
    if response.status_code >= 400:
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        raise RuntimeError(f"HTTP {response.status_code}: {detail}")
    return payload


def _error(message: str) -> None:
    raise gr.Error(message)


def login(email: str, password: str) -> tuple[Any, ...]:
    """Authenticate, resolve memberships, and only then reveal the workspace."""

    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
    if not supabase_url or not anon_key:
        _error("إعدادات Supabase غير مكتملة على الخادم.")
    if not email.strip() or not password:
        _error("اكتب البريد الإلكتروني وكلمة المرور أولاً.")
    response = None
    for attempt in range(3):
        try:
            response = requests.post(
                f"{supabase_url}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": anon_key,
                    "Content-Type": "application/json",
                },
                json={"email": email.strip(), "password": password},
                timeout=(10, 60),
            )
            break
        except requests.exceptions.RequestException:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))

    if response is None:
        _error("تعذر الوصول إلى Supabase حالياً. حاول تسجيل الدخول مرة أخرى بعد لحظات.")
    if response.status_code >= 400:
        _error("تعذر تسجيل الدخول. تأكد من الحساب وكلمة المرور.")
    body = response.json()
    token = body["access_token"]
    session = _request("GET", "/auth/session", token=token)
    memberships = session.get("memberships", [])
    session_is_platform_admin = bool(session.get("is_platform_admin"))
    choices = [(f"{item['name']}  ·  {item['role']}", item["id"]) for item in memberships]
    if not choices:
        _error("تم تسجيل الدخول، لكن لا توجد مؤسسة مرتبطة بهذا الحساب بعد.")
    selected = choices[0][1]
    role = "PLATFORM_ADMIN" if session_is_platform_admin else memberships[0]["role"]
    can_admin = role in {"PLATFORM_ADMIN", "ORG_ADMIN"}
    is_platform_admin = session_is_platform_admin or role == "PLATFORM_ADMIN"
    role_choices = ["AGENT", "ORG_ADMIN"] if is_platform_admin else ["AGENT"]
    message = f"تم تسجيل الدخول بنجاح. أهلاً بك، {email.strip()}"
    return (
        token,
        message,
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(choices=choices, value=selected),
        f"الدور الحالي: **{role}**",
        gr.update(visible=can_admin),
        gr.update(visible=can_admin),
        gr.update(visible=can_admin),
        gr.update(visible=is_platform_admin),
        gr.update(choices=role_choices, value="AGENT"),
    )


def logout() -> tuple[Any, ...]:
    """Clear the local Gradio session and restore the login view."""
    return (
        "",  # token_state
        "تم تسجيل الخروج.",  # auth_status
        gr.update(visible=True),  # auth_panel
        gr.update(visible=False),  # workspace
        gr.update(choices=[], value=None),  # organization
        "",  # role_badge
        [],  # chatbot
        gr.update(visible=False),  # documents_tab
        gr.update(visible=False),  # reports_tab
        gr.update(visible=False),  # administration_tab
        gr.update(visible=False),  # platform_admin_controls
        gr.update(choices=["AGENT"], value="AGENT"),  # member_role
        gr.update(choices=[], value=None),  # admin_target_organization
    )


def select_organization(token: str, organization_id: str) -> tuple[Any, ...]:
    try:
        session = _request("GET", "/auth/session", token=token)
        session_is_platform_admin = bool(session.get("is_platform_admin"))
        selected = next((item for item in session.get("memberships", []) if item["id"] == organization_id), None)
        if selected is None:
            return (
                "",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(choices=["AGENT"], value="AGENT"),
            )
        role = "PLATFORM_ADMIN" if session_is_platform_admin else selected["role"]
        can_admin = role in {"PLATFORM_ADMIN", "ORG_ADMIN"}
        is_platform_admin = session_is_platform_admin or role == "PLATFORM_ADMIN"
        role_choices = ["AGENT", "ORG_ADMIN"] if is_platform_admin else ["AGENT"]
        return (
            f"المؤسسة الحالية: **{selected['name']}** · الدور: **{role}**",
            gr.update(visible=can_admin),
            gr.update(visible=can_admin),
            gr.update(visible=can_admin),
            gr.update(visible=is_platform_admin),
            gr.update(choices=role_choices, value="AGENT"),
        )
    except Exception as exc:
        raise gr.Error(str(exc))


def load_cases(token: str, organization_id: str) -> tuple[list[list[Any]], Any]:
    try:
        rows = _request("GET", "/campaign/cases", token=token, organization_id=organization_id)
        table = [[row.get(key) for key in ("customer_name", "subject", "status", "updated_at")] for row in rows]
        choices = [
            (f"{row.get('subject', 'حالة')} · {row.get('customer_name', 'عميل')}", row["id"])
            for row in rows
        ]
        return table, gr.update(choices=choices, value=(choices[0][1] if choices else None))
    except Exception as exc:
        raise gr.Error(str(exc))


def _format_arabic_datetime(value: Any) -> str:
    """Render an API timestamp in a readable Cairo-local Arabic format."""
    if not value:
        return "غير محدد"
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        local = parsed.astimezone(ZoneInfo(DISPLAY_TIMEZONE))
        hour = local.hour % 12 or 12
        meridiem = "ص" if local.hour < 12 else "م"
        return f"{local.day} {_ARABIC_MONTHS[local.month - 1]} {local.year}، {hour}:{local.minute:02d} {meridiem}"
    except (TypeError, ValueError, KeyError):
        return str(value)


def _format_scheduled_task(row: dict[str, Any]) -> str:
    status_labels = {
        "PENDING": "قيد الانتظار",
        "IN_PROGRESS": "قيد التنفيذ",
        "COMPLETED": "مكتملة",
        "FAILED": "فشلت",
    }
    return "\n".join(
        [
            "### تمت جدولة المتابعة بنجاح",
            f"**معرّف المهمة:** `{row.get('id', '')}`",
            f"**الحالة:** {status_labels.get(row.get('status'), row.get('status', 'غير معروف'))}",
            f"**موعد التنفيذ:** {_format_arabic_datetime(row.get('scheduled_for'))}",
            "تم وضع معرّف المهمة تلقائياً في حقل بدء الاتصال. إذا كان scheduler يعمل، فسيبدأ المهمة تلقائياً عند حلول الموعد.",
        ]
    )


def direct_call(case_id: str, greeting: str, token: str, organization_id: str) -> str:
    if not case_id or not case_id.strip():
        _error("اختر حالة صحيحة من قائمة الحالات أولاً.")
    try:
        UUID(case_id.strip())
    except ValueError:
        _error("معرّف الحالة غير صالح. اضغط تحديث الحالات ثم اختر حالة من القائمة.")
    try:
        body = _request(
            "POST",
            "/campaign/calls/direct",
            token=token,
            organization_id=organization_id,
            json={
                "case_id": case_id.strip(),
                "greeting": greeting.strip() or "مرحباً، بنتابع مع حضرتك للتأكد إن المشكلة اتحلت.",
            },
        )
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        raise gr.Error(str(exc))


def schedule_followup(case_id: str, scheduled_for: str, token: str, organization_id: str) -> tuple[str, Any]:
    if not case_id or not case_id.strip():
        _error("اختر حالة صحيحة من قائمة الحالات أولاً.")
    try:
        UUID(case_id.strip())
    except ValueError:
        _error("معرّف الحالة غير صالح. اضغط تحديث الحالات ثم اختر حالة من القائمة.")
    if not scheduled_for or not scheduled_for.strip():
        _error("أدخل موعد المتابعة بصيغة ISO.")
    try:
        datetime.fromisoformat(scheduled_for.strip())
    except ValueError:
        _error("موعد المتابعة غير صالح. استخدم مثالاً مثل 2026-08-20T12:00:00+00:00.")
    try:
        row = _request(
            "POST",
            "/campaign/followups",
            token=token,
            organization_id=organization_id,
            json={"case_id": case_id, "scheduled_for": scheduled_for.strip()},
        )
        return _format_scheduled_task(row), str(row.get("id", ""))
    except Exception as exc:
        raise gr.Error(str(exc))


def load_followups(token: str, organization_id: str) -> tuple[list[list[Any]], Any]:
    if not token or not token.strip() or not organization_id or not organization_id.strip():
        return [], gr.update(choices=[], value=None)
    try:
        rows = _request("GET", "/campaign/followups", token=token, organization_id=organization_id)
        table = [
            [
                row.get("customer_name"),
                row.get("subject"),
                row.get("scheduled_for"),
                row.get("status"),
                row.get("attempt_number"),
                row.get("id"),
            ]
            for row in rows
        ]
        choices = [
            (
                f"{row.get('customer_name', 'عميل')} · {row.get('subject', 'متابعة')} · "
                f"{row.get('status', '')} · {row.get('id', '')}",
                str(row["id"]),
            )
            for row in rows
        ]
        return table, gr.update(choices=choices, value=(choices[0][1] if choices else None))
    except Exception as exc:
        raise gr.Error(str(exc))


def load_escalations(token: str, organization_id: str) -> tuple[list[list[Any]], str]:
    try:
        rows = _request("GET", "/agent/escalations", token=token, organization_id=organization_id)
        print(
            f"[escalations] api={DEFAULT_API_URL.rstrip('/')} organization_id={organization_id} "
            f"returned_rows={len(rows) if isinstance(rows, list) else 'non-list'}",
            flush=True,
        )
        table = [
            [
                row.get("customer_name"),
                row.get("subject"),
                row.get("reason"),
                row.get("latest_customer_message"),
                row.get("escalated_at"),
                row.get("escalation_id"),
            ]
            for row in rows
        ]
        return table, f"تم تحميل {len(table)} تصعيدات مفتوحة للمؤسسة الحالية."
    except Exception as exc:
        print(
            f"[escalations] api={DEFAULT_API_URL.rstrip('/')} organization_id={organization_id} "
            f"error_type={type(exc).__name__}",
            flush=True,
        )
        raise gr.Error(str(exc))


def resolve_escalation(escalation_id: str, token: str, organization_id: str) -> str:
    if not escalation_id.strip():
        _error("اختر تصعيداً من قائمة العمل أولاً.")
    try:
        body = _request(
            "POST",
            "/agent/escalations/resolve",
            token=token,
            organization_id=organization_id,
            json={"escalation_id": escalation_id.strip()},
        )
        return json.dumps(body, ensure_ascii=False, indent=2)
    except Exception as exc:
        raise gr.Error(str(exc))


def start_followup(task_id: str, greeting: str, token: str, organization_id: str) -> str:
    if not task_id or not task_id.strip():
        _error("أدخل معرّف مهمة المتابعة من نتيجة الجدولة.")
    try:
        body = _request(
            "POST",
            f"/campaign/followups/{task_id.strip()}/start",
            token=token,
            organization_id=organization_id,
            json={"greeting": greeting.strip() or "مرحباً، بنتابع مع حضرتك للتأكد إن المشكلة اتحلت."},
        )
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        message = str(exc)
        if "HTTP 409" in message and "not pending" in message.lower():
            raise gr.Error("هذه المهمة لم تعد قيد الانتظار؛ قد يكون scheduler بدأ تنفيذها تلقائياً. انتظر نتيجة المكالمة أو استخدم مهمة جديدة.")
        raise gr.Error(message)


def simulate_outcome(call_id: str, outcome: str, token: str, organization_id: str) -> str:
    if not call_id.strip():
        _error("أدخل معرّف المكالمة أولاً.")
    try:
        body = _request(
            "POST",
            f"/campaign/calls/{call_id.strip()}/simulate-outcome",
            token=token,
            organization_id=organization_id,
            json={"outcome": outcome},
        )
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        raise gr.Error(str(exc))


def ask_agent(message: str, history: list[dict] | None, token: str, organization_id: str) -> tuple[list[dict], str]:
    if not message.strip():
        return history or [], ""
    try:
        body = _request(
            "POST", "/agent/query", token=token, organization_id=organization_id,
            json={"question": message.strip()},
        )
        answer = body.get("answer", "")
        citations = body.get("citations", [])
        if citations:
            source_lines = []
            for item in citations:
                citation_id = item.get("citation_id", "S?")
                title = item.get("document_title") or item.get("title") or "مستند المؤسسة"
                page = item.get("page_number")
                page_text = f"، الصفحة {page}" if page else ""
                quote = (item.get("quote") or item.get("snippet") or "").strip()
                source_lines.append(
                    f"- **[{citation_id}] {title}**{page_text}\n  {quote}"
                )
            answer += "\n\n**المصادر:**\n" + "\n".join(source_lines)
        history = history or []
        history.extend([{"role": "user", "content": message}, {"role": "assistant", "content": answer}])
        return history, ""
    except Exception as exc:
        raise gr.Error(str(exc))


def upload_document(file_path: str, token: str, organization_id: str) -> str:
    if not file_path:
        _error("اختر مستنداً أولاً.")
    try:
        with open(file_path, "rb") as handle:
            body = _request(
                "POST", "/documents/upload", token=token, organization_id=organization_id,
                files={"file": (Path(file_path).name, handle)},
            )
        return json.dumps(body, ensure_ascii=False, indent=2)
    except Exception as exc:
        raise gr.Error(str(exc))


def list_documents(token: str, organization_id: str) -> str:
    try:
        body = _request("GET", "/documents", token=token, organization_id=organization_id)
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        raise gr.Error(str(exc))


def report_fcr(start: str, end: str, token: str, organization_id: str) -> str:
    try:
        date.fromisoformat(start)
        date.fromisoformat(end)
        body = _request(
            "POST", "/reports/fcr", token=token, organization_id=organization_id,
            json={"period_start": start, "period_end": end},
        )
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        raise gr.Error(str(exc))


def create_organization(name: str, slug: str, token: str) -> str:
    try:
        body = _request("POST", "/admin/organizations", token=token, json={"name": name.strip(), "slug": slug.strip()})
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        raise gr.Error(str(exc))


def load_admin_organizations(token: str) -> Any:
    if not token or not token.strip():
        return gr.update(choices=[], value=None)
    try:
        session = _request("GET", "/auth/session", token=token)
        memberships = session.get("memberships", [])
        choices = [(f"{item['name']}  ·  {item['role']}", item["id"]) for item in memberships]
        return gr.update(choices=choices, value=(choices[0][1] if choices else None))
    except Exception as exc:
        raise gr.Error(str(exc))


def list_members(token: str, organization_id: str) -> str:
    try:
        body = _request("GET", f"/admin/{organization_id}/members", token=token, organization_id=organization_id)
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        raise gr.Error(str(exc))


def invite_member(email: str, role: str, token: str, organization_id: str | None) -> str:
    if not email or not email.strip():
        _error("أدخل البريد الإلكتروني أولاً.")
    if not organization_id or not organization_id.strip():
        _error("اختر المؤسسة المستهدفة قبل إرسال الدعوة. اضغط تحديث قائمة المؤسسات إذا كانت القائمة فارغة.")
    if not role or role not in {"AGENT", "ORG_ADMIN"}:
        _error("اختر دوراً صالحاً للمستخدم.")
    try:
        body = _request(
            "POST", f"/admin/{organization_id}/invite", token=token, organization_id=organization_id,
            json={"email": email.strip(), "role": role},
        )
        return json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        raise gr.Error(str(exc))


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="منصة المتابعة الذكية", css=_CSS, theme=gr.themes.Soft()) as demo:
        token_state = gr.State("")
        role_state = gr.State("")
        gr.HTML(
            '<section class="hero"><h1>منصة المتابعة الذكية</h1>'
            '<p>متابعة العملاء باللغة العربية، مساعد معرفة للموظفين، وتقارير جودة متعددة المؤسسات.</p></section>'
        )

        with gr.Column(elem_classes="auth-card") as auth_panel:
            gr.Markdown("## تسجيل الدخول\nاستخدم حسابك في Supabase Auth للوصول إلى مؤسساتك المصرح بها.")
            with gr.Row():
                email = gr.Textbox(label="البريد الإلكتروني", placeholder="name@example.com")
                password = gr.Textbox(label="كلمة المرور", type="password")
            login_button = gr.Button("تسجيل الدخول", variant="primary")
            auth_status = gr.Markdown("", elem_classes="status")

        with gr.Column(visible=False) as workspace:
            with gr.Row():
                organization = gr.Dropdown(label="المؤسسة الحالية", choices=[], interactive=True, scale=3)
                role_badge = gr.Markdown("", elem_classes="status", elem_id="role-badge")
                logout_button = gr.Button("تسجيل الخروج", scale=1)
            workspace_status = gr.Markdown("اختر المؤسسة لبدء العمل.", elem_classes="status")

            with gr.Tabs():
                with gr.Tab("المكالمات والتصعيدات"):
                    gr.Markdown("### المكالمات والتصعيدات")
                    gr.Markdown("اعرض التصعيدات، ثم جدولة أو بدء مكالمة متابعة للعميل.", elem_classes="small-note")
                    refresh_escalations = gr.Button("تحديث التصعيدات")
                    escalation_status = gr.Markdown("اضغط تحديث التصعيدات لتحميل الحالات المفتوحة.", elem_classes="status")
                    escalations = gr.Dataframe(
                        headers=["العميل", "الموضوع", "سبب التصعيد", "آخر رسالة", "وقت التصعيد", "معرّف التصعيد"],
                        interactive=False,
                        wrap=True,
                    )
                    escalation_selector = gr.Textbox(label="معرّف التصعيد المراد إغلاقه")
                    resolve_button = gr.Button("تحديد التصعيد كمُعالج", variant="primary")
                    escalation_result = gr.Code(label="نتيجة الإجراء", language="json")
                    refresh_escalations.click(
                        load_escalations,
                        [token_state, organization],
                        [escalations, escalation_status],
                    )
                    resolve_button.click(
                        resolve_escalation,
                        [escalation_selector, token_state, organization],
                        escalation_result,
                    )
                    gr.Markdown("### تشغيل متابعة للعميل")
                    refresh = gr.Button("تحديث الحالات")
                    cases = gr.Dataframe(headers=["العميل", "الموضوع", "الحالة", "آخر تحديث"], interactive=False)
                    case_selector = gr.Dropdown(label="الحالة المطلوب متابعتها", choices=[], interactive=True)
                    gr.Markdown("### اتصال فوري بدون جدولة")
                    direct_greeting = gr.Textbox(
                        label="رسالة الاتصال الفوري",
                        value="مرحباً، بنتابع مع حضرتك للتأكد إن المشكلة اتحلت.",
                    )
                    direct_call_button = gr.Button("اتصال فوري بالعميل", variant="primary")
                    direct_call_result = gr.Code(label="نتيجة الاتصال الفوري", language="json")
                    direct_call_button.click(
                        direct_call,
                        [case_selector, direct_greeting, token_state, organization],
                        direct_call_result,
                    )
                    gr.Markdown("### جدولة متابعة لاحقة")
                    scheduled_for = gr.Textbox(
                        label="موعد المتابعة (ISO؛ مثال: 2026-08-20T12:00:00+00:00)",
                        value=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
                    )
                    create_task = gr.Button("جدولة متابعة", variant="primary")
                    task_result = gr.Markdown(label="نتيجة الجدولة")
                    task_table = gr.Dataframe(
                        headers=["العميل", "الموضوع", "الموعد", "الحالة", "المحاولة", "معرّف المهمة"],
                        interactive=False,
                    )
                    refresh_tasks = gr.Button("عرض مهام المتابعة")
                    task_id = gr.Dropdown(
                        label="مهمة المتابعة المراد تشغيلها",
                        choices=[],
                        allow_custom_value=True,
                        interactive=True,
                    )
                    greeting = gr.Textbox(
                        label="رسالة البداية الاختيارية",
                        value="مرحباً، بنتابع مع حضرتك للتأكد إن المشكلة اتحلت.",
                    )
                    refresh.click(load_cases, [token_state, organization], [cases, case_selector])
                    refresh_tasks.click(
                        load_followups,
                        [token_state, organization],
                        [task_table, task_id],
                    )
                    create_task.click(
                        schedule_followup,
                        [case_selector, scheduled_for, token_state, organization],
                        [task_result, task_id],
                    )
                    start_call = gr.Button("بدء الاتصال الآن", variant="primary")
                    call_result = gr.Code(label="نتيجة الاتصال", language="json")
                    start_call.click(
                        start_followup,
                        [task_id, greeting, token_state, organization],
                        call_result,
                    )

                with gr.Tab("مساعد المعرفة العربي"):
                    gr.Markdown("### مساعد المعرفة العربي")
                    chatbot = gr.Chatbot(label="المساعد المعرفي العربي", type="messages")
                    question = gr.Textbox(label="سؤالك", placeholder="اكتب سؤالاً متعلقاً بحالة العميل أو إجراءات المؤسسة...")
                    send = gr.Button("إرسال السؤال", variant="primary")
                    send.click(ask_agent, [question, chatbot, token_state, organization], [chatbot, question])
                    question.submit(ask_agent, [question, chatbot, token_state, organization], [chatbot, question])

                with gr.Tab("المعرفة والمستندات") as documents_tab:
                    document = gr.File(label="رفع مستند المؤسسة PDF / DOCX / TXT", type="filepath")
                    upload = gr.Button("رفع ومعالجة المستند", variant="primary")
                    document_result = gr.Code(label="نتيجة المعالجة", language="json")
                    upload.click(upload_document, [document, token_state, organization], document_result)
                    list_docs = gr.Button("عرض مستندات المؤسسة")
                    docs_result = gr.Code(label="المستندات الحالية", language="json")
                    list_docs.click(list_documents, [token_state, organization], docs_result)

                with gr.Tab("تقارير الجودة") as reports_tab:
                    with gr.Row():
                        start = gr.Textbox(label="من", value=str(date.today()))
                        end = gr.Textbox(label="إلى", value=str(date.today()))
                    generate_report = gr.Button("إنشاء تقرير FCR", variant="primary")
                    report_result = gr.Code(label="تقرير الجودة", language="json")
                    generate_report.click(report_fcr, [start, end, token_state, organization], report_result)

                with gr.Tab("الإدارة") as administration_tab:
                    gr.Markdown("## الإدارة\nهذه الأدوات تظهر فقط للمسؤول العام أو مسؤول المؤسسة.")
                    admin_target_organization = gr.Dropdown(
                        label="المؤسسة المستهدفة للدعوات وإدارة الأعضاء",
                        choices=[],
                        interactive=True,
                    )
                    refresh_admin_orgs = gr.Button("تحديث قائمة المؤسسات")
                    gr.Markdown(
                        "اختر المؤسسة المستهدفة هنا قبل إرسال الدعوة. بعد إنشاء مؤسسة جديدة اضغط تحديث قائمة المؤسسات.",
                        elem_classes="small-note",
                    )
                    with gr.Column(elem_id="platform-admin-controls") as platform_admin_controls:
                        with gr.Row():
                            org_name = gr.Textbox(label="اسم المؤسسة الجديدة")
                            org_slug = gr.Textbox(label="المعرّف المختصر")
                            create_org_button = gr.Button("إنشاء مؤسسة")
                        org_result = gr.Code(label="نتيجة إنشاء المؤسسة", language="json")
                        create_org_button.click(create_organization, [org_name, org_slug, token_state], org_result)
                    refresh_admin_orgs.click(load_admin_organizations, [token_state], admin_target_organization)
                    with gr.Row():
                        member_email = gr.Textbox(label="بريد العضو")
                        member_role = gr.Dropdown(["AGENT", "ORG_ADMIN"], value="AGENT", label="الدور")
                        invite_button = gr.Button("إرسال الدعوة")
                    invite_result = gr.Code(label="نتيجة الدعوة", language="json")
                    invite_button.click(
                        invite_member,
                        [member_email, member_role, token_state, admin_target_organization],
                        invite_result,
                    )
                    members_button = gr.Button("عرض أعضاء المؤسسة")
                    members_result = gr.Code(label="الأعضاء", language="json")
                    members_button.click(list_members, [token_state, admin_target_organization], members_result)
                    gr.Markdown("رابط دعوة المستخدم يفتح صفحة إعداد كلمة المرور، ثم يمكنه تسجيل الدخول من صفحة المنصة.", elem_classes="small-note")


            login_event = login_button.click(
                login,
                [email, password],
                [
                    token_state,
                    auth_status,
                    auth_panel,
                    workspace,
                    organization,
                    role_badge,
                    documents_tab,
                    reports_tab,
                    administration_tab,
                    platform_admin_controls,
                    member_role,
                ],
            )
            login_event.then(
                load_admin_organizations,
                [token_state],
                admin_target_organization,
            )
            logout_button.click(
                logout,
                [],
                [
                    token_state,
                    auth_status,
                    auth_panel,
                    workspace,
                    organization,
                    role_badge,
                    chatbot,
                    documents_tab,
                    reports_tab,
                    administration_tab,
                    platform_admin_controls,
                    member_role,
                    admin_target_organization,
                ],
            )
            organization.input(
                select_organization,
                [token_state, organization],
                [
                    workspace_status,
                    documents_tab,
                    reports_tab,
                    administration_tab,
                    platform_admin_controls,
                    member_role,
                ],
            )

    return demo


def main() -> None:
    build_ui().launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.getenv("GRADIO_PORT", "7860")),
    )


if __name__ == "__main__":
    main()
