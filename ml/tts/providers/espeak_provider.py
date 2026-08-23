"""eSpeak NG TTS provider (§42) — a real, fully-offline generic synthetic voice.

Not neural (the voice is robotic), but it is genuine synthesized speech from the
transcript, needs no downloaded weights, and never clones a real person's voice
(§43). Piper remains the higher-quality option when its voice models are
reachable; this is the dependable local default.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

from ml.common.results import Availability, ModelInfo, available, model_unavailable
from ml.common.types import AudioArtifact
from ml.tts.base import SYNTHETIC_LABEL, TextToSpeechProvider


class EspeakTTS(TextToSpeechProvider):
    name = "tts"

    def __init__(self, voice_lang: str = "en-us", words_per_minute: int = 150) -> None:
        self.voice_lang = voice_lang
        self.wpm = words_per_minute

    def _binary(self) -> str | None:
        return shutil.which("espeak-ng") or shutil.which("espeak")

    def availability(self) -> Availability:
        if self._binary() is None:
            return model_unavailable(
                "eSpeak NG is not installed. Install it (apt-get install espeak-ng) "
                "or configure another TTS provider.",
                ["espeak-ng"],
            )
        return available(ModelInfo(name="espeak-ng", version="1.x", framework="espeak-ng",
                                   license="GPL-3.0", configuration={"voice": self.voice_lang,
                                                                     "generic": True}))

    def synthesize(self, text, out_path, voice="generic", authorized_voice_confirmation=False):
        self.guard_voice(voice, authorized_voice_confirmation)
        binary = self._binary()
        if binary is None:
            return AudioArtifact(path="", duration=0.0, sample_rate=0, voice=voice,
                                 label=SYNTHETIC_LABEL, availability=self.availability())
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [binary, "-v", self.voice_lang, "-s", str(self.wpm), "-w", str(out_path), text or " "],
            capture_output=True, check=True, timeout=120,
        )
        duration, sample_rate = _wav_info(out_path)
        return AudioArtifact(
            path=str(out_path),
            duration=round(duration, 3),
            sample_rate=sample_rate,
            voice="generic-espeak",
            label=SYNTHETIC_LABEL,
            availability=available(ModelInfo(name="espeak-ng", framework="espeak-ng",
                                             license="GPL-3.0")),
        )


def _wav_info(path: Path) -> tuple[float, int]:
    try:
        with wave.open(str(path), "r") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return (frames / rate if rate else 0.0), rate
    except Exception:
        return 0.0, 22050
