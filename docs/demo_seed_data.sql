-- Demo seed data for the Arabic AI-Powered Outbound Calls platform.
-- Run this script in Supabase Dashboard -> SQL Editor.
-- It deletes and recreates ONLY the two reserved demo organizations:
--   demo-alpha-2026 and demo-beta-2026
-- It does not modify your existing dell organization or its data.
-- Run the cleanup section at the bottom later to remove all demo data.

begin;

do $$
declare
  platform_admin_id uuid;
  demo_agent_id uuid;
  alpha_id uuid;
  beta_id uuid;
  alpha_customer_1 uuid;
  alpha_customer_2 uuid;
  beta_customer_1 uuid;
  beta_customer_2 uuid;
  alpha_case_1 uuid;
  alpha_case_2 uuid;
  beta_case_1 uuid;
  beta_case_2 uuid;
  alpha_task_pending uuid;
  alpha_task_completed uuid;
  beta_task_failed uuid;
  alpha_call_resolved uuid;
  alpha_call_escalated uuid;
  beta_call_no_answer uuid;
  beta_call_failed uuid;
  alpha_doc uuid;
  beta_doc uuid;
begin
  select pa.user_id
  into platform_admin_id
  from public.platform_admins pa
  limit 1;

  if platform_admin_id is null then
    raise exception 'No platform administrator exists. Create/authenticate the platform admin first.';
  end if;

  -- Pick an existing non-platform user as an optional demo agent.
  select u.id
  into demo_agent_id
  from auth.users u
  left join public.platform_admins pa on pa.user_id = u.id
  where pa.user_id is null
  order by u.created_at
  limit 1;

  -- The two reserved demo tenants are safe to recreate.
  delete from public.organizations
  where slug in ('demo-alpha-2026', 'demo-beta-2026');

  insert into public.organizations (name, slug)
  values ('Demo Alpha Support', 'demo-alpha-2026')
  returning id into alpha_id;

  insert into public.organizations (name, slug)
  values ('Demo Beta Services', 'demo-beta-2026')
  returning id into beta_id;

  -- Give the existing platform admin explicit memberships for easy UI selection.
  insert into public.organization_memberships (organization_id, user_id, role, is_active)
  values
    (alpha_id, platform_admin_id, 'ORG_ADMIN', true),
    (beta_id, platform_admin_id, 'ORG_ADMIN', true);

  -- If an existing non-platform user is available, make that user an agent in Alpha.
  if demo_agent_id is not null then
    insert into public.organization_memberships (organization_id, user_id, role, is_active)
    values (alpha_id, demo_agent_id, 'AGENT', true);
  end if;

  insert into public.customers (organization_id, full_name, phone_e164, preferred_language)
  values (alpha_id, 'أحمد حسن - Demo Alpha', '+201000000101', 'ar')
  returning id into alpha_customer_1;

  insert into public.customers (organization_id, full_name, phone_e164, preferred_language)
  values (alpha_id, 'منى إبراهيم - Demo Alpha', '+201000000102', 'ar')
  returning id into alpha_customer_2;

  insert into public.customers (organization_id, full_name, phone_e164, preferred_language)
  values (beta_id, 'محمد علي - Demo Beta', '+201000000201', 'ar')
  returning id into beta_customer_1;

  insert into public.customers (organization_id, full_name, phone_e164, preferred_language)
  values (beta_id, 'سارة محمود - Demo Beta', '+201000000202', 'ar')
  returning id into beta_customer_2;

  insert into public.support_cases
    (organization_id, customer_id, assigned_agent_id, subject, description, status)
  values
    (alpha_id, alpha_customer_1, demo_agent_id, 'انقطاع الإنترنت بعد تغيير الإعدادات', 'العميل يريد التأكد من عودة الخدمة بعد تحديث إعدادات جهاز الراوتر.', 'OPEN')
  returning id into alpha_case_1;

  insert into public.support_cases
    (organization_id, customer_id, assigned_agent_id, subject, description, status)
  values
    (alpha_id, alpha_customer_2, demo_agent_id, 'مشكلة في الفاتورة الشهرية', 'العميلة ترى رسماً إضافياً وتحتاج إلى مراجعة تفاصيل الفاتورة.', 'IN_PROGRESS')
  returning id into alpha_case_2;

  insert into public.support_cases
    (organization_id, customer_id, subject, description, status, resolved_at)
  values
    (beta_id, beta_customer_1, 'تفعيل خدمة الرسائل العربية', 'العميل طلب تفعيل الإشعارات والرسائل باللغة العربية.', 'RESOLVED', now() - interval '2 days')
  returning id into beta_case_1;

  insert into public.support_cases
    (organization_id, customer_id, subject, description, status)
  values
    (beta_id, beta_customer_2, 'تأخر طلب الصيانة', 'العميلة لم تتلق موعداً واضحاً لفريق الصيانة وتحتاج إلى متابعة بشرية.', 'OPEN')
  returning id into beta_case_2;

  insert into public.follow_up_tasks
    (organization_id, case_id, scheduled_for, attempt_number, status)
  values
    (alpha_id, alpha_case_1, now() + interval '2 hours', 1, 'PENDING')
  returning id into alpha_task_pending;

  insert into public.follow_up_tasks
    (organization_id, case_id, scheduled_for, attempt_number, status, completed_at)
  values
    (alpha_id, alpha_case_2, now() - interval '1 day', 1, 'COMPLETED', now() - interval '23 hours')
  returning id into alpha_task_completed;

  insert into public.follow_up_tasks
    (organization_id, case_id, scheduled_for, attempt_number, status)
  values
    (beta_id, beta_case_2, now() - interval '1 hour', 3, 'FAILED')
  returning id into beta_task_failed;

  insert into public.calls
    (organization_id, case_id, follow_up_task_id, provider, provider_call_id, status, outcome, started_at, ended_at, duration_seconds)
  values
    (alpha_id, alpha_case_2, alpha_task_completed, 'simulated', 'DEMO-ALPHA-RESOLVED-001', 'COMPLETED', 'ANSWERED_RESOLVED', now() - interval '23 hours 30 minutes', now() - interval '23 hours 27 minutes', 180)
  returning id into alpha_call_resolved;

  insert into public.calls
    (organization_id, case_id, provider, provider_call_id, status, outcome, started_at, ended_at, duration_seconds)
  values
    (alpha_id, alpha_case_1, 'simulated', 'DEMO-ALPHA-ESCALATED-001', 'COMPLETED', 'ANSWERED_UNRESOLVED', now() - interval '3 hours', now() - interval '2 hours 56 minutes', 240)
  returning id into alpha_call_escalated;

  insert into public.calls
    (organization_id, case_id, follow_up_task_id, provider, provider_call_id, status, outcome, started_at, ended_at, duration_seconds)
  values
    (beta_id, beta_case_1, null, 'simulated', 'DEMO-BETA-NOANSWER-001', 'COMPLETED', 'NO_ANSWER', now() - interval '2 days', now() - interval '2 days' + interval '25 seconds', 25)
  returning id into beta_call_no_answer;

  insert into public.calls
    (organization_id, case_id, follow_up_task_id, provider, provider_call_id, status, outcome)
  values
    (beta_id, beta_case_2, beta_task_failed, 'simulated', 'DEMO-BETA-FAILED-001', 'FAILED', 'FAILED')
  returning id into beta_call_failed;

  insert into public.call_events
    (organization_id, call_id, provider, provider_event_id, event_type, payload)
  values
    (alpha_id, alpha_call_resolved, 'simulated', 'DEMO-EVENT-ALPHA-001', 'completed', '{"demo":true,"result":"resolved"}'::jsonb),
    (alpha_id, alpha_call_escalated, 'simulated', 'DEMO-EVENT-ALPHA-002', 'completed', '{"demo":true,"result":"unresolved"}'::jsonb),
    (beta_id, beta_call_no_answer, 'simulated', 'DEMO-EVENT-BETA-001', 'no-answer', '{"demo":true,"result":"no_answer"}'::jsonb),
    (beta_id, beta_call_failed, 'simulated', 'DEMO-EVENT-BETA-002', 'failed', '{"demo":true,"result":"failed"}'::jsonb);

  insert into public.call_turns
    (organization_id, call_id, turn_number, speaker, text_raw, text_norm, language, stt_model)
  values
    (alpha_id, alpha_call_resolved, 0, 'AI', 'أهلاً بك، هل تم حل المشكلة؟', 'اهلا بك هل تم حل المشكلة', 'ar', 'demo'),
    (alpha_id, alpha_call_resolved, 1, 'CUSTOMER', 'نعم، المشكلة اتحلت وشكراً لكم.', 'نعم المشكلة اتحلت وشكرا لكم', 'ar', 'demo'),
    (alpha_id, alpha_call_escalated, 0, 'AI', 'هل تم حل مشكلة الفاتورة؟', 'هل تم حل مشكلة الفاتورة', 'ar', 'demo'),
    (alpha_id, alpha_call_escalated, 1, 'CUSTOMER', 'لا، ما زالت المشكلة موجودة وأحتاج إلى موظف.', 'لا ما زالت المشكلة موجودة واحتاج الى موظف', 'ar', 'demo');

  insert into public.escalations
    (organization_id, call_id, reason, brief_msa, assigned_human_id, status, resolved_at)
  values
    (alpha_id, alpha_call_escalated, 'العميل أفاد بأن المشكلة ما زالت قائمة', 'مراجعة الفاتورة والتواصل مع العميل خلال يوم عمل.', demo_agent_id, 'PENDING', null),
    (beta_id, beta_call_no_answer, 'لم يتمكن النظام من الوصول إلى العميل', 'إعادة المحاولة أو التواصل عبر قناة بديلة.', null, 'PENDING', null),
    (beta_id, beta_call_failed, 'فشل مزود الاتصال في إنشاء المكالمة', 'التحقق من إعدادات مزود الاتصال قبل إعادة المحاولة.', null, 'RESOLVED', now() - interval '3 hours');

  insert into public.knowledge_documents
    (organization_id, uploaded_by, title, storage_path, mime_type, language, checksum, status, source_metadata)
  values
    (alpha_id, platform_admin_id, 'دليل الدعم - Demo Alpha', 'demo-alpha-2026/guide.txt', 'text/plain', 'ar', 'demo-alpha-checksum', 'PROCESSED', '{"demo":true}'::jsonb)
  returning id into alpha_doc;

  insert into public.knowledge_documents
    (organization_id, uploaded_by, title, storage_path, mime_type, language, checksum, status, source_metadata)
  values
    (beta_id, platform_admin_id, 'سياسة الخدمة - Demo Beta', 'demo-beta-2026/policy.txt', 'text/plain', 'ar', 'demo-beta-checksum', 'PROCESSED', '{"demo":true}'::jsonb)
  returning id into beta_doc;

  insert into public.knowledge_chunks
    (organization_id, document_id, chunk_index, content_raw, content_norm, page_number)
  values
    (alpha_id, alpha_doc, 0, 'في حالة استمرار مشكلة الإنترنت، يجب التحقق من حالة الخدمة ثم فتح تصعيد للموظف المختص.', 'في حالة استمرار مشكلة الانترنت يجب التحقق من حالة الخدمة ثم فتح تصعيد للموظف المختص', 1),
    (alpha_id, alpha_doc, 1, 'يتم التواصل مع العميل خلال يوم عمل عند تحويل الحالة إلى فريق الدعم البشري.', 'يتم التواصل مع العميل خلال يوم عمل عند تحويل الحالة الى فريق الدعم البشري', 1),
    (beta_id, beta_doc, 0, 'طلبات الصيانة المتأخرة تحتاج إلى مراجعة الموعد وإعادة التواصل مع العميل.', 'طلبات الصيانة المتأخرة تحتاج الى مراجعة الموعد واعادة التواصل مع العميل', 1),
    (beta_id, beta_doc, 1, 'يجب تسجيل نتيجة كل محاولة اتصال في سجل الحالة.', 'يجب تسجيل نتيجة كل محاولة اتصال في سجل الحالة', 1);

  insert into public.fcr_reports
    (organization_id, period_start, period_end, total_calls, resolved_on_first_follow_up, escalated_calls, report_msa)
  values
    (alpha_id, current_date - 30, current_date, 2, 1, 1, 'تقرير تجريبي: حالة واحدة حُلت من أول متابعة وحالة واحدة صُعّدت.'),
    (beta_id, current_date - 30, current_date, 2, 1, 1, 'تقرير تجريبي: توجد مكالمة لم يتم الرد عليها ومكالمة فاشلة.');

  raise notice 'Demo data inserted. Alpha organization: %, Beta organization: %, demo agent: %', alpha_id, beta_id, demo_agent_id;
