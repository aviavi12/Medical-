"""TextToSpeechProvider interface (§42, §43).

Default is a generic synthetic voice (Piper). The system NEVER clones the voice
of a person in an uploaded video. Any non-generic/authorized voice requires an
explicit permission confirmation. All generated audio is labelled
"Synthetic audio generated from visual transcript."
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ml.common.config import MLConfig, get_ml_config
from ml.common.results import Availability, model_unavailable
from ml.common.types import AudioArtifact

SYNTHETIC_LABEL = "Synthetic audio generated from visual transcript."


class VoicePermissionError(PermissionError):
    """Raised when a non-generic voice is requested without authorization (§43)."""


class TextToSpeechProvider(ABC):
    name = "tts"

    @abstractmethod
    def availability(self) -> Availability: ...

    @abstractmethod
    def synthesize(
        self, text: str, out_path: str | Path, voice: str = "generic",
        authorized_voice_confirmation: bool = False,
    ) -> AudioArtifact: ...

    @staticmethod
    def guard_voice(voice: str, authorized_voice_confirmation: bool) -> None:
        if voice != "generic" and not authorized_voice_confirmation:
            raise VoicePermissionError(
                "A non-generic voice requires explicit confirmation that you have "
                "permission to use it. Default TTS uses a generic synthetic voice."
            )


class UnavailableTTS(TextToSpeechProvider):
    def __init__(self, reason: str, missing: list[str]) -> None:
        self._reason = reason
        self._missing = missing

    def availability(self) -> Availability:
        return model_unavailable(self._reason, self._missing)

    def synthesize(self, text, out_path, voice="generic", authorized_voice_confirmation=False):
        self.guard_voice(voice, authorized_voice_confirmation)
        return AudioArtifact(
            path="", duration=0.0, sample_rate=0, voice=voice,
            label=SYNTHETIC_LABEL, availability=self.availability(),
        )


def get_tts_provider(config: MLConfig | None = None) -> TextToSpeechProvider:
    config = config or get_ml_config()

    if config.allow_mock:
        from ml.tts.providers.mock_provider import MockTTS

        return MockTTS()

    if config.tts_provider in ("local", "piper"):
        # Prefer Piper (neural, higher quality) when installed; otherwise use the
        # dependable, fully-offline eSpeak NG generic voice.
        try:
            import piper  # type: ignore  # noqa: F401

            from ml.tts.providers.piper_provider import PiperTTS  # pragma: no cover

            return PiperTTS(config)  # pragma: no cover
        except Exception:
            pass
        from ml.tts.providers.espeak_provider import EspeakTTS

        provider = EspeakTTS()
        if provider.availability().is_available:
            return provider
        return UnavailableTTS(
            "No local TTS available. Install espeak-ng (apt-get install espeak-ng) "
            "or piper-tts + a voice model. See docs/model-selection.md.",
            ["espeak-ng", "piper-tts"],
        )

    if config.tts_provider == "espeak":
        from ml.tts.providers.espeak_provider import EspeakTTS

        return EspeakTTS()

    return UnavailableTTS(
        f"TTS provider '{config.tts_provider}' is not configured.", [config.tts_provider]
    )
