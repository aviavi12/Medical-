"""Text-to-speech subsystem (generic synthetic voice by default)."""

from ml.tts.base import TextToSpeechProvider, get_tts_provider

__all__ = ["TextToSpeechProvider", "get_tts_provider"]
