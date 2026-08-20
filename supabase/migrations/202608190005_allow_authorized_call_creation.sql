-- Allow authenticated tenant users to create calls for cases they are allowed to work.
-- Provider callbacks and the scheduler continue to use the protected trusted path.
create policy calls_insert on public.calls for insert to authenticated
with check (
  (select private.is_org_member(organization_id))
  and exists (
    select 1
    from public.support_cases sc
    where sc.id = calls.case_id
      and sc.organization_id = calls.organization_id
      and (
        (select private.is_org_admin(calls.organization_id))
        or sc.assigned_agent_id = (select private.current_actor_id())
      )
  )
  and (
    calls.follow_up_task_id is null
    or exists (
      select 1
      from public.follow_up_tasks f
      where f.id = calls.follow_up_task_id
        and f.case_id = calls.case_id
        and f.organization_id = calls.organization_id
    )
  )
);
