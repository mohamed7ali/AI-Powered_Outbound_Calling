-- Allow authenticated organization members to read the escalation work queue.
-- The existing API query joins escalations to calls, support_cases, customers,
-- and call_turns. Apply this migration in Supabase SQL Editor.

create or replace function public.authenticated_actor_can_read_org(p_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_catalog
as $$
  select exists (
    select 1
    from public.organization_memberships om
    where om.organization_id = p_organization_id
      and om.user_id = nullif(current_setting('app.current_user_id', true), '')::uuid
      and om.is_active = true
  )
  or exists (
    select 1
    from public.platform_admins pa
    where pa.user_id = nullif(current_setting('app.current_user_id', true), '')::uuid
  );
$$;

grant execute on function public.authenticated_actor_can_read_org(uuid) to authenticated;

create policy escalations_select_active_members_20260820
on public.escalations
for select
to authenticated
using (public.authenticated_actor_can_read_org(organization_id));

create policy calls_select_active_members_20260820
on public.calls
for select
to authenticated
using (public.authenticated_actor_can_read_org(organization_id));

create policy support_cases_select_active_members_20260820
on public.support_cases
for select
to authenticated
using (public.authenticated_actor_can_read_org(organization_id));

create policy customers_select_active_members_20260820
on public.customers
for select
to authenticated
using (public.authenticated_actor_can_read_org(organization_id));

create policy call_turns_select_active_members_20260820
on public.call_turns
for select
to authenticated
using (public.authenticated_actor_can_read_org(organization_id));
