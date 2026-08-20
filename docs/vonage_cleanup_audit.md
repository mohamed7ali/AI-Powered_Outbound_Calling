# Vonage-First Cleanup Audit

## Scope

The repository was cleaned for a single live telephony provider: Vonage Voice API. The simulated adapter remains available for zero-carrier-cost development and presentation testing. The cleanup was intentionally conservative: required database, tenant, RAG, reporting, scheduler, escalation, authentication, UI, and Docker paths were retained.

## Removed from the active runtime

| Removed item | Reason |
|---|---|
| Twilio adapter, TwiML module, Twilio router, and Twilio tests | Twilio is no longer a supported provider in this deployment. |
| Vapi adapter, Vapi router, Vapi tests, and Vapi setup documents | Vapi was evaluated but is not the selected provider. |
| Standalone Whisper/ElevenLabs browser voice package and tests | These modules were not wired into the phone-call path; Vonage owns the live phone TTS/STT pipeline. |
| LangGraph/LangChain/LangSmith dependencies | No active source module imported or used them in the current implementation. |
| Twilio/Vapi/standalone voice dependency packages | No longer required after provider cleanup. |
| Unused RAG and data packages (`rank-bm25`, `tiktoken`, `pandas`) | The active RAG path uses PostgreSQL full-text search, pgvector, and the configured embedding/LLM client. |
| Unused audio runtime packages (`soundfile`, `webrtcvad-wheels`, `numpy`, `scipy`, `tenacity`, `elevenlabs`) | No standalone audio layer remains in the cleaned runtime. |

## Preserved and validated

| Preserved capability | Validation |
|---|---|
| Vonage live adapter | Existing Vonage unit tests pass, including JWT call creation, phone normalization, and callback input parsing. |
| Simulated telephony | Provider factory still supports `TELEPHONY_PROVIDER=simulated`. |
| Arabic prompts | Shared prompts moved from the deleted TwiML module to `telephony/prompts.py`; Vonage imports them directly. |
| Vonage callbacks | `/vonage/answer/{call_id}`, `/vonage/input/{call_id}`, and `/vonage/event/{call_id}` remain registered. |
| Database call flow | Calls, turns, provider events, outcomes, durations, escalations, and follow-up settlement remain unchanged. |
| Tenant isolation | Existing RLS and organization predicates remain in place. |
| Human-agent workflow | Escalation queue, RAG assistant, documents, reports, and Gradio tabs remain in the application. |
| Docker | Dockerfile and Compose still build from the cleaned `pyproject.toml`; the unused audio system package was removed. |

## Logical checks

The cleanup was checked beyond unit tests:

- The FastAPI application imports successfully.
- Only the Vonage callback router is active among live provider routes.
- Deleted `/twilio` and `/vapi` paths are absent from active application routing.
- The simulator factory works without live credentials.
- Vonage fails fast when live credentials are missing rather than making an unsafe partial call.
- The package builds into a Python wheel.
- The active test suite passes after cleanup.

## Remaining external prerequisites

A real call still requires a Vonage Voice Application, an application private/public key pair, a supported Vonage virtual number, a valid destination number, a public HTTPS callback URL, and any required Vonage account permissions or credits. Provider-side Arabic TTS/STT quality, number availability, and pricing remain external acceptance concerns. Audio recording is not enabled by default; the application stores text turns and raw provider events.
