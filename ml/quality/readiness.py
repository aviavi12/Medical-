"""Lip-reading readiness score (§15) and quality gates (§65).

The readiness score is a configurable weighted blend of per-person aggregates.
Weights live in a single place (ReadinessWeights) — never hard-coded across
files. Quality gates decide whether the expensive lip-reading model runs at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from ml.common.config import MLConfig, QualityGates, ReadinessWeights, get_ml_config


@dataclass
class PersonAggregate:
    """Per-person averages used for readiness scoring (0..1 unless noted)."""

    face_quality: float          # 0..100
    mouth_visibility: float      # 0..1
    face_resolution: float       # 0..1
    tracking_stability: float    # 0..1
    pose_quality: float          # 0..1
    sharpness: float             # 0..1


def lip_reading_readiness(agg: PersonAggregate, weights: ReadinessWeights | None = None) -> float:
    """Return a 0–100 readiness score from configurable weights."""
    w = (weights or ReadinessWeights()).normalized()
    score = (
        w.face_quality * (agg.face_quality / 100.0)
        + w.mouth_visibility * agg.mouth_visibility
        + w.face_resolution * agg.face_resolution
        + w.tracking_stability * agg.tracking_stability
        + w.pose_quality * agg.pose_quality
        + w.sharpness * agg.sharpness
    )
    return round(100.0 * max(0.0, min(1.0, score)), 2)


def passes_quality_gates(
    *,
    face_width: float,
    face_quality: float,
    mouth_visibility: float,
    tracking_stability: float,
    gates: QualityGates | None = None,
    override: bool = False,
) -> tuple[bool, list[str]]:
    """Check §65 thresholds. Returns (passed, list_of_failures). ``override`` lets
    advanced users bypass gates but still records what was skipped."""
    gates = gates or get_ml_config().gates
    failures: list[str] = []
    if face_width < gates.min_face_width:
        failures.append(
            f"Face resolution is insufficient (width {face_width:.0f}px < {gates.min_face_width}px)."
        )
    if face_quality < gates.min_face_quality:
        failures.append(
            f"Face quality {face_quality:.0f} is below the minimum of {gates.min_face_quality:.0f}."
        )
    if mouth_visibility < gates.min_mouth_visibility:
        failures.append(
            f"Mouth region is not consistently visible ({mouth_visibility:.2f} < {gates.min_mouth_visibility:.2f})."
        )
    if tracking_stability < gates.min_tracking_stability:
        failures.append(
            f"Tracking stability {tracking_stability:.2f} is below {gates.min_tracking_stability:.2f}."
        )
    passed = len(failures) == 0
    if override:
        return True, failures
    return passed, failures


def default_weights(config: MLConfig | None = None) -> ReadinessWeights:
    return (config or get_ml_config()).weights
