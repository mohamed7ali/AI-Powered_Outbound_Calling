import os
from unittest.mock import Mock, patch

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

import pytest

from outbound_ai.api.routers.admin import OrganizationCreateRequest, InviteRequest, create_organization, invite_member
from outbound_ai.api.routers.documents import upload_document
from outbound_ai.api.routers.reports import FcrReportRequest, fcr_report
from outbound_ai.api.auth import Principal, TenantContext
from outbound_ai.ui import app as ui


ORG = "775bb9b6-5c04-46ff-bdab-0f39e4962eb3"


def _login_outputs(role: str, *, is_platform_admin: bool = False):
    response = Mock(status_code=200)
    response.json.return_value = {"access_token": "token"}
    session = {
        "is_platform_admin": is_platform_admin,
        "memberships": [{"id": ORG, "name": "dell", "slug": "dell", "role": role}],
    }
    with patch.object(ui.requests, "post", return_value=response), patch.object(ui, "_request", return_value=session):
        return ui.login("member@example.com", "password123")


def test_org_admin_login_reveals_operational_management_but_not_platform_controls() -> None:
    outputs = _login_outputs("ORG_ADMIN")
    assert outputs[5] == "الدور الحالي: **ORG_ADMIN**"
    assert outputs[6]["visible"] is True  # documents tab
    assert outputs[7]["visible"] is True  # reports tab
    assert outputs[8]["visible"] is True  # administration tab
    assert outputs[9]["visible"] is False  # platform controls
    assert outputs[10]["choices"] == ["AGENT"]


def test_platform_admin_session_flag_reveals_full_management_workspace() -> None:
    outputs = _login_outputs("AGENT", is_platform_admin=True)
    assert outputs[5] == "الدور الحالي: **PLATFORM_ADMIN**"
    assert outputs[6]["visible"] is True
    assert outputs[7]["visible"] is True
    assert outputs[8]["visible"] is True
    assert outputs[9]["visible"] is True
    assert outputs[10]["choices"] == ["AGENT", "ORG_ADMIN"]


def test_agent_login_hides_management_parent() -> None:
    outputs = _login_outputs("AGENT")
    assert outputs[5] == "الدور الحالي: **AGENT**"
    assert outputs[6]["visible"] is False
    assert outputs[7]["visible"] is False
    assert outputs[8]["visible"] is False
    assert outputs[9]["visible"] is False
    assert outputs[10]["choices"] == ["AGENT"]


def test_logout_clears_session_and_restores_login_view() -> None:
    outputs = ui.logout()
    assert len(outputs) == 13
    assert outputs[0] == ""  # token
    assert outputs[2]["visible"] is True  # auth panel
    assert outputs[3]["visible"] is False  # workspace
    assert outputs[4]["choices"] == []  # organization selector
    assert outputs[5] == ""  # role badge
    assert outputs[6] == []  # chatbot history
    assert outputs[7]["visible"] is False
    assert outputs[8]["visible"] is False
    assert outputs[9]["visible"] is False
    assert outputs[10]["visible"] is False
    assert outputs[12]["choices"] == []


def test_invite_rejects_missing_organization_before_request() -> None:
    with pytest.raises(Exception) as exc_info:
        ui.invite_member("new@example.com", "AGENT", "token", None)
    assert "اختر المؤسسة" in str(exc_info.value)


def test_headers_tolerate_empty_gradio_values() -> None:
    assert ui._headers(None, None) == {}


def test_direct_call_uses_immediate_endpoint_without_scheduling() -> None:
    response = {"call_id": "call-1", "status": "INITIATED", "follow_up_task_id": None}
    with patch.object(ui, "_request", return_value=response) as request:
        result = ui.direct_call(ORG, "رسالة اختبار", "token", ORG)
    request.assert_called_once_with(
        "POST",
        "/campaign/calls/direct",
        token="token",
        organization_id=ORG,
        json={"case_id": ORG, "greeting": "رسالة اختبار"},
    )
    assert "follow_up_task_id" in result


def test_schedule_output_formats_time_and_returns_task_id() -> None:
    task_id = "b6b6e282-611b-49ea-855e-2da00c14d657"
    row = {
        "id": task_id,
        "case_id": ORG,
        "scheduled_for": "2026-08-20T21:36:41.406128Z",
        "status": "PENDING",
        "attempt_number": 1,
    }
    with patch.object(ui, "_request", return_value=row):
        result, returned_task_id = ui.schedule_followup(
            ORG,
            "2026-08-20T21:36:41.406128Z",
            "token",
            ORG,
        )
    assert returned_task_id == task_id
    assert "تمت جدولة المتابعة بنجاح" in result
    assert "موعد التنفيذ" in result
    assert "أغسطس" in result
    assert "2026-08-20T21:36:41" not in result


def test_org_admin_cannot_create_an_organization() -> None:
    principal = Principal(user_id="00000000-0000-0000-0000-000000000001", is_platform_admin=False, role="ORG_ADMIN")
    with pytest.raises(Exception) as exc_info:
        create_organization(OrganizationCreateRequest(name="Blocked", slug="blocked"), principal=principal)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_org_admin_cannot_invite_another_org_admin() -> None:
    principal = Principal(user_id="00000000-0000-0000-0000-000000000001", is_platform_admin=False, role="ORG_ADMIN")
    context = TenantContext(actor_id=principal.user_id, organization_id=ORG, actor_role="ORG_ADMIN")
    with patch("outbound_ai.api.routers.admin.tenant_context", return_value=context):
        with pytest.raises(Exception) as exc_info:
            invite_member(ORG, InviteRequest(email="new@example.com", role="ORG_ADMIN"), principal=principal)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_agent_cannot_upload_documents_or_generate_reports() -> None:
    principal = Principal(user_id="00000000-0000-0000-0000-000000000002", is_platform_admin=False, role="AGENT")
    context = TenantContext(actor_id=principal.user_id, organization_id=ORG, actor_role="AGENT")
    with patch("outbound_ai.api.routers.documents.tenant_context", return_value=context):
        with pytest.raises(Exception) as upload_exc:
            upload_document(None, principal=principal, organization_id=ORG)
    assert getattr(upload_exc.value, "status_code", None) == 403

    with patch("outbound_ai.api.routers.reports.tenant_context", return_value=context):
        with pytest.raises(Exception) as report_exc:
            fcr_report(FcrReportRequest(period_start="2026-08-01", period_end="2026-08-20"), principal=principal, organization_id=ORG)
    assert getattr(report_exc.value, "status_code", None) == 403
