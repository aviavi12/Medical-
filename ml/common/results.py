"""The honesty envelope (§2, §64, §97).

Every ML subsystem reports one of four explicit states so a real model result is
never confused with a placeholder, and missing dependencies are named exactly
instead of being faked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AvailabilityState(str, Enum):
    """Explicit outcome state for any ML inference."""

    REAL_RESULT = "REAL_RESULT"
    """A real model performed inference and produced this output."""

    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    """Weights / dependencies / GPU / license missing. ``detail`` says what."""

    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    """A real model ran but confidence is below threshold."""

    NO_SIGNAL = "NO_SIGNAL"
    """Visual quality gates failed; the expensive model was not run."""


@dataclass(frozen=True)
class ModelInfo:
    """Reproducibility metadata attached to every result (§53, §98, §99)."""

    name: str
    version: str = "0.0.0"
    framework: str = "unknown"
    device: str = "cpu"
    checkpoint: str | None = None
    license: str | None = None
    configuration: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "framework": self.framework,
            "device": self.device,
            "checkpoint": self.checkpoint,
            "license": self.license,
            "configuration": self.configuration,
        }


@dataclass
class Availability:
    """Wraps a subsystem outcome with its honesty state.

    ``is_real`` is the single source of truth callers use to decide whether an
    output may be shown as a genuine model prediction.
    """

    state: AvailabilityState
    model: ModelInfo | None = None
    detail: str | None = None
    missing: list[str] = field(default_factory=list)

    @property
    def is_real(self) -> bool:
        return self.state == AvailabilityState.REAL_RESULT

    @property
    def is_available(self) -> bool:
        """True when a model could run at all (real or low-confidence)."""
        return self.state in (
            AvailabilityState.REAL_RESULT,
            AvailabilityState.LOW_CONFIDENCE,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "detail": self.detail,
            "missing": self.missing,
            "model": self.model.as_dict() if self.model else None,
        }


# ── convenience constructors ────────────────────────────────────────────────


def available(model: ModelInfo) -> Availability:
    return Availability(state=AvailabilityState.REAL_RESULT, model=model)


def model_unavailable(reason: str, missing: list[str] | None = None,
                      model: ModelInfo | None = None) -> Availability:
    return Availability(
        state=AvailabilityState.MODEL_UNAVAILABLE,
        detail=reason,
        missing=missing or [],
        model=model,
    )


def low_confidence(model: ModelInfo, detail: str | None = None) -> Availability:
    return Availability(
        state=AvailabilityState.LOW_CONFIDENCE, model=model, detail=detail
    )


def no_signal(detail: str, model: ModelInfo | None = None) -> Availability:
    return Availability(state=AvailabilityState.NO_SIGNAL, detail=detail, model=model)
