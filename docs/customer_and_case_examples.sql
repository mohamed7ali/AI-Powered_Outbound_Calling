-- Customer and support-case examples.
-- Run in Supabase SQL Editor only after applying all migrations.
-- These are examples, not schema migrations. Replace the values first.
-- This script does not place a call.

begin;

with input_data(full_name, phone_e164, preferred_language, subject, description) as (
  values
    ('Customer One', '+201000000001', 'ar',
     'مشكلة في تسجيل الدخول',
     'العميل لا يستطيع تسجيل الدخول إلى حسابه.'),
    ('Customer Two', '+201000000002', 'ar',
     'مشكلة في الخدمة',
     'العميل أبلغ عن توقف الخدمة.')
),
organization_row as (
  select id
  from public.organizations
  where lower(name) = lower('dell')
  limit 1
),
new_customers as (
  insert into public.customers
    (organization_id, full_name, phone_e164, preferred_language)
  select o.id, i.full_name, i.phone_e164, i.preferred_language
  from organization_row o
  cross join input_data i
  returning id, organization_id, full_name, phone_e164
),
created_cases as (
  insert into public.support_cases
    (organization_id, customer_id, subject, description, status)
  select nc.organization_id, nc.id, i.subject, i.description,
         'OPEN'::public.case_status
  from new_customers nc
  join input_data i
    on i.full_name = nc.full_name
   and i.phone_e164 = nc.phone_e164
  returning id, customer_id, subject, status
)
select nc.id as customer_id, nc.full_name, nc.phone_e164,
       cc.id as case_id, cc.subject, cc.status
from new_customers nc
join created_cases cc on cc.customer_id = nc.id;

commit;

-- If a customer already exists, create only a new callable case:
-- insert into public.support_cases
--   (organization_id, customer_id, subject, description, status)
-- select cu.organization_id, cu.id,
--        'مشكلة جديدة تحتاج إلى متابعة',
--        'وصف المشكلة الجديدة هنا.',
--        'OPEN'::public.case_status
-- from public.customers cu
-- join public.organizations o on o.id = cu.organization_id
-- where lower(o.name) = lower('dell')
--   and cu.phone_e164 = '+201000000001'
-- returning id as case_id, customer_id, subject, status;

-- One-time synchronization for cases whose latest call was resolved.
-- Run this only if an older application version updated calls.outcome but
-- did not update support_cases.status.
-- with latest_call as (
--   select distinct on (case_id) case_id, outcome
--   from public.calls
--   order by case_id, created_at desc
-- )
-- update public.support_cases sc
-- set status = 'RESOLVED'::public.case_status,
--     resolved_at = coalesce(sc.resolved_at, now()),
--     updated_at = now()
-- from latest_call lc
-- where lc.case_id = sc.id
--   and lc.outcome = 'ANSWERED_RESOLVED'
--   and sc.status <> 'RESOLVED'::public.case_status;

-- Verify customers and callable cases:
-- select cu.id as customer_id, cu.full_name, cu.phone_e164,
--        sc.id as case_id, sc.subject, sc.status
-- from public.customers cu
-- join public.support_cases sc on sc.customer_id = cu.id
-- join public.organizations o on o.id = cu.organization_id
-- where lower(o.name) = lower('dell')
-- order by cu.created_at desc;
