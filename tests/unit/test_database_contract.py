"""Static contract tests for the first database migration.

These tests do not require a Supabase project. They catch accidental removal of
security-critical tables, RLS, tenant predicates, or the embedding dimension.
Live RLS tests should run against a disposable Supabase/PostgreSQL database in CI.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = "\n".join(
    (
        (ROOT / "supabase/migrations/202608160001_initial_schema.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608190005_allow_authorized_call_creation.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608200006_allow_escalation_resolution.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608200007_allow_fcr_report_writes.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608200008_allow_authenticated_audit_event_writes.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608200009_allow_member_escalation_reads.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608200010_allow_member_followup_task_creation.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608230011_switch_to_arabic_sentence_transformer_384.sql").read_text(encoding="utf-8"),
        (ROOT / "supabase/migrations/202608230012_calibrate_hybrid_retrieval_scores.sql").read_text(encoding="utf-8"),
    )
)


def test_required_domain_tables_are_migrated() -> None:
    required = {
        "profiles",
        "platform_admins",
        "organizations",
        "organization_memberships",
        "customers",
        "support_cases",
        "follow_up_tasks",
        "calls",
        "call_events",
        "call_turns",
        "escalations",
        "fcr_reports",
        "knowledge_documents",
        "knowledge_chunks",
        "agent_conversations",
        "agent_messages",
        "audit_events",
    }
    for table in required:
        assert f"create table public.{table}" in MIGRATION


def test_call_creation_policy_is_present() -> None:
    assert "create policy calls_insert" in MIGRATION
    assert "sc.assigned_agent_id = (select private.current_actor_id())" in MIGRATION
    assert "f.case_id = calls.case_id" in MIGRATION


def test_escalation_resolution_policy_is_present() -> None:
    assert "create policy escalations_update" in MIGRATION
    assert "assigned_human_id = (select private.current_actor_id())" in MIGRATION
    assert "status in ('PENDING', 'IN_PROGRESS', 'RESOLVED')" in MIGRATION


def test_fcr_report_write_policies_are_present() -> None:
    assert "create policy reports_insert" in MIGRATION
    assert "create policy reports_update" in MIGRATION
    assert "private.is_org_member(organization_id)" in MIGRATION


def test_tenant_security_contract_is_present() -> None:
    assert "create or replace function private.current_actor_id" in MIGRATION
    assert "create or replace function private.is_org_member" in MIGRATION
    assert "create or replace function private.is_org_admin" in MIGRATION
    assert "alter table public.knowledge_chunks enable row level security" in MIGRATION
    assert "private.is_org_member(organization_id)" in MIGRATION
    assert "create policy audit_insert" in MIGRATION


def test_rag_contract_is_permission_aware_and_dimension_matches_settings() -> None:
    assert "embedding extensions.vector(3072)" in MIGRATION  # initial schema history
    assert "alter column embedding type extensions.vector(384)" in MIGRATION
    assert "create index chunks_embedding_idx" in MIGRATION
    assert "create or replace function public.match_knowledge_chunks" in MIGRATION
    assert "security invoker" in MIGRATION
    assert "kc.organization_id = match_organization_id" in MIGRATION
    assert "private.is_org_member(kc.organization_id)" in MIGRATION
    assert "query_embedding extensions.vector(384)" in MIGRATION
    assert "greatest(0.0, least(1.0" in MIGRATION


def test_runtime_member_workflow_policies_are_present() -> None:
    assert "audit_events_insert" in MIGRATION or "audit_events_insert" in MIGRATION
    assert "escalations_select_active_members_20260820" in MIGRATION
    assert "follow_up_tasks_insert_active_members_20260820" in MIGRATION
    assert "public.authenticated_actor_can_read_org" in MIGRATION
    assert "public.follow_up_tasks.case_id" in MIGRATION


def test_storage_contract_is_private_and_organization_scoped() -> None:
    assert "values ('organization-documents', 'organization-documents', false)" in MIGRATION
    assert "create policy org_documents_read" in MIGRATION
    assert "private.storage_org_id(name)" in MIGRATION
