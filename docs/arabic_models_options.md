# Arabic STT and Embedding Options

## Current phone path

Live Vonage calls currently use Vonage NCCO `talk` for provider-side TTS and `input` for provider-side DTMF/speech recognition with `ar-EG`. The application stores the resulting text turns and provider events but does not send live phone audio to a local Whisper process. Vonage’s ASR documentation says ASR is chargeable and supports Arabic Egypt; it documents Google and Deepgram providers.

## STT choices

| Option | Strength | Cost/operational trade-off | Recommendation |
|---|---|---|---|
| Vonage ASR | No media-stream server is needed; integrates with the current NCCO flow. | Provider ASR is chargeable and quality depends on the selected Vonage backend. | Keep for the first Vonage acceptance test. |
| `openai/whisper-large-v3` locally | Mature multilingual baseline and fully local after download. | Large model; CPU latency and RAM are significant; GPU is preferable. | Good fallback for post-call audio transcription, not the first live phone path. |
| `AbdelrahmanHassan/whisper-large-v3-egyptian-arabic` | Apache-2.0 LoRA adapter fine-tuned for Egyptian Arabic. | Model card reports self-reported WER 0.4739 and the adapter requires the base Whisper model, PEFT, Transformers, and audio loading. It is not deployed by a Hugging Face Inference Provider. | Test against generic Whisper on a representative Egyptian sample before adopting. |
| `speechbrain/asr-whisper-large-v2-commonvoice-ar` | Apache-2.0 Arabic Whisper model with a model-card WER of 16.96 on its CommonVoice evaluation. | Large model and older training/evaluation context; requires SpeechBrain/Transformers. | Practical local Arabic baseline. |

## Embedding choices

| Option | Dimensions/endpoint | Cost/operational trade-off | Recommendation |
|---|---:|---|---|
| OpenAI `text-embedding-3-large` | 3072 in this repository | API quota required; current Supabase schema already matches it. | Preferred production path when quota is available. Re-ingest all documents after any provider change. |
| Local `Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet` | 384-dimensional Sentence Transformer | Free after download; approximately 0.1B parameters and 128-token maximum sequence length according to its model card. Requires changing the database vector dimension and re-ingesting. | Strong low-cost Arabic experiment; do not switch without a migration and full re-index. |
| Local multilingual MiniLM baseline | 384 dimensions | Small and free locally, but Arabic quality may be below an Arabic-specialized model. | Useful fallback benchmark. |
| DeepSeek API | DeepSeek’s official API documentation describes chat/completion models and an OpenAI-compatible interface; it does not document a public embeddings endpoint. | Do not plan on DeepSeek for embeddings unless the provider publishes a supported embedding endpoint. | Use DeepSeek, if desired, as an LLM provider, not as the current embedding provider. |

## Dimension migration rule

The current database uses a `3072`-dimension vector column and a halfvec HNSW index. A 384-dimensional local model cannot be inserted into that column. A provider switch therefore requires a migration or a new vector column/index, a settings change, and complete document re-ingestion. Mixing dimensions within one index is not valid.

## Sources

1. https://developer.vonage.com/en/voice/voice-api/concepts/asr
2. https://huggingface.co/AbdelrahmanHassan/whisper-large-v3-egyptian-arabic
3. https://huggingface.co/speechbrain/asr-whisper-large-v2-commonvoice-ar
4. https://huggingface.co/Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet
5. https://api-docs.deepseek.com/
