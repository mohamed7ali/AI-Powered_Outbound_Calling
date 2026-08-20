-- Arabic AI-Powered Outbound Calls
-- Migration 0001: core domain schema, tenant helpers, RLS, and vector retrieval.
-- Apply with Supabase migrations or the Supabase SQL Editor.

create extension if not exists pgcrypto;
create extension if not exists vector with schema extensions;

create schema if not exists private;

create type public.organization_member_role as enum ('ORG_ADMIN', 'AGENT');
create type public.case_status as enum ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED');
create type public.call_outcome as enum (
  'PENDING',
  'ANSWERED_RESOLVED',
  'ANSWERED_UNRESOLVED',
  'NO_ANSWER',
  'BUSY',
  'FAILED',
  'ESCALATED'
);
create type public.call_speaker as enum ('CUSTOMER', 'AI', 'HUMAN');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  phone text,
  preferred_language text not null default 'ar',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.platform_admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organization_memberships (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.organization_member_role not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table public.customers (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  full_name text not null,
  phone_e164 text not null,
  preferred_language text not null default 'ar',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.support_cases (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  customer_id uuid not null references public.customers(id) on delete restrict,
  assigned_agent_id uuid references auth.users(id) on delete set null,
  subject text not null,
  description text not null,
  status public.case_status not null default 'OPEN',
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.follow_up_tasks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  case_id uuid not null references public.support_cases(id) on delete cascade,
  scheduled_for timestamptz not null,
  attempt_number integer not null default 1 check (attempt_number > 0),
  status text not null default 'PENDING',
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table public.calls (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  case_id uuid not null references public.support_cases(id) on delete cascade,
  follow_up_task_id uuid references public.follow_up_tasks(id) on delete set null,
  provider text not null,
  provider_call_id text,
  status text not null default 'QUEUED',
  outcome public.call_outcome not null default 'PENDING',
  started_at timestamptz,
  ended_at timestamptz,
  duration_seconds integer check (duration_seconds is null or duration_seconds >= 0),
  created_at timestamptz not null default now()
);

create table public.call_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  call_id uuid not null references public.calls(id) on delete cascade,
  provider text not null,
  provider_event_id text,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (provider, provider_event_id)
);

create table public.call_turns (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  call_id uuid not null references public.calls(id) on delete cascade,
  turn_number integer not null check (turn_number >= 0),
  speaker public.call_speaker not null,
  text_raw text not null,
  text_norm text,
  language text not null default 'ar',
  stt_model text,
  duration_ms integer check (duration_ms is null or duration_ms >= 0),
  audio_path text,
  audio_retained boolean not null default false,
  created_at timestamptz not null default now(),
  unique (call_id, turn_number)
);

create table public.escalations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  call_id uuid not null references public.calls(id) on delete cascade,
  reason text not null,
  brief_msa text,
  assigned_human_id uuid references auth.users(id) on delete set null,
  status text not null default 'PENDING',
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table public.fcr_reports (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  period_start date not null,
  period_end date not null,
  total_calls integer not null default 0,
  resolved_on_first_follow_up integer not null default 0,
  escalated_calls integer not null default 0,
  report_msa text,
  generated_at timestamptz not null default now(),
  unique (organization_id, period_start, period_end),
  check (period_end >= period_start)
);

create table public.knowledge_documents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  uploaded_by uuid not null references auth.users(id) on delete restrict,
  title text not null,
  storage_bucket text not null default 'organization-documents',
  storage_path text not null,
  mime_type text not null,
  language text not null default 'ar',
  checksum text,
  status text not null default 'UPLOADED',
  source_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, storage_path)
);

