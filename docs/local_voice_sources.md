# Local Arabic voice sources

The implementation is based on these public sources:

- https://github.com/SYSTRAN/faster-whisper
- https://huggingface.co/facebook/mms-tts-ara
- https://developer.vonage.com/en/voice/voice-api/ncco-reference
- https://developer.vonage.com/en/voice/voice-api/concepts/asr

Verified details:

- faster-whisper is an MIT-licensed CTranslate2 reimplementation of Whisper. Its documentation describes lower memory use and up to 4x speed improvement over the original openai-whisper implementation; CPU INT8 inference is supported. Arabic is handled through Whisper's multilingual language selection.
- facebook/mms-tts-ara is an Arabic VITS TTS checkpoint usable locally through Transformers. Its model card reports about 36.3M parameters and a CC-BY-NC 4.0 license, so it is appropriate for a non-commercial/demo project but requires license review for commercial use.
- Vonage NCCO is a JSON array of call-control actions. `talk` and `stream` are synchronous unless barge-in is enabled, and `input` captures DTMF or speech. A call ends when the NCCO actions complete.
- Vonage's `input` speech action is provider-managed ASR. Using local Whisper instead requires a recording or media-streaming path, downloading/receiving audio, transcribing locally, and returning new call-control instructions or audio.
- The current implementation's local_voice.py adds lazy-loaded optional adapters and does not yet alter the live Vonage flow. Local TTS audio would need a public HTTPS URL plus a Vonage `stream` NCCO action. Local STT would need recording/media callbacks or a WebSocket media path.

Additional verified Vonage sources:

- https://developer.vonage.com/en/voice/voice-api/webhook-reference
- https://developer.vonage.com/en/voice/voice-api/concepts/recording
- https://developer.vonage.com/en/api/voice

Verified details:

- The Voice webhook reference states that the answer webhook must return an NCCO and that outgoing calls can override answer/event URLs and methods at call creation.
- The recording guide states that a synchronous `record` action ends on `endOnSilence`, `endOnKey`, or `timeout`, then sends a recording webhook containing a downloadable recording URL. Recording downloads require a JWT signed by the same application key that created the recording.
- The Voice API reference provides `PUT /v1/calls/{uuid}` to modify an in-progress call. The body uses `action: transfer` and a `destination` of type `ncco`, allowing the application to replace the active call's NCCO after local processing.
- The Voice API reference defines `stream` as a way to play an audio file into a call, which is the integration point for locally synthesized WAV audio exposed through a public HTTPS URL.
