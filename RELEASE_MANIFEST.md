# Arabic AI Outbound Calls — Consolidated Release

This archive is the consolidated project state through August 20, 2026. It contains the active Vonage-first FastAPI, Gradio, PostgreSQL/Supabase, RAG, reporting, scheduling, and tenant-isolation implementation.

## Included production scope

The release includes the Arabic Gradio workspace, FastAPI routes, Supabase JWT authentication, hierarchical roles, tenant-scoped RLS migrations, Vonage calling, simulated development telephony, Gemini-compatible LLM support, organization document ingestion, hybrid retrieval, escalation handling, follow-up scheduling, FCR reporting, Docker Compose deployment, tests, and operational documentation.

## Migration order

Apply the SQL files in `supabase/migrations/` in filename order. Migrations `0001` through `0007` establish the original schema and earlier policy corrections. Migrations `0008`, `0009`, and `0010` are required runtime policy corrections for authenticated audit writes, organization-member escalation reads, and organization-member follow-up-task creation.

Migrations must be applied in the Supabase SQL Editor or through the project's migration workflow. Do not run the same migration twice against the same database unless it has been made idempotent or the database is reset.

## Removed from the release

The archive excludes temporary replacement files, diagnostic scripts, generated zip archives, Python caches, pytest caches, virtual environments, local `.env` files, and obsolete provider/framework implementation artifacts. The active telephony implementation is Vonage with an explicitly supported simulated provider. Twilio, Vapi, LangGraph, LangChain, LangSmith, and Streamlit are not runtime dependencies or active application modules.

Historical architecture and cleanup documentation may mention previously evaluated technologies for presentation context; those references do not represent active code or dependencies.

## Secrets

The archive does not contain `.env`. Copy `.env.example` to `.env` in the deployment environment and fill in real Supabase, Gemini, database, authentication redirect, and Vonage values. Never commit `.env`, private keys, service-role keys, or Vonage private key files.

## Validation performed before packaging

The release source was compiled, the complete unit suite passed, the Gradio interface construction check passed, and the archive was inspected for caches, local secrets, generated artifacts, and obsolete replacement files.
