-- Allow authorized tenant users to resolve their organization's escalations.
-- The application still controls the exact columns changed by close_escalation().
create policy escalations_update on public.escalations
for update
to authenticated
using (
  (select private.is_platform_admin())
  or (select private.is_org_admin(organization_id))
  or (
    (select private.is_org_member(organization_id))
    and (
      assigned_human_id is null
      or assigned_human_id = (select private.current_actor_id())
    )
  )
)
with check (
  (
    (select private.is_platform_admin())
    or (select private.is_org_admin(organization_id))
    or (
      (select private.is_org_member(organization_id))
      and assigned_human_id = (select private.current_actor_id())
    )
  )
  and status in ('PENDING', 'IN_PROGRESS', 'RESOLVED')
);
