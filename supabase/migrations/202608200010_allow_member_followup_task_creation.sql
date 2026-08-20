-- Allow authenticated active organization members to schedule follow-up tasks.
-- The API still verifies that the selected support case belongs to the same organization.
-- Apply this migration in Supabase SQL Editor after migration 0009.

create policy follow_up_tasks_insert_active_members_20260820
on public.follow_up_tasks
for insert
to authenticated
with check (
  public.authenticated_actor_can_read_org(organization_id)
  and exists (
    select 1
    from public.support_cases sc
    where sc.id = public.follow_up_tasks.case_id
      and sc.organization_id = public.follow_up_tasks.organization_id
  )
);

create policy follow_up_tasks_select_active_members_20260820
on public.follow_up_tasks
for select
to authenticated
using (public.authenticated_actor_can_read_org(organization_id));
