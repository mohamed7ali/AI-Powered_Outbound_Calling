from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from outbound_ai.db.repositories.escalations import serialize_escalation


def test_serialize_escalation_converts_uuid_and_datetime_values() -> None:
    escalation_id = uuid4()
    created_at = datetime.now(UTC)
    result = serialize_escalation(
        {
            "escalation_id": escalation_id,
            "created_at": created_at,
            "customer_name": "عميل تجريبي",
        }
    )

    assert result["escalation_id"] == str(escalation_id)
    assert result["created_at"] == created_at.isoformat()
    assert result["customer_name"] == "عميل تجريبي"


def test_escalation_repository_has_explicit_organization_scope() -> None:
    from pathlib import Path

    source = Path("src/outbound_ai/db/repositories/escalations.py").read_text(encoding="utf-8")
    assert "where e.organization_id = %s" in source
    assert "and c.organization_id = e.organization_id" in source
    assert "and sc.organization_id = e.organization_id" in source
    assert "and cu.organization_id = e.organization_id" in source


def test_agent_router_exposes_escalation_queue_and_resolution() -> None:
    from outbound_ai.api.routers.agent import router

    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in router.routes
    }
    assert ("/escalations", ("GET",)) in routes
    assert ("/escalations/resolve", ("POST",)) in routes
