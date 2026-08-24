"""Lip-reading readiness score (§15), combined-score gate (§10, §11) and the
per-person quality report (§25).

The readiness score is a configurable weighted blend of per-person aggregates.
Weights live in a single place (ReadinessWeights) — never hard-coded across
files. The *gate* that decides whether "Analyze Speech" is offered is the
combined score compared against configurable thresholds — deliberately NOT a
single face-size threshold. When a person is not READY we report the specific
weak signals (§24) rather than a generic failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ml.common.config import MLConfig, QualityGates, ReadinessWeights, get_ml_config

# Readiness status values (§10).
READY = "READY"
WARNING = "WARNING"
INSUFFICIENT = "INSUFFICIENT"


@dataclass
class PersonAggregate:
    """Per-person averages used for readiness scoring (0..1 unless noted)."""

    face_quality: float          # 0..100
    mouth_visibility: float      # 0..1
    face_resolution: float       # 0..1
    tracking_stability: float    # 0..1
    pose_quality: float          # 0..1
    sharpness: float             # 0..1


@dataclass
class PersonQualityReport:
    """The full, honest per-person quality report shown in the gallery (§25)."""

    status: str                       # READY / WARNING / INSUFFICIENT
    readiness_score: float            # 0..100 combined score (the gate signal)
    face_quality_score: float         # 0..100
    lip_readiness_score: float        # 0..100 (== readiness_score; explicit for UI)
    usable_duration: float            # seconds of visible/usable face time
    visible_ratio: float              # 0..1 fraction of scanned frames present
    avg_face_width_px: float          # average detected face width in pixels
    avg_mouth_visibility: float       # 0..1
    avg_sharpness: float              # 0..1
    avg_pose_quality: float           # 0..1
    tracking_stability: float         # 0..1
    reasons: list[str] = field(default_factory=list)   # specific weaknesses (§24)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "readiness_score": round(self.readiness_score, 1),
            "face_quality_score": round(self.face_quality_score, 1),
            "lip_readiness_score": round(self.lip_readiness_score, 1),
            "usable_duration": round(self.usable_duration, 2),
            "visible_ratio": round(self.visible_ratio, 3),
            "avg_face_width_px": round(self.avg_face_width_px, 1),
            "avg_mouth_visibility_pct": round(self.avg_mouth_visibility * 100, 1),
            "avg_sharpness": round(self.avg_sharpness, 3),
            "avg_pose_quality": round(self.avg_pose_quality, 3),
            "tracking_stability": round(self.tracking_stability, 3),
            "reasons": list(self.reasons),
        }


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


def _weakness_reasons(
    *,
    avg_face_width_px: float,
    avg_mouth_visibility: float,
    avg_sharpness: float,
    avg_pose_quality: float,
    tracking_stability: float,
    usable_duration: float,
    gates: QualityGates,
) -> list[str]:
    """Human-readable reasons a person may lip-read poorly (§24). Ordered by
    typical impact so the most important limitation is shown first."""
    reasons: list[str] = []
    if avg_face_width_px and avg_face_width_px < gates.min_face_width:
        reasons.append(
            f"Face is too small to lip-read (average width {avg_face_width_px:.0f}px; "
            f"needs at least {gates.min_face_width}px, {gates.recommended_face_width}px recommended)."
        )
    elif avg_face_width_px and avg_face_width_px < gates.recommended_face_width:
        reasons.append(
            f"Face is small (average width {avg_face_width_px:.0f}px; "
            f"{gates.recommended_face_width}px+ recommended for reliable lip reading)."
        )
    if avg_mouth_visibility < gates.min_mouth_visibility:
        reasons.append(
            f"Mouth is not consistently visible ({avg_mouth_visibility * 100:.0f}% of frames); "
            "the person may be turned away or the mouth is occluded."
        )
    if avg_pose_quality < 0.5:
        reasons.append(
            "Head is frequently turned away from the camera (non-frontal pose reduces accuracy)."
        )
    if avg_sharpness < 0.35:
        reasons.append("Footage is soft / motion-blurred, which hides fine lip movement.")
    if tracking_stability < gates.min_tracking_stability:
        reasons.append(
            f"The face was tracked in only {tracking_stability * 100:.0f}% of the time it was on "
            "screen (intermittent detection)."
        )
    if usable_duration < 0.5:
        reasons.append(
            f"Only {usable_duration:.1f}s of usable face time — too short for a reliable transcript."
        )
    return reasons


def readiness_status(
    *,
    readiness_score: float,
    avg_face_width_px: float,
    avg_mouth_visibility: float,
    avg_sharpness: float,
    avg_pose_quality: float,
    tracking_stability: float,
    usable_duration: float,
    face_quality_score: float,
    visible_ratio: float,
    gates: QualityGates | None = None,
) -> PersonQualityReport:
    """Combined-score gate → READY / WARNING / INSUFFICIENT plus a full report.

    The status is driven by the *combined* readiness score (not a single
    face-size threshold, §11), with an absolute unusable-face floor.
    """
    gates = gates or get_ml_config().gates
    reasons = _weakness_reasons(
        avg_face_width_px=avg_face_width_px,
        avg_mouth_visibility=avg_mouth_visibility,
        avg_sharpness=avg_sharpness,
        avg_pose_quality=avg_pose_quality,
        tracking_stability=tracking_stability,
        usable_duration=usable_duration,
        gates=gates,
    )

    # Absolute "unusable" floor: a face below the minimum width, or with almost
    # no usable time, cannot be lip-read no matter the blended score.
    unusable = (
        (avg_face_width_px and avg_face_width_px < gates.min_face_width)
        or usable_duration < 0.4
    )

    if unusable or readiness_score < gates.warning_score:
        status = INSUFFICIENT
    elif readiness_score < gates.ready_score or reasons:
        status = WARNING
    else:
        status = READY

    return PersonQualityReport(
        status=status,
        readiness_score=readiness_score,
        face_quality_score=face_quality_score,
        lip_readiness_score=readiness_score,
        usable_duration=usable_duration,
        visible_ratio=visible_ratio,
        avg_face_width_px=avg_face_width_px,
        avg_mouth_visibility=avg_mouth_visibility,
        avg_sharpness=avg_sharpness,
        avg_pose_quality=avg_pose_quality,
        tracking_stability=tracking_stability,
        reasons=reasons,
    )


def passes_quality_gates(
    *,
    face_width: float,
    face_quality: float,
    mouth_visibility: float,
    tracking_stability: float,
    gates: QualityGates | None = None,
    override: bool = False,
    readiness_score: float | None = None,
    avg_sharpness: float = 1.0,
    avg_pose_quality: float = 1.0,
    usable_duration: float = 999.0,
    visible_ratio: float = 1.0,
) -> tuple[bool, list[str]]:
    """Decide whether the expensive lip-reading model runs (§10, §11, §65).

    Uses the combined-score status: READY and WARNING run; only INSUFFICIENT is
    blocked (with the specific reasons). ``override`` bypasses the block but
    still returns what was flagged, so the UI can warn honestly.

    ``readiness_score`` may be passed directly (from the stored per-person
    aggregate); otherwise a conservative estimate is derived from the signals.
    """
    gates = gates or get_ml_config().gates
    if readiness_score is None:
        readiness_score = lip_reading_readiness(
            PersonAggregate(
                face_quality=face_quality,
                mouth_visibility=mouth_visibility,
                face_resolution=min(1.0, face_width / 200.0) if face_width else 0.0,
                tracking_stability=tracking_stability,
                pose_quality=avg_pose_quality,
                sharpness=avg_sharpness,
            ),
            get_ml_config().weights,
        )
    report = readiness_status(
        readiness_score=readiness_score,
        avg_face_width_px=face_width,
        avg_mouth_visibility=mouth_visibility,
        avg_sharpness=avg_sharpness,
        avg_pose_quality=avg_pose_quality,
        tracking_stability=tracking_stability,
        usable_duration=usable_duration,
        face_quality_score=face_quality,
        visible_ratio=visible_ratio,
        gates=gates,
    )
    passed = report.status != INSUFFICIENT
    failures = report.reasons or (
        [] if passed else ["Combined visual quality is insufficient for reliable lip reading."]
    )
    if override:
        return True, failures
    return passed, failures


def default_weights(config: MLConfig | None = None) -> ReadinessWeights:
    return (config or get_ml_config()).weights
