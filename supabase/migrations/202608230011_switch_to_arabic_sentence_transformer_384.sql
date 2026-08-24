-- Migration 0011: switch RAG embeddings to the Arabic Sentence Transformer.
--
-- The existing database contract used 3072-dimensional vectors for the
-- OpenAI embedding path. The selected local Arabic model returns 384 values,
-- so the old vectors must be invalidated and every document must be reindexed.
-- This migration intentionally clears embeddings; it never mixes dimensions
-- inside one pgvector column or index.

-- Remove old function signatures before changing the column type.
drop function if exists public.hybrid_knowledge_chunks(
  extensions.vector(3072), text, uuid, integer
);
drop function if exists public.match_knowledge_chunks(
  extensions.vector(3072), uuid, integer
);

drop index if exists public.chunks_embedding_idx;

-- Existing vectors cannot be converted semantically. They must be recreated
-- from the source chunks by the document-ingestion pipeline.
update public.knowledge_chunks
set embedding = null;

alter table public.knowledge_chunks
  alter column embedding type extensions.vector(384)
  using null::extensions.vector(384);

create index chunks_embedding_idx on public.knowledge_chunks
  using hnsw ((embedding::extensions.halfvec(384)) extensions.halfvec_cosine_ops);

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
    1 - (kc.embedding <=> query_embedding) as similarity
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
      1 - ((kc.embedding::extensions.halfvec(384)) <=>
           (query_embedding::extensions.halfvec(384))) as dense_similarity,
      ts_rank_cd(kc.search_vector, plainto_tsquery('simple', query_text)) as lexical_score
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
      + (0.25 * least(coalesce(c.lexical_score, 0), 1)) as similarity
  from candidates c
  order by similarity desc, c.id
  limit greatest(1, least(match_count, 100));
$$;

grant execute on function public.hybrid_knowledge_chunks(
  extensions.vector(384), text, uuid, integer
) to authenticated;

-- Mark source documents for operational visibility. The ingestion service will
-- replace their chunks' embeddings on the next upload/re-index operation.
update public.knowledge_documents d
set status = 'NEEDS_REINDEX', updated_at = now()
where exists (
  select 1
  from public.knowledge_chunks c
  where c.document_id = d.id
);
