# Vonage answer-call findings

Sources reviewed:

- https://developer.vonage.com/en/voice/voice-api/concepts/text-to-speech
- https://developer.vonage.com/en/voice/voice-api/ncco-reference
- https://developer.vonage.com/en/voice/voice-api/concepts/asr

Verified facts:

- Vonage TTS `talk` actions support Arabic with the standard language code `ar` (multiple styles), according to the current Text to Speech documentation. The current project uses `language: "ar-EG"` for `talk`, which is a likely invalid/unsupported TTS locale for the legacy `talk` action even though `ar-EG` is listed for legacy/ASR speech input.
- Vonage NCCO must be a JSON array. `talk` is synchronous, and when all actions are complete the call ends.
- The answer webhook must return a valid NCCO. The project answer route returns a `talk` action followed by an `input` action.
- Vonage ASR legacy speech input supports Arabic Egypt `ar-EG`; the current `input.speech.language` value is therefore appropriate for ASR input, but it should not automatically be used as the `talk.language` value.
- The project’s latest live logs showed `/vonage/answer/<call_id>` returning HTTP 200, but the caller heard no speech and the call ended. The likely application defect is the invalid `talk` locale `ar-EG`; change only `talk` actions to `language: "ar"` while retaining `input.speech.language: "ar-EG"`.
