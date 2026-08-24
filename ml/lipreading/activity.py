"""Visual Speaking Activity Estimate (§17) and silence handling (§18).

From a window of grayscale lower-face crops we estimate whether the mouth is
*moving as in speech* — WITHOUT running the transcription model. This is a
motion heuristic, deliberately named an **estimate**, never "speech detection":
we cannot hear anything, we only observe lip motion.

- SPEAKING_LIKELY : sustained lip motion consistent with talking.
- NOT_SPEAKING    : the mouth is essentially still.
- UNCERTAIN       : too little signal / borderline motion to call it.

When a window is NOT_SPEAKING the pipeline returns NO_SPEECH_EVIDENCE for that
window instead of forcing the model to invent a transcript (§18).
"""

from __future__ import annotations

import os

SPEAKING_LIKELY = "SPEAKING_LIKELY"
NOT_SPEAKING = "NOT_SPEAKING"
UNCERTAIN = "UNCERTAIN"

# Env-tunable thresholds on the mean frame-to-frame motion (uint8 intensity units)
# inside the mouth region of a 96x96 lower-face crop.
_SPEAK_MOTION = float(os.environ.get("ACTIVITY_SPEAK_MOTION", "3.2"))
_STILL_MOTION = float(os.environ.get("ACTIVITY_STILL_MOTION", "1.4"))
_MIN_FRAMES = 4


def _mouth_region(crop):
    """Lower-central mouth region of a 96x96 lower-face crop."""
    h, w = crop.shape[:2]
    y0, y1 = int(h * 0.50), int(h * 0.95)
    x0, x1 = int(w * 0.22), int(w * 0.78)
    return crop[y0:y1, x0:x1]


def motion_score(gray_crops: list) -> float:
    """Mean absolute frame-to-frame intensity change in the mouth region.

    Returns 0.0 for fewer than two usable frames. Robust to a static camera:
    a still face yields a near-zero score, a talking face several units.
    """
    try:
        import numpy as np  # type: ignore
    except Exception:  # pragma: no cover
        return 0.0
    if not gray_crops or len(gray_crops) < 2:
        return 0.0
    diffs = []
    prev = _mouth_region(gray_crops[0]).astype("float32")
    for c in gray_crops[1:]:
        cur = _mouth_region(c).astype("float32")
        if cur.shape != prev.shape:
            # Crops can vary by a pixel after resize edge cases; align by min shape.
            hh = min(cur.shape[0], prev.shape[0])
            ww = min(cur.shape[1], prev.shape[1])
            diffs.append(float(np.mean(np.abs(cur[:hh, :ww] - prev[:hh, :ww]))))
        else:
            diffs.append(float(np.mean(np.abs(cur - prev))))
        prev = cur
    if not diffs:
        return 0.0
    return float(np.mean(diffs))


def estimate_activity(gray_crops: list) -> tuple[str, float]:
    """Return (activity_state, motion_score) for a window of gray crops."""
    if not gray_crops or len(gray_crops) < _MIN_FRAMES:
        return UNCERTAIN, 0.0
    score = motion_score(gray_crops)
    if score >= _SPEAK_MOTION:
        return SPEAKING_LIKELY, score
    if score <= _STILL_MOTION:
        return NOT_SPEAKING, score
    return UNCERTAIN, score
