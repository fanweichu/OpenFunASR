#!/usr/bin/env python3
"""Use locally supplied, non-repository speech audio for a real engine test."""
from __future__ import annotations

import os
import shutil
import tempfile
import wave
from pathlib import Path

from openfunasr_app import (
    AppDelegate, DEFAULT_AUDIO_FILE, FUNASR_DECODER_MODEL_NAME,
    FUNASR_ENCODER_MODEL_NAME, FUNASR_VAD_MODEL_NAME, merge_config,
    resolve_funasr_binary, resolve_funasr_model, resolve_vad_binary, resolve_vad_model,
)


def main() -> None:
    audio = os.environ.get("OPENFUNASR_TEST_AUDIO")
    if not audio or not Path(audio).is_file():
        raise SystemExit("Set OPENFUNASR_TEST_AUDIO to a local 16 kHz mono PCM WAV containing speech; no recordings are distributed.")
    delegate = AppDelegate.alloc().init()
    delegate.config = merge_config(None)
    delegate.vad_bin = resolve_vad_binary()
    delegate.vad_model_path = resolve_vad_model()
    delegate.funasr_bin = resolve_funasr_binary()
    delegate.funasr_encoder_path = resolve_funasr_model(FUNASR_ENCODER_MODEL_NAME)
    delegate.funasr_model_path = resolve_funasr_model(FUNASR_DECODER_MODEL_NAME)
    delegate.funasr_vad_path = resolve_funasr_model(FUNASR_VAD_MODEL_NAME)
    delegate.recognition_process = None
    try:
        with tempfile.TemporaryDirectory() as directory:
            silence = Path(directory) / "silence.wav"
            with wave.open(str(silence), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\x00\x00" * 16000)
            shutil.copyfile(silence, DEFAULT_AUDIO_FILE)
            assert delegate.runTranscription() == ""
        shutil.copyfile(audio, DEFAULT_AUDIO_FILE)
        transcript = delegate.runTranscription()
        assert transcript.strip(), "Speech test produced no transcription"
        print(f"Real VAD + Fun-ASR inference passed ({len(transcript)} characters); silence gate passed.")
    finally:
        DEFAULT_AUDIO_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
