"""GazeEstimator (§32, §34, §35).

Combines head pose and iris offset into an approximate gaze direction. Iris is
preferred when reliable, otherwise head pose; when neither is usable the result
is UNKNOWN — a direction is never invented. Multi-person gaze reports a *possible*
target, never certainty about where someone is looking.
"""

from __future__ import annotations

from ml.common.config import MLConfig, get_ml_config
from ml.common.results import Availability, ModelInfo, available, model_unavailable
from ml.common.types import BBox, FaceLandmarks, GazeDirection, GazeResult, HeadPose
from ml.gaze.base import BaseGazeEstimator
from ml.gaze.head_pose import estimate_head_pose
from ml.gaze.iris import iris_offset


class GazeEstimator(BaseGazeEstimator):
    def __init__(
        self,
        config: MLConfig | None = None,
        yaw_threshold: float = 12.0,
        pitch_threshold: float = 12.0,
        iris_threshold: float = 0.25,
    ) -> None:
        self.config = config or get_ml_config()
        self.yaw_threshold = yaw_threshold
        self.pitch_threshold = pitch_threshold
        self.iris_threshold = iris_threshold

    def _model_info(self) -> ModelInfo:
        return ModelInfo(name="gaze-geometric", version="0.1", framework="opencv/numpy")

    def availability(self) -> Availability:
        # Gaze runs on landmarks; if the landmarker is unavailable so is gaze.
        return available(self._model_info())

    def estimate(self, landmarks: FaceLandmarks | None, timestamp: float = 0.0) -> GazeResult:
        if landmarks is None:
            return GazeResult(
                timestamp=timestamp,
                direction=GazeDirection.UNKNOWN,
                confidence=0.0,
                availability=model_unavailable(
                    "Gaze requires facial landmarks, which are unavailable.",
                    ["face landmarks (mediapipe)"],
                ),
            )

        head = estimate_head_pose(landmarks)
        iris = iris_offset(landmarks)

        direction, confidence = self._classify(head, iris)
        return GazeResult(
            timestamp=timestamp,
            direction=direction,
            confidence=round(confidence, 3),
            head_pose=head,
            availability=available(self._model_info()),
        )

    def _classify(self, head: HeadPose, iris) -> tuple[GazeDirection, float]:
        # Prefer iris when reliable, blended with head pose.
        if iris.reliable:
            h = iris.horizontal
            v = iris.vertical
            if abs(h) < self.iris_threshold and abs(v) < self.iris_threshold and abs(head.yaw) < self.yaw_threshold:
                return GazeDirection.CENTER, 0.7
            if abs(h) >= abs(v):
                return (GazeDirection.RIGHT if h > 0 else GazeDirection.LEFT), min(0.9, 0.5 + abs(h))
            return (GazeDirection.DOWN if v > 0 else GazeDirection.UP), min(0.9, 0.5 + abs(v))

        # Fall back to head pose.
        if head.confidence <= 0.0:
            return GazeDirection.UNKNOWN, 0.0
        if abs(head.yaw) < self.yaw_threshold and abs(head.pitch) < self.pitch_threshold:
            return GazeDirection.CENTER, head.confidence * 0.7
        if abs(head.yaw) >= abs(head.pitch):
            return (GazeDirection.RIGHT if head.yaw > 0 else GazeDirection.LEFT), head.confidence
        return (GazeDirection.DOWN if head.pitch > 0 else GazeDirection.UP), head.confidence

    def gaze_toward(
        self, source_face: BBox, gaze: GazeResult, others: list[tuple[int, BBox]]
    ) -> tuple[int | None, float]:
        """Estimate whether ``gaze`` points toward another person's face (§35).

        Returns (target_person_id, confidence) or (None, 0). Deliberately coarse
        and reported as 'possible' by callers — never a certainty.
        """
        if gaze.direction in (GazeDirection.UNKNOWN, GazeDirection.CENTER):
            return None, 0.0
        scx, scy = source_face.center
        best_id: int | None = None
        best_conf = 0.0
        for pid, bbox in others:
            ocx, ocy = bbox.center
            dx = ocx - scx
            horiz = GazeDirection.RIGHT if dx > 0 else GazeDirection.LEFT
            if gaze.direction == horiz:
                # Confidence scales with gaze confidence, capped low to signal
                # approximation.
                conf = min(0.75, 0.4 + 0.35 * gaze.confidence)
                if conf > best_conf:
                    best_conf = conf
                    best_id = pid
        return best_id, round(best_conf, 3)


def get_gaze_estimator(config: MLConfig | None = None) -> GazeEstimator:
    return GazeEstimator(config)
