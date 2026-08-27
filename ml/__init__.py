"""LipSight ML subsystems.

Each subsystem (detection, tracking, association, quality, landmarks, mouth,
lipreading, gaze, tts) exposes a clean interface plus pluggable adapters so any
individual model can be replaced without touching callers.
"""

__all__ = ["common"]
