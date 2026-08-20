-- Migration 0004: allow authenticated RLS policies and tenant search to invoke
-- private helper functions. SECURITY DEFINER functions retain the isolation checks.

grant usage on schema private to authenticated;

grant execute on function private.current_actor_id() to authenticated;
grant execute on function private.is_platform_admin() to authenticated;
grant execute on function private.is_org_member(uuid) to authenticated;
grant execute on function private.is_org_admin(uuid) to authenticated;
grant execute on function private.is_assigned_agent(uuid, uuid) to authenticated;
grant execute on function private.storage_org_id(text) to authenticated;

-- The public search functions are already granted in earlier migrations; repeat
-- these grants so the complete search contract is explicit and idempotent.
grant execute on function public.match_knowledge_chunks(extensions.vector(3072), uuid, integer)
  to authenticated;
grant execute on function public.hybrid_knowledge_chunks(extensions.vector(3072), text, uuid, integer)
  to authenticated;
