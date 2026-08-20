"""Iris / eye analysis (§34).

Computes the iris centre position relative to the eye's horizontal/vertical
extent. Returns offsets in [-1, 1] plus a reliability flag. When iris landmarks
are absent or the eye is too small, reliability is False and callers fall back to
head pose (never invent a gaze).
"""

from __future__ import annotations

from dataclasses import dataclass

from ml.common.types import FaceLandmarks


@dataclass
class IrisOffset:
    horizontal: float  # -1 (left) .. +1 (right)
    vertical: float    # -1 (up) .. +1 (down)
    reliable: bool


def _bounds(pts: list[tuple[float, float]]):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _eye_iris_offset(landmarks: FaceLandmarks, eye_idx: list[int], iris_idx: list[int]):
    eye_pts = landmarks.region_points(eye_idx)
    iris_pts = landmarks.region_points(iris_idx)
    if len(eye_pts) < 2 or not iris_pts:
        return None
    ex1, ey1, ex2, ey2 = _bounds(eye_pts)
    ew = (ex2 - ex1) or 1.0
    eh = (ey2 - ey1) or 1.0
    icx = sum(p[0] for p in iris_pts) / len(iris_pts)
    icy = sum(p[1] for p in iris_pts) / len(iris_pts)
    h = ((icx - ex1) / ew) * 2 - 1
    v = ((icy - ey1) / eh) * 2 - 1
    return (h, v, ew)


def iris_offset(landmarks: FaceLandmarks, min_eye_width: float = 6.0) -> IrisOffset:
    left = _eye_iris_offset(landmarks, landmarks.left_eye, landmarks.left_iris)
    right = _eye_iris_offset(landmarks, landmarks.right_eye, landmarks.right_iris)

    samples = [s for s in (left, right) if s is not None]
    if not samples:
        return IrisOffset(0.0, 0.0, reliable=False)

    h = sum(s[0] for s in samples) / len(samples)
    v = sum(s[1] for s in samples) / len(samples)
    widths = [s[2] for s in samples]
    reliable = min(widths) >= min_eye_width
    return IrisOffset(horizontal=round(h, 3), vertical=round(v, 3), reliable=reliable)
