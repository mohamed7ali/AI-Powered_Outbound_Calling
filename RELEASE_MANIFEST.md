# Arabic AI Outbound Calls — Final Release Manifest

This archive is the consolidated project state through August 24, 2026. It contains the verified Vonage-first FastAPI, Gradio, PostgreSQL/Supabase, RAG, reporting, scheduling, tenant-isolation, local voice, routing, and documentation implementation.

## Included production scope

The release includes the Arabic RTL Gradio workspace, FastAPI routes, Supabase JWT authentication, hierarchical roles, tenant-scoped RLS migrations, Vonage calling, simulated development telephony, native Vonage Arabic speech, optional local faster-whisper recording transcription, Arabic decision routing, organization document ingestion, hybrid retrieval, Gemini-compatible LLM support, escalation handling, follow-up scheduling, FCR reporting, Docker Compose deployment, regression tests, and operational documentation.

Resolved calls synchronize both the call outcome and the linked support-case status. The operational cases list excludes resolved and closed cases, while calls, turns, events, and historical records remain available for reporting and audit purposes.

## Database migrations

Apply every SQL file under `supabase/migrations/` in filename order. The migrations establish the original schema, call duration, hybrid knowledge search, helper permissions, authorized call creation, escalation resolution, FCR writes, audit writes, member reads, follow-up creation, Arabic Sentence Transformer vector dimensions, and calibrated hybrid retrieval thresholds.

Apply migrations in the Supabase SQL Editor or through the project’s migration workflow. Do not run the same migration twice against an existing database unless it is idempotent or the database has been reset.

The `supabase/seed.sql` file is development seed data and is not required for production records. The non-migration example `docs/customer_and_case_examples.sql` shows how to add customers and callable support cases to an existing organization without placing a call; it is safe to adapt after reviewing its values.

## Active telephony behavior

Direct and scheduled calls use the same Vonage outbound adapter and public answer/event callbacks. The greeting and all live response messages use native Vonage Arabic `talk`. When `LOCAL_STT_ENABLED=true`, the answer flow records the customer after a beep, downloads the WAV recording, transcribes it with local `faster-whisper`, applies Arabic-normalized routing, persists the customer turn, and records the resolved or escalated outcome.

The scheduler is a separate process and must be restarted after changing `.env`, Vonage credentials, the application ID, the private key, or the public webhook hostname. The API and scheduler must load the same environment.

## Included validation

The current reference tree was syntax-checked and the complete regression suite passed **76 tests**. The tests cover routing, Arabic normalization, local voice behavior, Vonage payloads and callbacks, webhook security, scheduler contracts, RAG behavior, database contracts, escalation handling, role boundaries, and UI construction.

Included diagnostic scripts cover Arabic decision matrices, live routing-module verification, local voice smoke testing, scheduler execution, escalation routes, role transitions, Gradio configuration, UI validation, and reproduction of known agent issues.

## Removed from the release

The archive excludes temporary replacement files, generated ZIP archives, ZIP checksums, diagnostic output dumps, Python caches, pytest caches, virtual environments, local `.env` files, local audio caches, runtime logs, and obsolete provider/framework implementation artifacts. Twilio, Vapi, LangGraph, LangChain, LangSmith, and Streamlit are not runtime dependencies or active application modules.

Historical architecture and cleanup documents may mention previously evaluated technologies for presentation context; those references do not represent active runtime code.

## Secrets

The archive does not contain `.env`, Vonage private keys, public keys, Supabase service-role keys, Gemini keys, or other credentials. Copy `.env.example` to `.env` in the deployment environment and fill in the required values. The environment template includes the separate Vonage application credentials and account signature secret; the signature secret is not interchangeable with the application private key.

Never commit `.env`, `private.key`, `public.key`, service-role keys, provider tokens, generated recordings, or customer exports.

## Release replacement policy

This ZIP is a clean release snapshot, not a patch applied to the user’s live checkout. Before replacing a live repository, preserve its `.env` and any private key files separately, extract the archive into a temporary directory, compare the source and configuration templates, and run the test suite. Do not copy secrets from the archive because none are included.
