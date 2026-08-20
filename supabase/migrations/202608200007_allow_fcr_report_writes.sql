-- Allow organization members to generate and refresh their own organization's FCR reports.
-- Reports contain only tenant-scoped aggregates already visible through reports_read.
create policy reports_insert on public.fcr_reports
for insert
to authenticated
with check ((select private.is_org_member(organization_id)));

create policy reports_update on public.fcr_reports
for update
to authenticated
using ((select private.is_org_member(organization_id)))
with check ((select private.is_org_member(organization_id)));
