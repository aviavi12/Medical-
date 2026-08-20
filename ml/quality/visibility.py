"""Brightness / contrast / visibility metrics.

Brightness and contrast are measured directly from pixels. Without landmarks
(coarse scan), mouth/eye visibility are *heuristic proxies* derived from face
resolution and sharpness — clearly documented as approximate. Stage B recomputes
true mouth/eye visibility from landmarks.
"""

from __future__ import annotations

from typing import Any


def brightness_score(gray: Any) -> float:
    """Mean luminance mapped to 0..1, penalising very dark or blown-out crops."""
    try:
        import numpy as np  # type: ignore

        mean = float(np.mean(gray)) / 255.0
    except Exception:
        return 0.5
    # Ideal around 0.35–0.75; falls off toward 0 and 1.
    if mean < 0.35:
        return max(0.0, mean / 0.35)
    if mean > 0.85:
        return max(0.0, (1.0 - mean) / 0.15)
    return 1.0


def contrast_score(gray: Any) -> float:
    try:
        import numpy as np  # type: ignore

        std = float(np.std(gray)) / 128.0
        return max(0.0, min(1.0, std))
    except Exception:
        return 0.5


def resolution_score(face_width: float, min_width: float = 80.0, good_width: float = 200.0) -> float:
    """0 below ``min_width``, 1 at/above ``good_width``, linear between."""
    if face_width <= min_width:
        return max(0.0, face_width / (min_width * 2))  # small partial credit under threshold
    if face_width >= good_width:
        return 1.0
    return (face_width - min_width) / (good_width - min_width)


def heuristic_mouth_visibility(resolution: float, sharpness: float) -> float:
    """Approximate mouth visibility without landmarks (proxy, not a measurement)."""
    return round(min(1.0, 0.5 * resolution + 0.5 * sharpness), 4)