create table public.knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  document_id uuid not null references public.knowledge_documents(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  content_raw text not null,
  content_norm text not null,
  page_number integer,
  embedding extensions.vector(3072),
  search_vector tsvector generated always as (
    to_tsvector('simple', coalesce(content_norm, ''))
  ) stored,
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create table public.agent_conversations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.agent_messages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  conversation_id uuid not null references public.agent_conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete set null,
  actor_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  resource_type text,
  resource_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Indexes for tenant filters, joins, scheduling, and retrieval.
create index memberships_user_idx on public.organization_memberships (user_id, organization_id)
  where is_active = true;
create index memberships_org_idx on public.organization_memberships (organization_id, user_id)
  where is_active = true;
create index customers_org_idx on public.customers (organization_id, created_at desc);
create index cases_org_status_idx on public.support_cases (organization_id, status, created_at desc);
create index cases_org_assignee_idx on public.support_cases (organization_id, assigned_agent_id);
create index followups_due_idx on public.follow_up_tasks (organization_id, scheduled_for)
  where status = 'PENDING';
create index calls_org_idx on public.calls (organization_id, created_at desc);
create index turns_call_idx on public.call_turns (organization_id, call_id, turn_number);
create index documents_org_idx on public.knowledge_documents (organization_id, created_at desc);
create index chunks_org_idx on public.knowledge_chunks (organization_id, document_id, chunk_index);
create index chunks_search_idx on public.knowledge_chunks using gin (search_vector);
create index chunks_embedding_idx on public.knowledge_chunks
  using hnsw ((embedding::extensions.halfvec(3072)) extensions.halfvec_cosine_ops);
create index messages_conversation_idx on public.agent_messages
  (organization_id, conversation_id, created_at);

-- The direct Python connection can set app.current_user_id. Supabase REST requests
-- provide request.jwt.claim.sub. This allows the same policies to protect both paths.
create or replace function private.current_actor_id()
returns uuid
language sql
stable
as $$
  select nullif(
    coalesce(
      nullif(current_setting('app.current_user_id', true), ''),
      nullif(current_setting('request.jwt.claim.sub', true), '')
    ),
    ''
  )::uuid;
$$;

create or replace function private.is_platform_admin()
returns boolean
language sql
stable
security definer
set search_path = public, private
as $$
  select exists (
    select 1 from public.platform_admins
    where user_id = (select private.current_actor_id())
  );
$$;

create or replace function private.is_org_member(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, private
as $$
  select (select private.is_platform_admin())
      or exists (
        select 1 from public.organization_memberships m
        where m.organization_id = target_org
          and m.user_id = (select private.current_actor_id())
          and m.is_active = true
      );
$$;

create or replace function private.is_org_admin(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, private
as $$
  select (select private.is_platform_admin())
      or exists (
        select 1 from public.organization_memberships m
        where m.organization_id = target_org
          and m.user_id = (select private.current_actor_id())
          and m.role = 'ORG_ADMIN'
          and m.is_active = true
      );
$$;

create or replace function private.is_assigned_agent(target_agent uuid, target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, private
as $$
  select target_agent = (select private.current_actor_id())
     and (select private.is_org_member(target_org));
$$;

create or replace function private.storage_org_id(object_name text)
returns uuid
language plpgsql
stable
as $$
begin
  return split_part(object_name, '/', 1)::uuid;
exception when invalid_text_representation then
  return null;
end;
$$;

-- Enable RLS on every table reachable by the application API.
alter table public.profiles enable row level security;
alter table public.platform_admins enable row level security;
alter table public.organizations enable row level security;
alter table public.organization_memberships enable row level security;
alter table public.customers enable row level security;
alter table public.support_cases enable row level security;
alter table public.follow_up_tasks enable row level security;
alter table public.calls enable row level security;
alter table public.call_events enable row level security;
alter table public.call_turns enable row level security;
alter table public.escalations enable row level security;
alter table public.fcr_reports enable row level security;
alter table public.knowledge_documents enable row level security;
alter table public.knowledge_chunks enable row level security;
alter table public.agent_conversations enable row level security;
alter table public.agent_messages enable row level security;
alter table public.audit_events enable row level security;

-- Read policies.
create policy profiles_read on public.profiles for select to authenticated
using (
  id = (select private.current_actor_id())
  or exists (
    select 1 from public.organization_memberships mine
    join public.organization_memberships theirs
      on theirs.organization_id = mine.organization_id
    where mine.user_id = (select private.current_actor_id())
      and mine.is_active = true
      and theirs.user_id = profiles.id
      and theirs.is_active = true
  )
  or (select private.is_platform_admin())
);

create policy platform_admins_read on public.platform_admins for select to authenticated
using (user_id = (select private.current_actor_id()) or (select private.is_platform_admin()));

create policy organizations_read on public.organizations for select to authenticated
using ((select private.is_org_member(id)));

create policy memberships_read on public.organization_memberships for select to authenticated
using ((select private.is_org_member(organization_id)));

create policy customers_read on public.customers for select to authenticated
using ((select private.is_org_member(organization_id)));

create policy cases_read on public.support_cases for select to authenticated
using (
  (select private.is_org_member(organization_id))
  and (
    (select private.is_org_admin(organization_id))
    or assigned_agent_id = (select private.current_actor_id())
  )
);

create policy followups_read on public.follow_up_tasks for select to authenticated
using ((select private.is_org_member(organization_id)));
create policy calls_read on public.calls for select to authenticated
using ((select private.is_org_member(organization_id)));
create policy call_events_read on public.call_events for select to authenticated
using ((select private.is_org_member(organization_id)));
create policy call_turns_read on public.call_turns for select to authenticated
using ((select private.is_org_member(organization_id)));
create policy escalations_read on public.escalations for select to authenticated
using ((select private.is_org_member(organization_id)));
create policy reports_read on public.fcr_reports for select to authenticated
using ((select private.is_org_member(organization_id)));

create policy documents_read on public.knowledge_documents for select to authenticated
using ((select private.is_org_member(organization_id)));
create policy chunks_read on public.knowledge_chunks for select to authenticated
using ((select private.is_org_member(organization_id)));

create policy conversations_read on public.agent_conversations for select to authenticated
using (
  (select private.is_platform_admin())
  or (select private.is_org_admin(organization_id))
  or user_id = (select private.current_actor_id())
);

create policy messages_read on public.agent_messages for select to authenticated
using ((select private.is_org_member(organization_id)));

create policy audit_read on public.audit_events for select to authenticated
using ((select private.is_platform_admin()) or (select private.is_org_admin(organization_id)));

-- Organization creation is a platform-admin operation.
create policy organizations_insert on public.organizations for insert to authenticated
with check ((select private.is_platform_admin()));
create policy organizations_update on public.organizations for update to authenticated
using ((select private.is_platform_admin()) or (select private.is_org_admin(id)))
with check ((select private.is_platform_admin()) or (select private.is_org_admin(id)));

-- Membership administration: organization admins can create AGENTs only;
-- platform admins can create either organization role.
create policy memberships_insert on public.organization_memberships for insert to authenticated
with check (
  (select private.is_platform_admin())
  or (
    role = 'AGENT'
    and (select private.is_org_admin(organization_id))
  )
);
create policy memberships_update on public.organization_memberships for update to authenticated
using ((select private.is_platform_admin()) or (select private.is_org_admin(organization_id)))
with check (
  (select private.is_platform_admin())
  or (
    role = 'AGENT'
    and (select private.is_org_admin(organization_id))
  )
);
create policy memberships_delete on public.organization_memberships for delete to authenticated
using ((select private.is_platform_admin()) or (select private.is_org_admin(organization_id)));

-- Organization operational writes.
create policy customers_insert on public.customers for insert to authenticated
with check ((select private.is_org_admin(organization_id)));
create policy customers_update on public.customers for update to authenticated
using ((select private.is_org_admin(organization_id)))
with check ((select private.is_org_admin(organization_id)));
create policy customers_delete on public.customers for delete to authenticated
using ((select private.is_org_admin(organization_id)));

create policy cases_insert on public.support_cases for insert to authenticated
with check ((select private.is_org_admin(organization_id)));
create policy cases_update on public.support_cases for update to authenticated
using (
  (select private.is_org_admin(organization_id))
  or (select private.is_assigned_agent(assigned_agent_id, organization_id))
)
with check (
  (select private.is_org_admin(organization_id))
  or (select private.is_assigned_agent(assigned_agent_id, organization_id))
);

create policy followups_insert on public.follow_up_tasks for insert to authenticated
with check ((select private.is_org_admin(organization_id)));
create policy followups_update on public.follow_up_tasks for update to authenticated
using ((select private.is_org_admin(organization_id)))
with check ((select private.is_org_admin(organization_id)));

create policy documents_insert on public.knowledge_documents for insert to authenticated
with check (
  (select private.is_org_admin(organization_id))
  and uploaded_by = (select private.current_actor_id())
);
create policy documents_update on public.knowledge_documents for update to authenticated
using ((select private.is_org_admin(organization_id)))
with check ((select private.is_org_admin(organization_id)));
create policy documents_delete on public.knowledge_documents for delete to authenticated
using ((select private.is_org_admin(organization_id)));

create policy chunks_insert on public.knowledge_chunks for insert to authenticated
with check ((select private.is_org_admin(organization_id)));
create policy chunks_delete on public.knowledge_chunks for delete to authenticated
using ((select private.is_org_admin(organization_id)));

create policy conversations_insert on public.agent_conversations for insert to authenticated
with check (
  (select private.is_org_member(organization_id))
  and user_id = (select private.current_actor_id())
);
create policy messages_insert on public.agent_messages for insert to authenticated
with check (
  (select private.is_org_member(organization_id))
  and exists (
    select 1 from public.agent_conversations c
    where c.id = conversation_id
      and c.organization_id = agent_messages.organization_id
      and (c.user_id = (select private.current_actor_id())
           or (select private.is_org_admin(c.organization_id)))
  )
);

create policy audit_insert on public.audit_events for insert to authenticated
with check (
  actor_id = (select private.current_actor_id())
  and (
    organization_id is null
    or (select private.is_org_member(organization_id))
  )
);

-- System/provider writes are expected to use a protected server connection or
-- Supabase secret key. Do not expose that key in Gradio, a browser, or a repo.

-- Supabase Storage bucket and policies. These statements require the standard
-- Supabase storage schema, which is present in a Supabase project.
insert into storage.buckets (id, name, public)
values ('organization-documents', 'organization-documents', false)
on conflict (id) do update set public = false;

create policy org_documents_read on storage.objects
for select to authenticated
using (
  bucket_id = 'organization-documents'
  and (select private.is_org_member((select private.storage_org_id(name))))
);

create policy org_documents_insert on storage.objects
for insert to authenticated
with check (
  bucket_id = 'organization-documents'
  and (select private.is_org_admin((select private.storage_org_id(name))))
);

create policy org_documents_update on storage.objects
for update to authenticated
using (
  bucket_id = 'organization-documents'
  and (select private.is_org_admin((select private.storage_org_id(name))))
)
with check (
  bucket_id = 'organization-documents'
  and (select private.is_org_admin((select private.storage_org_id(name))))
);

create policy org_documents_delete on storage.objects
for delete to authenticated
using (
  bucket_id = 'organization-documents'
  and (select private.is_org_admin((select private.storage_org_id(name))))
);

-- Permission-aware vector search. RLS and explicit organization filtering both apply.
create or replace function public.match_knowledge_chunks(
  query_embedding extensions.vector(3072),
  match_organization_id uuid,
  match_count integer default 10
)
returns table (
  id uuid,
  document_id uuid,
  organization_id uuid,
  content_raw text,
  page_number integer,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public, private, extensions
as $$
  select
    kc.id,
    kc.document_id,
    kc.organization_id,
    kc.content_raw,
    kc.page_number,
    1 - (kc.embedding <=> query_embedding) as similarity
  from public.knowledge_chunks kc
  where kc.organization_id = match_organization_id
    and kc.embedding is not null
    and (select private.is_org_member(kc.organization_id))
  order by kc.embedding <=> query_embedding
  limit greatest(1, least(match_count, 100));
$$;

grant execute on function public.match_knowledge_chunks(extensions.vector(3072), uuid, integer)
  to authenticated;
