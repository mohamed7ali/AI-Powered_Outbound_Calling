# Vonage Voice API Integration Findings

Research date: 2026-08-19.

The official Vonage Voice API documentation confirms that outbound calls are created with `POST https://api.nexmo.com/v1/calls` using a Bearer JWT, a `to` phone endpoint, a `from` phone endpoint, and an `answer_url`. The provider returns a call UUID that can be stored as the application provider call ID. The answer webhook returns an NCCO JSON array that controls the call.

Vonage answer webhooks support GET by default and POST when `answer_method` is set to `POST`. The answer payload includes `uuid`, `conversation_uuid`, `from`, `to`, and related fields. Vonage event webhooks are POST by default when `event_method` is configured accordingly and report events including `started`, `ringing`, `answered`, `busy`, `unanswered`, `disconnected`, `rejected`, `failed`, `timeout`, `completed`, `record`, and `input`.

NCCO supports `talk` for synthesized speech and `input` for DTMF and speech capture. The `input` action is synchronous and can send an input webhook after collecting caller input. The application can therefore preserve the current structured Egyptian-Arabic verification flow by returning NCCO `talk` plus `input` actions and mapping Vonage input callbacks into the existing Arabic routing policy.

Vonage supports signed webhooks. The replacement must validate signed callbacks or, at minimum for the first implementation, use a provider-specific verification boundary and record the raw event payload. The current public Codespaces API URL must be HTTPS and reachable by Vonage.

Vonage supports a `record` NCCO action with an `eventUrl`; the callback contains a protected recording URL. Recordings are stored by Vonage for 30 days by default and require JWT authentication to download. Transcription is documented as a chargeable feature. The first replacement should keep text turn persistence and not silently enable paid recording/transcription.

Official sources:

1. https://developer.vonage.com/en/voice/voice-api/code-snippets/making-calls/make-an-outbound-call
2. https://developer.vonage.com/en/voice/voice-api/webhook-reference
3. https://developer.vonage.com/en/voice/voice-api/ncco-reference
4. https://developer.vonage.com/en/voice/voice-api/concepts/recording

Additional verified details:

Vonage Voice API authentication uses a JWT generated from the Vonage application ID and the application's private key. The application must have Voice capability enabled. The outbound call API uses `Authorization: Bearer <JWT>`.

Vonage ASR input supports `type: ["dtmf", "speech"]` and accepts Arabic Egypt as `ar-EG`. The speech provider can be selected, but ASR is a chargeable feature. DTMF input is supported through the same `input` action. The webhook sends the collected input to the configured `eventUrl`; returning a new NCCO replaces the remaining action flow.

The initial replacement will use Vonage NCCO `talk` and `input` actions, with `input.eventUrl` pointing to an internal `/vonage/input/{call_id}` endpoint. Vonage `event_url` will point to `/vonage/event/{call_id}`. The provider call UUID will be stored in `calls.provider_call_id` and raw Vonage event payloads in `call_events.payload`.

Additional official sources:

5. https://developer.vonage.com/en/getting-started/concepts/authentication
6. https://developer.vonage.com/en/voice/voice-api/getting-started
7. https://developer.vonage.com/en/voice/voice-api/concepts/asr
8. https://developer.vonage.com/en/voice/voice-api/concepts/dtmf

## Current trial, Egypt, and ASR findings checked 2026-08-19

Vonage’s official Voice API getting-started guide says demo/trial accounts can use caller ID `123456789` to call the phone number originally supplied during signup, and that this feature is available until account credit is added. Renting a Vonage number requires adding credit. This special trial path is not the same as unrestricted Egypt-number provisioning.

Vonage’s official Voice API page says Voice API is free to try with free credit and no credit card required. Its pricing page says Voice API is usage-based and lists a starting PSTN-leg price of $0.01538 per minute, with exact pricing depending on the route. Trial credit may cover a small test, but the public pages do not guarantee that every Egypt-to-Egypt call is free; the Vonage dashboard balance and route eligibility are authoritative for the account.

Vonage’s official ASR documentation says speech recognition is chargeable, supports `ar-EG`, and supports Google and Deepgram providers. It lists Deepgram as Premier ASR at $0.024 per minute; Google is Standard ASR with exact rates on the Voice API pricing page.

Additional official sources:

9. https://developer.vonage.com/en/voice/voice-api/getting-started
10. https://www.vonage.com/communications-apis/voice/
11. https://www.vonage.com/communications-apis/pricing/
12. https://developer.vonage.com/en/voice/voice-api/concepts/asr
