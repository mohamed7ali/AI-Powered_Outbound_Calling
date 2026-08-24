-- Migration 0012: calibrate hybrid retrieval scores to a bounded 0..1 range.
--
-- These values are ranking indicators, not probabilities. Clamping prevents
-- negative cosine-derived values or unbounded lexical values from being shown
-- as misleading relevance scores in the UI.

create or replace function public.match_knowledge_chunks(
  query_embedding extensions.vector(384),
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
    greatest(0.0, least(1.0, 1 - (kc.embedding <=> query_embedding))) as similarity
  from public.knowledge_chunks kc
  where kc.organization_id = match_organization_id
    and kc.embedding is not null
    and (select private.is_org_member(kc.organization_id))
  order by kc.embedding <=> query_embedding
  limit greatest(1, least(match_count, 100));
$$;

grant execute on function public.match_knowledge_chunks(
  extensions.vector(384), uuid, integer
) to authenticated;

create or replace function public.hybrid_knowledge_chunks(
  query_embedding extensions.vector(384),
  query_text text,
  match_organization_id uuid,
  match_count integer default 8
)
returns table (
  id uuid,
  document_id uuid,
  organization_id uuid,
  content_raw text,
  page_number integer,
  dense_similarity double precision,
  lexical_score double precision,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public, private, extensions
as $$
  with candidates as (
    select
      kc.id,
      kc.document_id,
      kc.organization_id,
      kc.content_raw,
      kc.page_number,
      greatest(
        0.0,
        least(
          1.0,
          1 - ((kc.embedding::extensions.halfvec(384)) <=>
               (query_embedding::extensions.halfvec(384)))
        )
      ) as dense_similarity,
      greatest(
        0.0,
        least(1.0, ts_rank_cd(kc.search_vector, plainto_tsquery('simple', query_text)))
      ) as lexical_score
    from public.knowledge_chunks kc
    where kc.organization_id = match_organization_id
      and (select private.is_org_member(kc.organization_id))
      and (
        kc.embedding is not null
        or kc.search_vector @@ plainto_tsquery('simple', query_text)
      )
  )
  select
    c.id,
    c.document_id,
    c.organization_id,
    c.content_raw,
    c.page_number,
    coalesce(c.dense_similarity, 0),
    coalesce(c.lexical_score, 0),
    (0.75 * coalesce(c.dense_similarity, 0))
      + (0.25 * coalesce(c.lexical_score, 0)) as similarity
  from candidates c
  order by similarity desc, c.id
  limit greatest(1, least(match_count, 100));
$$;

grant execute on function public.hybrid_knowledge_chunks(
  extensions.vector(384), text, uuid, integer
) to authenticated;
