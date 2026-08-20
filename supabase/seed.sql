-- Development seed only.
-- Create Auth users in Supabase Auth first, then replace the UUID placeholders below.
-- Never use this seed in production without reviewing the data.

insert into public.organizations (name, slug)
values
  ('Alpha Support', 'alpha-support'),
  ('Beta Support', 'beta-support')
on conflict (slug) do nothing;

-- Example after creating real Supabase Auth users:
--
-- insert into public.profiles (id, full_name, preferred_language)
-- values
--   ('00000000-0000-0000-0000-000000000001', 'Alpha Admin', 'ar'),
--   ('00000000-0000-0000-0000-000000000002', 'Alpha Agent', 'ar'),
--   ('00000000-0000-0000-0000-000000000003', 'Beta Admin', 'ar'),
--   ('00000000-0000-0000-0000-000000000004', 'Beta Agent', 'ar')
-- on conflict (id) do nothing;
--
-- insert into public.organization_memberships (organization_id, user_id, role)
-- select o.id, x.user_id, x.role::public.organization_member_role
-- from public.organizations o
-- join (values
--   ('alpha-support', '00000000-0000-0000-0000-000000000001'::uuid, 'ORG_ADMIN'),
--   ('alpha-support', '00000000-0000-0000-0000-000000000002'::uuid, 'AGENT'),
--   ('beta-support', '00000000-0000-0000-0000-000000000003'::uuid, 'ORG_ADMIN'),
--   ('beta-support', '00000000-0000-0000-0000-000000000004'::uuid, 'AGENT')
--) as x(slug, user_id, role) on x.slug = o.slug
-- on conflict (organization_id, user_id) do update
-- set role = excluded.role, is_active = true;