end $$;

commit;

-- Verification queries. Run separately after the seed script if desired.
select
  o.name as organization_name,
  o.slug,
  count(distinct c.id) as customers,
  count(distinct sc.id) as cases,
  count(distinct f.id) as follow_up_tasks,
  count(distinct ca.id) as calls,
  count(distinct e.id) as escalations,
  count(distinct kd.id) as documents
from public.organizations o
left join public.customers c on c.organization_id = o.id
left join public.support_cases sc on sc.organization_id = o.id
left join public.follow_up_tasks f on f.organization_id = o.id
left join public.calls ca on ca.organization_id = o.id
left join public.escalations e on e.organization_id = o.id
left join public.knowledge_documents kd on kd.organization_id = o.id
where o.slug in ('demo-alpha-2026', 'demo-beta-2026')
group by o.id, o.name, o.slug
order by o.slug;

select
  o.slug,
  e.status,
  count(*) as total
from public.escalations e
join public.organizations o on o.id = e.organization_id
where o.slug in ('demo-alpha-2026', 'demo-beta-2026')
group by o.slug, e.status
order by o.slug, e.status;

select
  o.slug,
  f.status,
  count(*) as total
from public.follow_up_tasks f
join public.organizations o on o.id = f.organization_id
where o.slug in ('demo-alpha-2026', 'demo-beta-2026')
group by o.slug, f.status
order by o.slug, f.status;

-- Cleanup section: run ONLY when you want to delete the demo data.
-- delete from public.organizations
-- where slug in ('demo-alpha-2026', 'demo-beta-2026');
