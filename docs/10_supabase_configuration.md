# Supabase Configuration Map

## Values used by `.env`

| Variable | Where to get it | What to use for this repository |
|---|---|---|
| `SUPABASE_URL` | Supabase Dashboard → **Connect** or **Integrations → Data API** | The project URL, for example `https://PROJECT_REF.supabase.co` |
| `SUPABASE_ANON_KEY` | Dashboard → **Settings → API Keys → Legacy API Keys** | The `anon` public key for compatibility with the current UI login code. A publishable key can be adopted after the client configuration is updated. |
| `SUPABASE_SERVICE_ROLE_KEY` | Dashboard → **Settings → API Keys → Legacy API Keys** | The `service_role` key for the current server-side Storage and Auth Admin code. Never expose it to the browser or commit it. |
| `DATABASE_URL` | Dashboard → **Connect** → PostgreSQL connection string | Prefer **Shared Pooler → Session mode** for a Codespaces IPv4 development environment. The application uses a persistent psycopg connection pool. |
| `SUPABASE_JWT_SECRET` | Dashboard → **Settings → JWT Keys** only for a legacy HS256 setup | Leave blank when the project uses asymmetric signing keys and JWKS. The API will use `https://PROJECT_REF.supabase.co/auth/v1/.well-known/jwks.json`. |
| `SUPABASE_JWT_AUDIENCE` | Application setting, not copied from the dashboard | Keep `authenticated`. |
| `DOCUMENT_STORAGE_BUCKET` | Application setting | Keep `organization-documents`; the migration creates private Storage policies for this bucket. |

Supabase now offers publishable and secret API keys in addition to the legacy `anon` and `service_role` keys. The current repository explicitly uses the legacy variable names and sends the server key to Supabase Auth Admin and Storage endpoints, so use the legacy `anon` and `service_role` values initially. Do not paste secret values into chat. The server-side `service_role` key bypasses RLS and must only be stored in a protected server environment.

## Minimal first-test `.env`

For the first Codespaces test, use simulated telephony and deterministic embeddings:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_LEGACY_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_LEGACY_SERVICE_ROLE_KEY
DATABASE_URL=YOUR_SESSION_POOLER_CONNECTION_STRING
SUPABASE_JWT_SECRET=
SUPABASE_JWT_AUDIENCE=authenticated
DOCUMENT_STORAGE_BUCKET=organization-documents
TELEPHONY_PROVIDER=simulated
RAG_EMBEDDING_PROVIDER=deterministic
API_HOST=0.0.0.0
API_PORT=8000
GRADIO_PORT=7860
API_BASE_URL=http://localhost:8000
```

Leave Vonage and `PUBLIC_WEBHOOK_BASE_URL` blank until the Supabase, RAG, simulated-call, and tenant-isolation tests pass. Configure the Vonage variables only for the later live-call acceptance test.

## Database connection choice

Supabase documents direct connections as suitable for long-lived backends when IPv6 is available. Shared Pooler session mode is the practical alternative for persistent application traffic from IPv4-only environments such as many Codespaces configurations. Transaction mode uses port `6543` and is intended for transient/serverless traffic; it is not the first choice for this application’s persistent psycopg pool.

## Applying migrations

For a new Supabase project, use the repository migrations in order. With the Supabase CLI available in Codespaces:

```bash
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db push
```

For a new remote project with no pre-existing schema, `db push` applies the versioned migrations. Do not run `supabase db reset` against the hosted project. After applying the migrations, inspect the Table Editor for `organizations`, `organization_memberships`, `customers`, `support_cases`, `calls`, `knowledge_documents`, `knowledge_chunks`, and `fcr_reports`.

## First platform administrator

Create a user in Supabase Dashboard → **Authentication → Users → Add user**. Copy the user UUID, then run this in the Supabase SQL Editor:

```sql
insert into public.platform_admins (user_id)
values ('AUTH_USER_UUID')
on conflict (user_id) do nothing;

insert into public.profiles (id, full_name, preferred_language)
values ('AUTH_USER_UUID', 'Platform Administrator', 'ar')
on conflict (id) do update
set full_name = excluded.full_name,
    preferred_language = excluded.preferred_language,
    updated_at = now();
```

After this, log in through the Gradio UI. Use the Administration tab to create the first organization, then invite an organization administrator or agent. The platform administrator must explicitly select an organization UUID before accessing organization-scoped campaign, document, agent, or report tabs.

## References

[1]: https://supabase.com/docs/guides/getting-started/api-keys "Supabase API keys"
[2]: https://supabase.com/docs/guides/database/connecting-to-postgres "Supabase PostgreSQL connection methods"
[3]: https://supabase.com/docs/guides/local-development/database-migrations "Supabase database migrations"
[4]: https://supabase.com/docs/guides/auth/signing-keys "Supabase JWT signing keys and JWKS"
