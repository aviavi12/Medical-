"""Mock landmarker — UNIT TESTS ONLY (§24).

Places geometrically-plausible landmark points inside a face box so Stage-B
geometry (mouth ROI, eye/iris, head-pose scaffolding) can be exercised without
the real model. Guarded by ALLOW_MOCK_INFERENCE and marked mock=True.
"""

from __future__ import annotations

from typing import Any

from ml.common.results import Availability, ModelInfo, available
from ml.common.types import BBox, FaceLandmarks
from ml.landmarks.face_landmarks import (
    JAW,
    LEFT_EYE,
    LEFT_IRIS,
    LIPS,
    MOUTH_OUTER,
    RIGHT_EYE,
    RIGHT_IRIS,
)

_N = 478


class MockLandmarker:
    name = "face_landmarker"

    def availability(self) -> Availability:
        return available(ModelInfo(name="mock-landmarker", version="test",
                                   framework="mock", configuration={"mock": True}))

    def landmarks(self, frame: Any, face_bbox: BBox) -> FaceLandmarks:
        x1, y1 = face_bbox.x1, face_bbox.y1
        w, h = face_bbox.width or 1.0, face_bbox.height or 1.0
        cx, cy = face_bbox.center

        pts: list[tuple[float, float]] = [(cx, cy)] * _N

        def place(idx: int, fx: float, fy: float) -> None:
            if 0 <= idx < _N:
                pts[idx] = (x1 + fx * w, y1 + fy * h)

        # Mouth (lower-centre); spread horizontally so the ROI has real extent.
        mouth_layout = [(0.30, 0.72), (0.70, 0.72), (0.50, 0.66), (0.50, 0.80),
                        (0.38, 0.68), (0.62, 0.68), (0.62, 0.78), (0.38, 0.78)]
        for i, idx in enumerate(MOUTH_OUTER):
            fx, fy = mouth_layout[i % len(mouth_layout)]
            place(idx, fx, fy)
        for i, idx in enumerate(LIPS):
            place(idx, 0.30 + 0.13 * i, 0.72)

        # Jaw along the lower boundary.
        for i, idx in enumerate(JAW):
            place(idx, 0.15 + 0.06 * i, 0.90)

        # Eyes (upper third) and iris centres.
        for i, idx in enumerate(LEFT_EYE):
            place(idx, 0.33 + 0.02 * i, 0.35)
        for i, idx in enumerate(RIGHT_EYE):
            place(idx, 0.63 + 0.02 * i, 0.35)
        for idx in LEFT_IRIS:
            place(idx, 0.35, 0.36)
        for idx in RIGHT_IRIS:
            place(idx, 0.65, 0.36)

        return FaceLandmarks(
            points=pts,
            mouth=MOUTH_OUTER,
            lips=LIPS,
            jaw=JAW,
            left_eye=LEFT_EYE,
            right_eye=RIGHT_EYE,
            left_iris=LEFT_IRIS,
            right_iris=RIGHT_IRIS,
            image_size=face_bbox_shape(frame),
        )


def face_bbox_shape(frame: Any) -> tuple[int, int]:
    try:
        h, w = frame.shape[:2]
        return int(w), int(h)
    except Exception:
        return (0, 0)
