"""Lip-reading (visual speech recognition) subsystem — the central ML component."""

from ml.lipreading.base import InputContract, LipReadingModel, get_lip_reading_model

__all__ = ["InputContract", "LipReadingModel", "get_lip_reading_model"]
