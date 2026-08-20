"""Piper TTS provider (§42). Generic local synthetic voice.

Seam for real Piper synthesis. Requires piper-tts + a downloaded voice model.
"""

from __future__ import annotations

from pathlib import Path

from ml.common.config import MLConfig
from ml.common.results import Availability, ModelInfo, available
from ml.common.types import AudioArtifact
from ml.tts.base import SYNTHETIC_LABEL, TextToSpeechProvider


class PiperTTS(TextToSpeechProvider):  # pragma: no cover - requires piper
    def __init__(self, config: MLConfig) -> None:
        self.config = config

    def availability(self) -> Availability:
        return available(ModelInfo(name="piper", version="1.x", framework="piper", license="MIT"))

    def synthesize(self, text, out_path, voice="generic", authorized_voice_confirmation=False):
        self.guard_voice(voice, authorized_voice_confirmation)
        raise NotImplementedError(
            "Piper synthesis not wired. Install piper-tts + a voice model and "
            "implement synthesize() to write real audio to out_path."
        )
