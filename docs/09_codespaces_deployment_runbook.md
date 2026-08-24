# Codespaces and Deployment Runbook

This runbook explains how to move the production archive into GitHub, open it in Codespaces, run the application safely with simulated telephony, connect Supabase, and later deploy the Dockerized services. Codespaces is suitable for development and testing; it should not be treated as the production host because the development environment may stop or sleep when unused.

## 1. Create the GitHub repository

Create an empty GitHub repository, preferably private while credentials and customer-related code are being configured. Do not commit `.env`, Supabase service-role keys, Vonage private keys, Gemini/OpenAI keys, or customer phone numbers.

The most reliable import method is to extract the archive on your computer and push the repository contents rather than pushing the ZIP as a single file. From a terminal in the extracted project directory, run:

```bash
git init
git branch -M main
git add .
git commit -m "Add Arabic AI outbound follow-up platform"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

If you upload the ZIP through the GitHub web interface, the repository will initially contain only the archive. Open a Codespace, install `unzip`, extract the archive, move the extracted project files to the repository root, and commit the result. It is cleaner to extract locally before the first push.

## 2. Open the repository in Codespaces

Open the repository on GitHub, select **Code → Codespaces → Create codespace on main**, and wait for the VS Code browser environment to start. In the Codespaces terminal, verify the runtime:

```bash
python3 --version
node --version
pwd
ls
```

The project supports Python 3.11 and 3.12. Install the package and development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the first verification before configuring cloud services:

```bash
PYTHONPATH=src python -m pytest -q
python -m compileall -q src tests scripts
```

The expected result is a passing local suite. These tests do not require a Supabase database or a real phone call.

## 3. Configure the development environment

Create the local environment file. It is ignored by the archive and must never be committed:

```bash
cp .env.example .env
```

For the first application test, use simulated telephony and the local Arabic Sentence Transformer:

```dotenv
APP_ENV=dev
LOG_LEVEL=INFO
TELEPHONY_PROVIDER=simulated
RAG_EMBEDDING_PROVIDER=sentence_transformers
RAG_EMBEDDING_DIM=384
SENTENCE_TRANSFORMER_MODEL=Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet
SENTENCE_TRANSFORMER_DEVICE=cpu
RAG_MIN_CITATION_SCORE=0.30
RAG_CITATION_RELATIVE_THRESHOLD=0.55
RAG_MAX_CITATIONS=3
API_HOST=0.0.0.0
API_PORT=8000
GRADIO_PORT=7860
API_BASE_URL=http://localhost:8000
```

The unit tests can run without the remaining values. The API, campaign, reporting, documents, and agent UI require a configured Supabase project because their data is stored in PostgreSQL and Supabase Storage.

## 4. Run the application directly in Codespaces

Use three terminals in the Codespace. Activate the virtual environment in each terminal.

Terminal 1, API:

```bash
source .venv/bin/activate
PYTHONPATH=src uvicorn outbound_ai.api.app:app --host 0.0.0.0 --port 8000
```

Terminal 2, Gradio UI:

```bash
source .venv/bin/activate
PYTHONPATH=src python -m outbound_ai.ui.app
```

Terminal 3, scheduler:

```bash
source .venv/bin/activate
PYTHONPATH=src python scripts/run_scheduler.py
```

For the first check, open the forwarded port for `7860` from the Ports panel. The API health check is available at port `8000`:

```bash
curl http://localhost:8000/health
```

The expected response is:

```json
{"status":"ok"}
```

If the Codespaces Ports panel does not show the service automatically, forward ports `8000` and `7860` manually. Keep the forwarded ports private while authentication and deployment are being configured.

## 5. Configure Supabase

Create a Supabase project and copy its project URL, anonymous key, service-role key, and PostgreSQL connection string into `.env`. Apply the SQL migrations in `supabase/migrations/` in filename order using the Supabase SQL Editor or the Supabase CLI. The migrations create the organization hierarchy, customer and case tables, follow-up tasks, calls, RLS policies, private document Storage policies, pgvector chunks, hybrid search, conversations, audit events, and FCR reports.

At minimum, configure:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
DATABASE_URL=YOUR_POSTGRES_CONNECTION_STRING
SUPABASE_JWT_AUDIENCE=authenticated
DOCUMENT_STORAGE_BUCKET=organization-documents
```

