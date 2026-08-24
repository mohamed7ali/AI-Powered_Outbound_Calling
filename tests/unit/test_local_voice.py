from pathlib import Path

import numpy as np
import pytest

from outbound_ai.config.settings import get_settings
from outbound_ai.api.routers import vonage as vonage_router
from outbound_ai.telephony import local_voice
from outbound_ai.telephony.routing import FollowUpAction, decide_follow_up


def test_transcribe_retries_without_vad_when_first_pass_is_empty(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(b"wav")
    calls: list[bool] = []
    monkeypatch.setattr(local_voice, "_load_stt", lambda: object())

    def fake_transcribe_once(_model, _path, *, vad_filter: bool) -> str:
        calls.append(vad_filter)
        return "" if vad_filter else "نعم تم حل المشكلة"

    monkeypatch.setattr(local_voice, "_transcribe_once", fake_transcribe_once)
    assert local_voice.transcribe_arabic(audio_path) == "نعم تم حل المشكلة"
    assert calls == [True, False]


def test_transcribe_does_not_retry_when_vad_returns_text(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(b"wav")
    calls: list[bool] = []
    monkeypatch.setattr(local_voice, "_load_stt", lambda: object())

    def fake_transcribe_once(_model, _path, *, vad_filter: bool) -> str:
        calls.append(vad_filter)
        return "نعم تم حل المشكلة"

    monkeypatch.setattr(local_voice, "_transcribe_once", fake_transcribe_once)
    assert local_voice.transcribe_arabic(audio_path) == "نعم تم حل المشكلة"
    assert calls == [True]


def test_local_stt_is_disabled_by_default(monkeypatch, tmp_path: Path) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "local_stt_enabled", False)
    with pytest.raises(RuntimeError, match="Local STT is disabled"):
        local_voice.transcribe_arabic(tmp_path / "missing.wav")


def test_waveform_to_pcm_has_16_bit_amplitude() -> None:
    pcm = np.frombuffer(
        local_voice._waveform_to_pcm(np.array([0.0, 0.5, -0.25], dtype=np.float32)),
        dtype=np.int16,
    )
    assert pcm.tolist() == [0, 16383, -8191]


@pytest.mark.parametrize(
    "speech",
    [
        "نعم، المشكلة حُلّت",
        "تم حل المشكلة، المشكلة اتحلت، اه",
        "نعم تم حل المشكلة",
        "المشكلة اتحلت",
        "أجل، تم حلها",
        "بلى، انتهت المشكلة",
        "تم إصلاحها",
    ],
)
def test_common_arabic_resolved_answers_are_classified_as_resolved(speech: str) -> None:
    decision = decide_follow_up(speech=speech)
    assert decision.action == FollowUpAction.RESOLVED


@pytest.mark.parametrize(
    "speech",
    [
        "اوه تم حالة المشكلة. مشكلة حالت.",
        "لفكرة حلطة وطمحة المشكلة",
        "تم حالة المشكلة. مشكلة حالة طبعا",
        "المشكلة حالة أو تم حالة المشكلة",
    ],
)
def test_observed_whisper_resolution_errors_are_classified_as_resolved(speech: str) -> None:
    decision = decide_follow_up(speech=speech)
    assert decision.action == FollowUpAction.RESOLVED


def test_bare_problem_status_remains_unclear() -> None:
    decision = decide_follow_up(speech="حالة المشكلة")
    assert decision.action == FollowUpAction.HUMAN_TASK
    assert "إجابة العميل غير واضحة" in decision.reason


@pytest.mark.parametrize(
    "speech",
    [
        "لا، المشكلة لم تُحل",
        "المشكلة ما زالت موجودة",
        "لا تزال المشكلة قائمة",
        "لم تنته المشكلة",
        "المشكلة لم يتم حلها",
    ],
)
def test_common_arabic_unresolved_answers_are_classified_as_human_task(speech: str) -> None:
    decision = decide_follow_up(speech=speech)
    assert decision.action == FollowUpAction.HUMAN_TASK


def test_no_speech_has_specific_escalation_reason() -> None:
    decision = decide_follow_up(digits="", speech="")
    assert decision.action == FollowUpAction.HUMAN_TASK
    assert "لم نتلقَّ رداً صوتياً" in decision.reason


def test_unrecognized_speech_remains_distinct_from_no_speech() -> None:
    decision = decide_follow_up(digits="", speech="كلام غير مفهوم")
    assert decision.action == FollowUpAction.HUMAN_TASK
    assert "إجابة العميل غير واضحة" in decision.reason


def test_local_tts_is_disabled_by_default(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "local_tts_enabled", False)
    with pytest.raises(RuntimeError, match="Local TTS is disabled"):
        local_voice.synthesize_arabic("مرحباً")


def test_empty_tts_text_is_rejected_before_model_loading(monkeypatch) -> None:
    monkeypatch.setattr(local_voice, "_load_tts", lambda: pytest.fail("model should not load"))
    with pytest.raises(ValueError, match="cannot be empty"):
        local_voice.synthesize_arabic("   ")


def test_audio_cache_path_is_project_relative() -> None:
    settings = get_settings()
    assert settings.audio_cache_path.is_absolute()
    assert settings.audio_cache_path.name == "voice-audio"


def test_answer_ncco_keeps_existing_vonage_flow_by_default(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "local_stt_enabled", False)
    result = vonage_router._answer_ncco("00000000-0000-0000-0000-000000000001")
    assert result[0]["action"] == "talk"
    assert result[1]["action"] == "input"
    assert result[1]["type"] == ["speech"]


def test_answer_ncco_uses_recording_for_local_stt(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "local_stt_enabled", True)
    result = vonage_router._answer_ncco("00000000-0000-0000-0000-000000000001")
    assert [item["action"] for item in result] == ["talk", "record", "wait"]
    assert result[0] == {
        "action": "talk",
        "text": vonage_router.GREETING_TEXT,
        "language": "ar",
    }
    assert result[1]["format"] == "wav"
    assert result[1]["endOnSilence"] == 5
    assert result[1]["timeOut"] == 30
    assert result[1]["beepStart"] is True
    assert result[1]["eventMethod"] == "POST"
    assert result[2]["duration"] == 180


def test_input_retry_uses_native_arabic_voice(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "local_tts_enabled", True)
    monkeypatch.setattr(
        vonage_router,
        "synthesize_arabic",
        lambda _text: pytest.fail("live retry must not use local MMS TTS"),
    )

    result = vonage_router._input_ncco(
        "00000000-0000-0000-0000-000000000001"
    )

    assert result[0] == {
        "action": "talk",
        "text": vonage_router.UNRESOLVED_TEXT,
        "language": "ar",
    }
    assert result[1]["action"] == "input"


def test_local_tts_returns_stream_action(monkeypatch, tmp_path: Path) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "local_tts_enabled", True)
    monkeypatch.setattr(settings, "local_voice_public_base_url", "https://voice.example.test")
    monkeypatch.setattr(
        vonage_router,
        "synthesize_arabic",
        lambda _text: tmp_path / "tts-test.wav",
    )
    result = vonage_router._talk_action("مرحباً")
    assert result == {
        "action": "stream",
        "streamUrl": ["https://voice.example.test/vonage/audio/tts-test.wav"],
    }
