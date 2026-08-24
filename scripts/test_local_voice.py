"""Offline smoke test for the optional local Arabic voice models."""

from __future__ import annotations

import argparse

from outbound_ai.telephony.local_voice import synthesize_arabic, transcribe_arabic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", help="Existing WAV/MP3 file to transcribe")
    parser.add_argument(
        "--text",
        default="مرحباً، هذه تجربة للصوت العربي المحلي.",
        help="Arabic text to synthesize",
    )
    args = parser.parse_args()

    audio_path = synthesize_arabic(args.text)
    print(f"tts_audio={audio_path}")
    if args.audio:
        print(f"stt_text={transcribe_arabic(args.audio)}")


if __name__ == "__main__":
    main()
