"""Mock detection adapters — UNIT TESTS ONLY (§24).

Guarded by ALLOW_MOCK_INFERENCE. These produce deterministic synthetic
detections so the pipeline and integration tests can run without GPUs/weights.
They must NEVER be used as a production result; every result they emit carries a
`mock=True` marker in its ModelInfo configuration.
"""

from __future__ import annotations

from typing import Any

from ml.common.results import Availability, ModelInfo, available
from ml.common.types import BBox, FaceDetection, PersonDetection


def _frame_size(frame: Any) -> tuple[int, int]:
    try:
        h, w = frame.shape[:2]
        return int(w), int(h)
    except Exception:
        return 1280, 720


class MockPersonDetector:
    name = "person_detector"

    def availability(self) -> Availability:
        return available(ModelInfo(name="mock-person", version="test", framework="mock",
                                   configuration={"mock": True}))

    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0) -> list[PersonDetection]:
        w, h = _frame_size(frame)
        # Two stable people: one central, one near the right edge (§8 secondary).
        boxes = [
            (0.15 * w, 0.10 * h, 0.45 * w, 0.95 * h, 0.95),
            (0.70 * w, 0.15 * h, 0.95 * w, 0.90 * h, 0.82),
        ]
        return [
            PersonDetection(
                bbox=BBox(x1, y1, x2, y2),
                confidence=conf,
                frame_index=frame_index,
                timestamp=timestamp,
            )
            for (x1, y1, x2, y2, conf) in boxes
        ]


class MockFaceDetector:
    name = "face_detector"

    def availability(self) -> Availability:
        return available(ModelInfo(name="mock-face", version="test", framework="mock",
                                   configuration={"mock": True}))

    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0) -> list[FaceDetection]:
        w, h = _frame_size(frame)
        # One face in the upper part of each mock person box.
        faces = [
            (0.22 * w, 0.12 * h, 0.38 * w, 0.32 * h, 0.93),
            (0.75 * w, 0.18 * h, 0.90 * w, 0.38 * h, 0.80),
        ]
        return [
            FaceDetection(
                bbox=BBox(x1, y1, x2, y2),
                confidence=conf,
                frame_index=frame_index,
                timestamp=timestamp,
            )
            for (x1, y1, x2, y2, conf) in faces
        ]