Prefer Supabase JWKS verification by leaving `SUPABASE_JWT_SECRET` blank. Only set `SUPABASE_JWT_SECRET` when using a legacy HS256 Supabase project. The service-role key must remain on the server and must not be placed in Gradio JavaScript, GitHub, or Codespaces output.

Create a user through Supabase Auth, then insert that user into `platform_admins` using a controlled SQL operation. Do not expose a public endpoint that bootstraps platform-admin access. Once a platform administrator exists, use the administration API or Gradio administration tab to create organizations and invite organization administrators or agents.

## 6. Test in stages

### Stage A: Static and unit verification

Run the following after every substantial change:

```bash
source .venv/bin/activate
python -m compileall -q src tests scripts
PYTHONPATH=src python -m pytest -q
```

### Stage B: API startup

Start the API and run:

```bash
curl http://localhost:8000/health
PYTHONPATH=src python -c "from outbound_ai.api.app import app; print(len(app.routes))"
```

The application should import successfully and expose the health, Vonage, agent, campaign, document, report, and administration routes.

### Stage C: Authentication and tenant isolation

Create two organizations and at least one agent in each. Log in with an agent from organization A and send an authenticated request with organization B’s UUID. The request must return `403` rather than data from organization B. Repeat this test for documents, cases, reports, and agent queries. Test that a platform administrator can explicitly select an active organization, while an organization administrator cannot select an organization where they have no membership.

### Stage D: RAG and document ingestion

Configure the local Sentence Transformer for the standard test, or an approved OpenAI-compatible provider if `OPENAI_EMBEDDING_DIM` is set to the same `RAG_EMBEDDING_DIM`. After applying migration `202608230011_switch_to_arabic_sentence_transformer_384.sql`, re-upload or re-index every knowledge document because the migration clears old embeddings. Log in through Gradio, select the organization UUID, upload a small Arabic PDF/DOCX/TXT document, and confirm that the document appears in the organization’s document list. Ask an Arabic question that is answered by the uploaded document and confirm that the response includes citations. Upload a document to organization A, then verify that an agent from organization B cannot retrieve it.

### Stage E: Simulated outbound follow-up

Create a customer and support case in the active organization, create a follow-up task, and start it using the campaign tab or API. With `TELEPHONY_PROVIDER=simulated`, no real phone call is placed. Verify that a call row is created and a provider call identifier is attached. Exercise the routing policy with resolved, unresolved, ambiguous, and no-answer inputs. The unresolved path must create an escalation or human task and end the automated call.

### Stage F: FCR report

Generate an FCR report for a date range containing the simulated call. Confirm that the report is organization-scoped and contains total calls, resolved follow-ups, escalations, answer rate, FCR rate, duration, and Arabic report text.

## 7. Optional live Vonage test

Do not enable Vonage until the simulated workflow and tenant-isolation tests pass. Configure a Vonage Voice Application with Voice capability, a private/public key pair, a supported virtual number, and public HTTPS callback URLs. Configure:

```dotenv
TELEPHONY_PROVIDER=vonage
VONAGE_APPLICATION_ID=YOUR_VONAGE_APPLICATION_ID
VONAGE_PRIVATE_KEY_PATH=private.key
VONAGE_PUBLIC_KEY_PATH=public.key
VONAGE_FROM_NUMBER=YOUR_VONAGE_VIRTUAL_NUMBER
VONAGE_VERIFY_WEBHOOKS=true
PUBLIC_WEBHOOK_BASE_URL=https://YOUR_PUBLIC_HTTPS_DOMAIN
```

