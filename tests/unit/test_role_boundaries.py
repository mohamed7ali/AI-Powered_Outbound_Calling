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


def _login_outputs(role: str):
    response = Mock(status_code=200)
    response.json.return_value = {"access_token": "token"}
    session = {
        "memberships": [{"id": ORG, "name": "dell", "slug": "dell", "role": role}],
    }
    with patch.object(ui.requests, "post", return_value=response), patch.object(ui, "_request", return_value=session):
        return ui.login("member@example.com", "password123")


def test_org_admin_login_reveals_operational_management_but_not_platform_controls() -> None:
    outputs = _login_outputs("ORG_ADMIN")
    assert outputs[5] == "الدور الحالي: **ORG_ADMIN**"
    assert outputs[6]["visible"] is True  # administration panel
    assert outputs[7]["visible"] is False  # organization creation / platform controls
    assert outputs[8]["choices"] == ["AGENT"]
    assert outputs[9]["visible"] is True  # campaign/documents/reports/admin parent


def test_agent_login_hides_management_parent() -> None:
    outputs = _login_outputs("AGENT")
    assert outputs[5] == "الدور الحالي: **AGENT**"
    assert outputs[6]["visible"] is False
    assert outputs[7]["visible"] is False
    assert outputs[9]["visible"] is False


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
