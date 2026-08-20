"""FaceDetector interface + adapters (§11).

Person detection ≠ face detection, so this is a separate subsystem. Candidates
(MediaPipe vs YOLO-face) are chosen from a documented benchmark; missing deps
report MODEL_UNAVAILABLE with the exact gap.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ml.common.config import MLConfig, get_ml_config
from ml.common.results import Availability, ModelInfo, available, model_unavailable
from ml.common.types import FaceDetection


class FaceDetector(ABC):
    name = "face_detector"

    @abstractmethod
    def availability(self) -> Availability: ...

    @abstractmethod
    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0) -> list[FaceDetection]: ...


class UnavailableFaceDetector(FaceDetector):
    def __init__(self, reason: str, missing: list[str]) -> None:
        self._reason = reason
        self._missing = missing

    def availability(self) -> Availability:
        return model_unavailable(self._reason, self._missing)

    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0):
        return []


class MediaPipeFaceDetector(FaceDetector):  # pragma: no cover - requires mediapipe
    def __init__(self, config: MLConfig) -> None:
        self.config = config
        import mediapipe as mp  # type: ignore

        self._mp = mp
        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.5
        )

    def availability(self) -> Availability:
        return available(
            ModelInfo(name="mediapipe-face", version="0.10", framework="mediapipe", license="Apache-2.0")
        )

    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0):
        import cv2  # type: ignore

        from ml.common.types import BBox

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self._detector.process(rgb)
        out: list[FaceDetection] = []
        if not res.detections:
            return out
        for det in res.detections:
            box = det.location_data.relative_bounding_box
            x1 = box.xmin * w
            y1 = box.ymin * h
            out.append(
                FaceDetection(
                    bbox=BBox(x1, y1, x1 + box.width * w, y1 + box.height * h),
                    confidence=float(det.score[0]) if det.score else 0.0,
                    frame_index=frame_index,
                    timestamp=timestamp,
                )
            )
        return out


def _mediapipe_available() -> tuple[bool, list[str]]:
    try:
        import mediapipe  # type: ignore  # noqa: F401

        return True, []
    except Exception:
        return False, ["mediapipe"]


def get_face_detector(config: MLConfig | None = None) -> FaceDetector:
    config = config or get_ml_config()

    if config.allow_mock:
        from ml.detection.adapters.mock_adapter import MockFaceDetector

        return MockFaceDetector()

    if config.face_detector == "mediapipe":
        ok, missing = _mediapipe_available()
        if not ok:
            return UnavailableFaceDetector(
                "MediaPipe face detector unavailable. Install mediapipe. See docs/model-selection.md.",
                missing,
            )
        try:  # pragma: no cover
            return MediaPipeFaceDetector(config)
        except Exception as exc:  # pragma: no cover
            return UnavailableFaceDetector(f"Failed to init MediaPipe: {exc}", ["mediapipe"])

    # yolo-face and others: not wired in this build.
    return UnavailableFaceDetector(
        f"Face detector '{config.face_detector}' is not installed in this environment.",
        [config.face_detector],
    )
