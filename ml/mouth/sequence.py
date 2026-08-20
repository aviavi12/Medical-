"""Temporal mouth sequence construction (§22).

Lip reading uses temporal information — mouth frames are never classified
independently. This builds ordered, timestamp-preserving windows sized to the
model's required temporal window (``sequence_length`` / ``required_fps``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ml.common.types import MouthCrop


@dataclass
class TemporalMouthSequence:
    crops: list[MouthCrop] = field(default_factory=list)
    required_fps: float = 25.0
    sequence_length: int | None = None

    @property
    def start_time(self) -> float:
        return self.crops[0].timestamp if self.crops else 0.0

    @property
    def end_time(self) -> float:
        return self.crops[-1].timestamp if self.crops else 0.0

    def __len__(self) -> int:
        return len(self.crops)

    def timestamps(self) -> list[float]:
        return [c.timestamp for c in self.crops]


def build_sequence(
    crops: list[MouthCrop], required_fps: float = 25.0, sequence_length: int | None = None
) -> TemporalMouthSequence:
    """Order crops by timestamp; timestamps are always preserved (§18)."""
    ordered = sorted(crops, key=lambda c: c.timestamp)
    return TemporalMouthSequence(
        crops=ordered, required_fps=required_fps, sequence_length=sequence_length
    )


def window_sequences(
    crops: list[MouthCrop], window: int, stride: int, required_fps: float = 25.0
) -> list[TemporalMouthSequence]:
    """Split a long list of crops into overlapping fixed-length windows."""
    ordered = sorted(crops, key=lambda c: c.timestamp)
    out: list[TemporalMouthSequence] = []
    if window <= 0:
        return out
    i = 0
    while i < len(ordered):
        chunk = ordered[i : i + window]
        if not chunk:
            break
        out.append(TemporalMouthSequence(chunk, required_fps, window))
        if i + window >= len(ordered):
            break
        i += max(1, stride)
    return out
