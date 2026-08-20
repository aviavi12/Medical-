"""Mock TTS provider — TESTS ONLY.

Writes a real (silent) WAV placeholder so the artifact/export plumbing can be
tested without a TTS engine. Clearly labelled; never presented as real speech.
Guarded by ALLOW_MOCK_INFERENCE via the factory.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

from ml.common.results import Availability, ModelInfo, available
from ml.common.types import AudioArtifact
from ml.tts.base import TextToSpeechProvider


class MockTTS(TextToSpeechProvider):
    name = "tts"

    def availability(self) -> Availability:
        return available(ModelInfo(name="mock-tts", version="test", framework="mock",
                                   configuration={"mock": True}))

    def synthesize(self, text, out_path, voice="generic", authorized_voice_confirmation=False):
        self.guard_voice(voice, authorized_voice_confirmation)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rate = 22050
        # ~60 ms per character, clamped, of silence.
        duration = max(0.5, min(30.0, 0.06 * len(text or "")))
        n_frames = int(sample_rate * duration)
        with wave.open(str(out_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            silence = struct.pack("<h", 0)
            wf.writeframes(silence * n_frames)
        return AudioArtifact(
            path=str(out_path),
            duration=round(duration, 3),
            sample_rate=sample_rate,
            voice=voice,
            label="Synthetic audio generated from visual transcript. (MOCK placeholder — not speech.)",
            availability=self.availability(),
        )
