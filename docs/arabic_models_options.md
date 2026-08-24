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
| Local `Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet` | 384-dimensional Sentence Transformer | Free after download; approximately 0.1B parameters and 128-token maximum sequence length according to its model card. The model is downloaded on first use. | **Active default provider.** Apply migration 0011 and re-index all documents before querying. |
| OpenAI `text-embedding-3-large` | Configured dimension must be 384 for the current schema | API quota required; the current database contract is now 384 dimensions. | Optional API alternative. Set `RAG_EMBEDDING_PROVIDER=openai`, set `OPENAI_EMBEDDING_DIM=384`, and re-ingest if changing models. |
| Local multilingual MiniLM baseline | 384 dimensions | Small and free locally, but Arabic quality may be below an Arabic-specialized model. | Useful fallback benchmark. |
| DeepSeek API | DeepSeek’s official API documentation describes chat/completion models and an OpenAI-compatible interface; it does not document a public embeddings endpoint. | Do not plan on DeepSeek for embeddings unless the provider publishes a supported embedding endpoint. | Use DeepSeek, if desired, as an LLM provider, not as the current embedding provider. |

## Dimension migration rule

The current database uses a `384`-dimension vector column and a halfvec HNSW index after migration 0011. The migration clears old embeddings because vectors from different models or dimensions must not be mixed. Any future provider or dimension switch requires a migration, settings change, and complete document re-ingestion.

## Sources

1. https://developer.vonage.com/en/voice/voice-api/concepts/asr
2. https://huggingface.co/AbdelrahmanHassan/whisper-large-v3-egyptian-arabic
3. https://huggingface.co/speechbrain/asr-whisper-large-v2-commonvoice-ar
4. https://huggingface.co/Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet
5. https://api-docs.deepseek.com/
