"""Head-pose estimation (§33).

Estimates yaw/pitch/roll from facial landmarks using a geometric heuristic:
- roll  ← angle of the inter-eye line
- yaw   ← horizontal offset of the nose from the eye midpoint, normalised by
          inter-ocular distance
- pitch ← vertical offset of the nose from the eye–mouth midline

This is an approximate real measurement (documented as approximate, §33), not an
ML inference. Head direction is deliberately kept distinct from eye gaze (§34).
"""

from __future__ import annotations

import math

from ml.common.types import FaceLandmarks, HeadPose

NOSE_TIP = 1
MOUTH_CENTER = [13, 14]  # upper/lower inner lip midline


def _centroid(landmarks: FaceLandmarks, indices: list[int]) -> tuple[float, float]:
    pts = landmarks.region_points(indices)
    if not pts:
        return (0.0, 0.0)
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def estimate_head_pose(landmarks: FaceLandmarks) -> HeadPose:
    left_eye = _centroid(landmarks, landmarks.left_eye)
    right_eye = _centroid(landmarks, landmarks.right_eye)
    eye_mid = ((left_eye[0] + right_eye[0]) / 2.0, (left_eye[1] + right_eye[1]) / 2.0)

    interocular = math.hypot(right_eye[0] - left_eye[0], right_eye[1] - left_eye[1]) or 1.0

    # roll from eye line
    roll = math.degrees(math.atan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]))

    nose = landmarks.points[NOSE_TIP] if NOSE_TIP < len(landmarks.points) else eye_mid
    mouth = _centroid(landmarks, landmarks.mouth or landmarks.lips)

    # yaw: nose horizontal offset from eye midpoint (normalised) → degrees-ish
    yaw = math.degrees(math.atan2(nose[0] - eye_mid[0], interocular))

    # pitch: nose vertical offset relative to eye→mouth span
    face_height = (mouth[1] - eye_mid[1]) or interocular
    pitch = math.degrees(math.atan2((nose[1] - eye_mid[1]) - 0.5 * face_height, abs(face_height) or 1.0))

    # Confidence from how well-defined the geometry is (eyes/mouth present).
    have_eyes = bool(landmarks.left_eye and landmarks.right_eye)
    have_mouth = bool(landmarks.mouth or landmarks.lips)
    confidence = 0.6 if (have_eyes and have_mouth) else (0.3 if have_eyes else 0.0)

    return HeadPose(yaw=round(yaw, 2), pitch=round(pitch, 2), roll=round(roll, 2),
                    confidence=confidence)
