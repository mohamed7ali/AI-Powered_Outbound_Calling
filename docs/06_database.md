# Database and Supabase Integration

The repository now uses Supabase as a managed PostgreSQL database. Supabase Auth owns login identities, PostgreSQL stores business data, Supabase Storage stores private organization documents, and `pgvector` stores document embeddings.

## Migration files

- `supabase/migrations/202608160001_initial_schema.sql` creates the domain tables, enums, indexes, permission helper functions, RLS policies, private document bucket, and permission-aware vector search function.
- `supabase/seed.sql` creates two development organizations. It intentionally does not create Auth users because Auth users must be created through Supabase Auth first.

The schema has explicit organization ownership for customers, support cases, follow-up tasks, calls, transcripts, escalations, reports, documents, chunks, conversations, messages, and audit events. A normal organization administrator can manage only their own organization. Agents can read their organization’s knowledge base and work assigned cases, but cannot administer organizations or memberships.

## Supabase setup

1. Create a development Supabase project.
2. Enable the `vector` extension from **Database → Extensions** if it is not already enabled.
3. Run `supabase/migrations/202608160001_initial_schema.sql` in the Supabase SQL Editor, or apply it with the Supabase CLI.
4. Run `supabase/seed.sql`.
5. Create the development users in **Authentication → Users**.
6. Insert matching rows into `public.profiles` and `public.organization_memberships` using the real Auth UUIDs.
7. Add one platform-admin UUID to `public.platform_admins`.
8. Use a private Storage bucket named `organization-documents` and paths of the form `<organization_uuid>/<document_uuid>/filename.pdf`.

Do not commit `.env`. `SUPABASE_SERVICE_ROLE_KEY` is a server-only secret and must never be placed in Gradio/browser code. It bypasses RLS. User-facing transactions should use the authenticated context; trusted workers and provider callbacks should be separate, explicit system paths.

## Repository integration

`src/outbound_ai/db/connection.py` provides `Database`, `TenantContext`, and transaction-local context variables. A user-facing transaction must include the authenticated actor UUID and the active organization UUID. The transaction sets `app.current_user_id`, and the migration’s RLS helpers use it when a direct PostgreSQL connection is used.

`src/outbound_ai/db/repositories/organizations.py` contains organization and membership operations. `src/outbound_ai/db/repositories/knowledge.py` registers documents, inserts raw/normalized Arabic chunks and embeddings, and calls `match_knowledge_chunks`. Higher layers should use these repositories rather than writing SQL directly.

The active RAG embedding model is the Arabic Sentence Transformer `Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet`, which produces **384-dimensional vectors**. Migration `202608230011_switch_to_arabic_sentence_transformer_384.sql` changes the vector column and RPC signatures to `extensions.vector(384)`, clears old embeddings, and requires complete document re-ingestion. Migration `202608230012_calibrate_hybrid_retrieval_scores.sql` bounds dense, lexical, and hybrid scores to the `0..1` ranking range. These scores are not probabilities. Do not change `RAG_EMBEDDING_DIM` silently; any future model or dimension change requires a new migration and re-indexing.

## Applying with the Supabase CLI

After installing and linking the Supabase CLI, initialize the repository once if `supabase/config.toml` does not exist:

```bash
supabase init
```

Then review the generated configuration and apply the migrations:

```bash
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase db push
```

If the repository is not yet configured as a Supabase CLI project, initialize it once from the repository root and review the generated `supabase/config.toml` before pushing migrations.

For a direct development database connection, copy `.env.example` to `.env` and set `DATABASE_URL`, `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_RLS_ROLE`, and `DOCUMENT_STORAGE_BUCKET`. The Python pool requires `psycopg[binary,pool]`, already declared by `pyproject.toml`.

## Isolation test

Create Alpha and Beta organizations, each with an admin, agent, customer, and document. Run the application with an Alpha actor context and verify that:

- Alpha can read Alpha documents and chunks.
- Alpha cannot read Beta documents, chunks, users, customers, calls, or reports.
- Alpha cannot create a Beta membership or upload a document under Beta.
- A Beta query returns no Alpha citations.
- A platform admin can select either organization deliberately.

The most important security rule is that retrieval receives an organization UUID from a server-validated `TenantContext`; it must never trust an arbitrary organization UUID sent by a normal user interface.
