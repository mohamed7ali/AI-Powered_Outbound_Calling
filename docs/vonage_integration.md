# Vonage Voice Integration

The platform uses Vonage as its live telephony provider through the provider port. Set `TELEPHONY_PROVIDER=vonage` and keep the existing campaign, Supabase, RLS, transcript, routing, escalation, retry, and FCR code unchanged.

## Vonage prerequisites

Create a Vonage Voice API Application with Voice capability enabled. Generate an application private key and keep the downloaded `private.key` outside source control. Copy the application ID and assign a Vonage virtual number to the application. Vonage requires the `from` number for a PSTN call to be one of the application's Vonage virtual numbers.

The public application must be reachable over HTTPS because Vonage retrieves the answer NCCO and calls the input and event webhooks. In Codespaces, make API port `8000` Public and use its HTTPS URL.

## Environment variables

```dotenv
TELEPHONY_PROVIDER=vonage
VONAGE_APPLICATION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VONAGE_PRIVATE_KEY_PATH=private.key
VONAGE_PUBLIC_KEY_PATH=public.key
VONAGE_FROM_NUMBER=447700900000
VONAGE_VERIFY_WEBHOOKS=true
PUBLIC_WEBHOOK_BASE_URL=https://YOUR-PUBLIC-8000-HOST.app.github.dev
```

`VONAGE_FROM_NUMBER` should be the Vonage virtual number assigned to the application. The customer destination continues to come from `customers.phone_e164` and should be stored in E.164 format.

`private.key` must never be committed to GitHub or uploaded in the repository archive. `public.key` is used to validate signed Vonage webhooks. For a temporary local-only test, webhook verification can be disabled with `VONAGE_VERIFY_WEBHOOKS=false`, but production deployments must keep it enabled and provide the Vonage public key.

## Provider flow

The backend creates a call through the Vonage Voice API using an application JWT. Vonage returns a call UUID, which is stored as `calls.provider_call_id`. When the call is answered, Vonage requests the mounted `/vonage` answer route and receives an NCCO containing Egyptian-Arabic `talk` and `input` actions. The input action accepts DTMF and Arabic speech and posts to the mounted Vonage input route. Vonage lifecycle events post to the mounted Vonage event route. The exact callback URLs are generated from `PUBLIC_WEBHOOK_BASE_URL` by the provider adapter.

The existing decision model is preserved:

```text
DTMF 1 / positive Arabic response -> ANSWERED_RESOLVED -> call ends
DTMF 2 / unresolved Arabic response -> ESCALATED -> call ends -> human queue
no answer / busy / failed event -> retry with backoff
```

The application persists AI prompts, customer input, normalized Arabic text, provider payloads, final outcomes, durations, and escalation records in organization-scoped tables.

## Run in Codespaces

```bash
source .venv/bin/activate
set -a
source .env
set +a
PYTHONPATH=src uvicorn outbound_ai.api.app:app --host 0.0.0.0 --port 8000
```

The Gradio frontend does not need a provider-specific change. Use **متابعة الحملات → جدولة متابعة → تشغيل المتابعة → بدء الاتصال**. The same task and customer lookup path is used for Vonage.

## Official references

- [Make an outbound call](https://developer.vonage.com/en/voice/voice-api/code-snippets/making-calls/make-an-outbound-call)
- [Voice API webhook reference](https://developer.vonage.com/en/voice/voice-api/webhook-reference)
- [NCCO reference](https://developer.vonage.com/en/voice/voice-api/ncco-reference)
- [Speech to Text](https://developer.vonage.com/en/voice/voice-api/concepts/asr)
- [DTMF input](https://developer.vonage.com/en/voice/voice-api/concepts/dtmf)
- [Authentication](https://developer.vonage.com/en/getting-started/concepts/authentication)
