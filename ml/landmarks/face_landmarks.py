"""FaceLandmarker interface + adapters (§19).

Preferred back-end: MediaPipe Face Landmarker (468/478 points incl. iris,
Apache-2.0). When mediapipe is unavailable the factory returns an adapter that
reports MODEL_UNAVAILABLE; a mock adapter (tests only) emits geometric landmarks
inside a face box so Stage-B geometry can be exercised without the model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ml.common.config import MLConfig, get_ml_config
from ml.common.results import Availability, ModelInfo, available, model_unavailable
from ml.common.types import BBox, FaceLandmarks

# MediaPipe FaceMesh canonical index groups (subset used by this project).
MOUTH_OUTER = [61, 291, 0, 17, 39, 269, 405, 181]
LIPS = [61, 291, 0, 17]
JAW = [172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 397]
LEFT_EYE = [33, 133, 159, 145]
RIGHT_EYE = [362, 263, 386, 374]
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]


class FaceLandmarker(ABC):
    name = "face_landmarker"

    @abstractmethod
    def availability(self) -> Availability: ...

    @abstractmethod
    def landmarks(self, frame: Any, face_bbox: BBox) -> FaceLandmarks | None: ...


class UnavailableLandmarker(FaceLandmarker):
    def __init__(self, reason: str, missing: list[str]) -> None:
        self._reason = reason
        self._missing = missing

    def availability(self) -> Availability:
        return model_unavailable(self._reason, self._missing)

    def landmarks(self, frame: Any, face_bbox: BBox) -> FaceLandmarks | None:
        return None


class MediaPipeLandmarker(FaceLandmarker):  # pragma: no cover - requires mediapipe
    def __init__(self, config: MLConfig) -> None:
        self.config = config
        import mediapipe as mp  # type: ignore

        self._mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True, refine_landmarks=True, max_num_faces=1
        )

    def availability(self) -> Availability:
        return available(
            ModelInfo(name="mediapipe-face-landmarker", version="0.10",
                      framework="mediapipe", license="Apache-2.0")
        )

    def landmarks(self, frame: Any, face_bbox: BBox) -> FaceLandmarks | None:
        import cv2  # type: ignore

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self._mesh.process(rgb)
        if not res.multi_face_landmarks:
            return None
        h, w = frame.shape[:2]
        pts = [(lm.x * w, lm.y * h) for lm in res.multi_face_landmarks[0].landmark]
        return FaceLandmarks(
            points=pts,
            mouth=MOUTH_OUTER,
            lips=LIPS,
            jaw=JAW,
            left_eye=LEFT_EYE,
            right_eye=RIGHT_EYE,
            left_iris=LEFT_IRIS,
            right_iris=RIGHT_IRIS,
            image_size=(w, h),
        )


def _mediapipe_available() -> tuple[bool, list[str]]:
    try:
        import mediapipe  # type: ignore  # noqa: F401

        return True, []
    except Exception:
        return False, ["mediapipe"]


def get_landmarker(config: MLConfig | None = None) -> FaceLandmarker:
    config = config or get_ml_config()

    if config.allow_mock:
        from ml.landmarks.mock_landmarker import MockLandmarker

        return MockLandmarker()

    ok, missing = _mediapipe_available()
    if not ok:
        return UnavailableLandmarker(
            "Face landmarker unavailable. Install mediapipe (+ .task model). See docs/model-selection.md.",
            missing,
        )
    try:  # pragma: no cover
        return MediaPipeLandmarker(config)
    except Exception as exc:  # pragma: no cover
        return UnavailableLandmarker(f"Failed to init MediaPipe landmarker: {exc}", ["mediapipe"])
