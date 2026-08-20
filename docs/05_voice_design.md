# Voice Layer Design: Vonage Arabic Calls

This document describes the production-wired voice path for UC1. The live provider is **Vonage Voice API**; the repository also contains a simulated adapter for development. Standalone browser Whisper and ElevenLabs adapters are intentionally not part of this cleaned runtime because Vonage owns the phone-call audio pipeline.

## 1. Live call pipeline

```text
Scheduler or Gradio
      |
      v
Vonage outbound call API
      |
      v
Vonage NCCO talk action (Arabic prompt)
      |
      v
Vonage NCCO input action (DTMF + speech)
      |
      v
FastAPI /vonage callbacks
      |
      +--> call_events: raw provider event
      +--> call_turns: final AI/customer text turns
      +--> Arabic routing: resolved/escalated/ambiguous
      +--> calls: status, outcome, duration
      +--> escalations or follow-up retry
```

The automated call ends after the structured verification decision. There is no live transfer. An unresolved or ambiguous result becomes a human-agent escalation after the call.

## 2. TTS and STT responsibility

Vonage’s `talk` action performs provider-side TTS. The application supplies Egyptian-Arabic prompt text and an Arabic language configuration. Vonage’s `input` action performs provider-side DTMF and speech recognition. The input callback extracts the recognized speech or digits and sends them to the existing Arabic normalization and routing policy.

The application does not stream raw phone audio to Whisper or ElevenLabs. This keeps the phone path smaller and avoids an additional real-time media-stream service. Provider TTS/STT availability, language quality, pricing, and regional support remain Vonage account prerequisites.

## 3. Text persistence

The application persists the following information:

| Content | Database field |
|---|---|
| Internal/provider call identity | `public.calls.id`, `provider`, `provider_call_id` |
| Customer speech or DTMF interpretation | `public.call_turns.text_raw`, `text_norm` |
| AI prompt and branch response | `public.call_turns` with `speaker='AI'` |
| Raw provider callback | `public.call_events.payload` |
| Final decision | `public.calls.outcome` |
| Call duration and lifecycle | `public.calls.status`, `duration_seconds`, timestamps |
| Unresolved work | `public.escalations` |

Final transcript rows are written idempotently with provider-event handling so repeated callbacks do not create duplicate business effects.

## 4. Audio recording boundary

Audio recording is not enabled by default. The current Vonage NCCO does not request a recording, and the application does not download provider audio into Supabase Storage. The `call_turns` table can retain audio metadata if a future recording feature is added, but the current production contract is text transcript plus raw event audit.

Adding recording later requires explicit consent language, retention/deletion policy, private Storage upload, recording callback handling, and a provider-cost review. It should not be enabled silently for customer calls.

## 5. Development and acceptance tests

Use the simulator for a zero-carrier-cost test:

```dotenv
TELEPHONY_PROVIDER=simulated
```

For live Vonage testing:

```dotenv
TELEPHONY_PROVIDER=vonage
VONAGE_APPLICATION_ID=...
VONAGE_PRIVATE_KEY_PATH=private.key
VONAGE_PUBLIC_KEY_PATH=public.key
VONAGE_FROM_NUMBER=...
PUBLIC_WEBHOOK_BASE_URL=https://your-public-api.example.com
```

The acceptance test should use one authorized internal destination number and verify that a resolved response creates `ANSWERED_RESOLVED`, an unresolved response creates `ESCALATED`, a no-answer event schedules a retry, and duplicate callbacks do not duplicate `call_events`, turns, or escalations.
