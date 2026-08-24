"""Optional local Arabic speech adapters.

The heavy ML dependencies are imported lazily so the existing Vonage-managed
flow and test suite remain usable without installing local voice models.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import wave
from pathlib import Path
from typing import Any

from outbound_ai.config.settings import get_settings

logger = logging.getLogger(__name__)
_STT_LOCK = threading.RLock()
_TTS_LOCK = threading.RLock()
_STT_MODEL: Any | None = None
_TTS_MODEL: Any | None = None
_TTS_TOKENIZER: Any | None = None


def _audio_dir() -> Path:
    settings = get_settings()
    path = settings.local_voice_audio_dir
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _require_enabled(kind: str) -> None:
    settings = get_settings()
    enabled = settings.local_stt_enabled if kind == "stt" else settings.local_tts_enabled
    if not enabled:
        raise RuntimeError(
            f"Local {kind.upper()} is disabled. Set LOCAL_{kind.upper()}_ENABLED=true to enable it."
        )


def _load_stt() -> Any:
    global _STT_MODEL
    _require_enabled("stt")
    with _STT_LOCK:
        if _STT_MODEL is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "Local STT dependencies are missing. Install with: "
                    "pip install -e '.[local-voice]'"
                ) from exc
            settings = get_settings()
            _STT_MODEL = WhisperModel(
                settings.local_stt_model,
                device=settings.local_stt_device,
                compute_type=settings.local_stt_compute_type,
            )
    return _STT_MODEL


def _transcribe_once(model: Any, path: Path, *, vad_filter: bool) -> str:
    segments, _info = model.transcribe(
        str(path),
        language="ar",
        task="transcribe",
        beam_size=5,
        vad_filter=vad_filter,
        condition_on_previous_text=False,
        temperature=0.0,
    )
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()


def transcribe_arabic(audio_path: str | Path) -> str:
    """Transcribe phone audio, retrying quiet speech without aggressive VAD."""
    model = _load_stt()
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    text = _transcribe_once(model, path, vad_filter=True)
    if text:
        return text
    # Telephony recordings can be quiet enough for VAD to discard the whole
    # response. A second pass without VAD recovers speech in that case; truly
    # empty recordings still return an empty string and remain NO_INPUT.
    return _transcribe_once(model, path, vad_filter=False)


def _load_tts() -> tuple[Any, Any]:
    global _TTS_MODEL, _TTS_TOKENIZER
    _require_enabled("tts")
    with _TTS_LOCK:
        if _TTS_MODEL is None or _TTS_TOKENIZER is None:
            try:
                import torch
                from transformers import AutoTokenizer, VitsModel
            except ImportError as exc:
                raise RuntimeError(
                    "Local TTS dependencies are missing. Install with: "
                    "pip install -e '.[local-voice]'"
                ) from exc
            settings = get_settings()
            _TTS_TOKENIZER = AutoTokenizer.from_pretrained(settings.local_tts_model)
            _TTS_MODEL = VitsModel.from_pretrained(settings.local_tts_model)
            _TTS_MODEL.eval()
            # Keep a reference so the optional torch dependency is loaded before inference.
            _TTS_MODEL._local_voice_torch = torch
    return _TTS_MODEL, _TTS_TOKENIZER


def _waveform_to_pcm(waveform: Any) -> bytes:
    """Convert a floating-point waveform to audible signed 16-bit PCM."""
    peak = float(max(abs(float(value)) for value in waveform)) or 1.0
    # Model output is normally normalized near [-1, 1].  The previous code
    # omitted the 16-bit factor, producing valid WAV files with near-zero
    # amplitude that sounded silent in a phone call.
    scale = min((0.98 * 32767.0) / peak, 32767.0)
    pcm = (waveform * scale).clip(-32768, 32767).astype("int16")
    return pcm.tobytes()


def synthesize_arabic(text: str) -> Path:
    """Generate a cached mono 16-bit WAV file with local Arabic TTS."""
    clean_text = " ".join(str(text).split()).strip()
    if not clean_text:
        raise ValueError("TTS text cannot be empty")
    model, tokenizer = _load_tts()
    torch = model._local_voice_torch
    digest = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:32]
    output_path = _audio_dir() / f"tts-{digest}.wav"
    if output_path.exists() and output_path.stat().st_size > 44:
        return output_path
    inputs = tokenizer(clean_text, return_tensors="pt")
    with torch.no_grad():
        waveform = model(**inputs).waveform[0].detach().cpu().numpy()
    pcm_bytes = _waveform_to_pcm(waveform)
    with wave.open(str(output_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(model.config.sampling_rate))
        handle.writeframes(pcm_bytes)
    return output_path


def prewarm_local_voice(texts: list[str] | None = None) -> None:
    """Load enabled local models and cache fixed response audio before calls."""
    settings = get_settings()
    if settings.local_stt_enabled:
        _load_stt()
    if settings.local_tts_enabled:
        for text in texts or []:
            synthesize_arabic(text)


def recording_file_path(call_id: str) -> Path:
    """Return a deterministic WAV path for one call recording."""
    safe_id = "".join(character for character in str(call_id) if character.isalnum() or character == "-")
    if not safe_id:
        raise ValueError("Invalid call identifier")
    return _audio_dir() / f"recording-{safe_id}.wav"


def audio_file_path(filename: str) -> Path:
    """Resolve a generated audio filename inside the configured cache only."""
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.endswith(".wav"):
        raise ValueError("Invalid local voice audio filename")
    return _audio_dir() / safe_name


def clear_local_voice_cache() -> None:
    """Clear in-process model references; disk audio cache is retained."""
    global _STT_MODEL, _TTS_MODEL, _TTS_TOKENIZER
    with _STT_LOCK, _TTS_LOCK:
        _STT_MODEL = None
        _TTS_MODEL = None
        _TTS_TOKENIZER = None


__all__ = [
    "audio_file_path",
    "recording_file_path",
    "prewarm_local_voice",
    "clear_local_voice_cache",
    "synthesize_arabic",
    "transcribe_arabic",
]