Configure the Vonage answer, input, and event callbacks to reach the API under `/vonage`. Confirm that the provider can reach the public HTTPS URL, that Arabic input is captured, that duplicate callbacks do not create duplicate call events, and that terminal events persist duration and the correct outcome.

A Codespace forwarding URL can be useful for a short development experiment, but it is not a stable production webhook endpoint. Use a stable HTTPS deployment for real calls.

## 8. Docker and Docker Compose

Docker is included in the repository. The relevant files are `Dockerfile`, `docker-compose.yml`, and `.dockerignore`. Compose defines three services: `api`, `ui`, and `scheduler`. The API is published on port `8000`, and Gradio is published on port `7860`.

Check Docker availability:

```bash
docker --version
docker compose version
```

If Docker is available in the Codespace, copy `.env.example` to `.env`, fill in the required values, and run:

```bash
docker compose up --build
```

Run in the background with:

```bash
docker compose up --build -d
docker compose logs -f api ui scheduler
```

Stop the services with:

```bash
docker compose down
```

Codespaces may not provide a usable Docker daemon in every configuration. If `docker compose up` fails because there is no daemon, use the direct Python commands for development or deploy the same Compose files to a Linux VM with Docker Engine and the Compose plugin.

## 9. Production deployment recommendation

Use Codespaces for development only. For production, use a persistent Linux VM or managed container host with Docker, a stable domain, TLS, a firewall, secret management, backups, and a process restart policy. Place a reverse proxy such as Nginx or Caddy in front of the API and Gradio services, expose only HTTPS, restrict the Gradio console, and do not expose PostgreSQL directly to the public internet.

A production deployment sequence is:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
cp .env.example .env
# edit .env with production secrets
chmod 600 .env
docker compose up --build -d
docker compose ps
curl https://YOUR_DOMAIN/health
```

Before real customer calls, configure backups and monitoring, rotate credentials, apply the Supabase migrations, bootstrap the platform administrator, test organization isolation, test document privacy, test authenticated Vonage callbacks, and perform a controlled Arabic call. Keep the telephony provider set to `simulated` until those checks are complete.

## 10. Common problems

| Problem | Likely cause | Action |
|---|---|---|
| `ModuleNotFoundError` | Dependencies were not installed in the active virtual environment | Activate `.venv` and run `python -m pip install -e ".[dev]"` |
| `DATABASE_URL` error | Supabase/PostgreSQL connection is missing or malformed | Copy the correct connection string and confirm network access |
| `Bearer token required` | The UI is not logged in or the access token expired | Log in through Supabase Auth again |
| `Not a member of this organization` | The JWT user has no active membership for the selected UUID | Add the membership through the platform/admin workflow |
| `Supabase Storage configuration is missing` | Service-role key or Supabase URL is absent | Configure server-side Storage credentials; never put them in the browser |
| Gradio cannot reach the API | API is stopped or `API_BASE_URL` is wrong | Start the API and check port forwarding or the Compose service URL |
| Docker daemon unavailable | Codespace does not provide Docker-in-Docker | Use direct Python locally or deploy Compose to a Docker VM |
| Vonage callback failure | Public URL, key pair, application ID, or callback verification is incorrect | Verify `PUBLIC_WEBHOOK_BASE_URL`, HTTPS, Vonage Application settings, and public key |

## References

[1]: https://docs.github.com/en/codespaces "GitHub Codespaces documentation"
[2]: https://supabase.com/docs/guides/database/overview "Supabase database documentation"
[3]: https://supabase.com/docs/guides/auth/jwts "Supabase JWT documentation"
[4]: https://docs.docker.com/compose/ "Docker Compose documentation"
[5]: https://developer.vonage.com/en/voice/voice-api/webhook-reference "Vonage Voice API webhook reference"
