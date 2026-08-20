"""Face alignment (§20).

Estimate face orientation from eye landmarks and rotate so the eyes are
horizontal before mouth extraction, so the ROI follows the person's face rather
than a fixed rectangle. Pure geometry.
"""

from __future__ import annotations

import math
from typing import Any

from ml.common.types import FaceLandmarks


def eye_centers(landmarks: FaceLandmarks) -> tuple[tuple[float, float], tuple[float, float]]:
    def centroid(indices: list[int]) -> tuple[float, float]:
        pts = landmarks.region_points(indices)
        if not pts:
            return (0.0, 0.0)
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    return centroid(landmarks.left_eye), centroid(landmarks.right_eye)


def roll_angle_degrees(landmarks: FaceLandmarks) -> float:
    """In-plane rotation (roll) from the line between the eyes."""
    left, right = eye_centers(landmarks)
    dy = right[1] - left[1]
    dx = right[0] - left[0]
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(dy, dx))


def align_face(frame: Any, landmarks: FaceLandmarks):
    """Rotate ``frame`` about the eye midpoint so the eyes are horizontal.

    Returns (aligned_frame, angle_degrees). If OpenCV is unavailable, returns the
    original frame and the measured angle (callers can still use the angle).
    """
    angle = roll_angle_degrees(landmarks)
    try:
        import cv2  # type: ignore

        left, right = eye_centers(landmarks)
        center = ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0)
        h, w = frame.shape[:2]
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        aligned = cv2.warpAffine(frame, m, (w, h), flags=cv2.INTER_LINEAR)
        return aligned, angle
    except Exception:
        return frame, angle
