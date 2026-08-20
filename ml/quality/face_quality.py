"""FaceQualityEstimator (§14).

Computes real image-quality metrics on a face crop and produces a 0–100 score
with configurable interpretation bands. Metrics that genuinely require landmarks
(true mouth/eye visibility, precise pose) are flagged as heuristic in the coarse
scan and refined in Stage B.
"""

from __future__ import annotations

from typing import Any

from ml.common.config import MLConfig, get_ml_config
from ml.common.types import BBox, FaceQuality
from ml.quality.blur import blur_score, laplacian_variance, sharpness_score
from ml.quality.visibility import (
    brightness_score,
    contrast_score,
    heuristic_mouth_visibility,
    resolution_score,
)


class FaceQualityEstimator:
    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or get_ml_config()

    def score(self, frame: Any, bbox: BBox, tracking_stability: float = 0.0) -> FaceQuality:
        face_width = bbox.width
        face_height = bbox.height

        gray = self._face_gray(frame, bbox)
        if gray is None:
            # No pixels available (e.g. bbox only) — score from geometry alone.
            res = resolution_score(face_width, self.config.gates.min_face_width)
            return FaceQuality(
                score=round(60 * res, 2),
                face_width=face_width,
                face_height=face_height,
                sharpness=0.0,
                blur=1.0,
                brightness=0.0,
                contrast=0.0,
                pose_score=0.6,
                mouth_visibility=heuristic_mouth_visibility(res, 0.0),
                eye_visibility=heuristic_mouth_visibility(res, 0.0),
                occlusion=0.2,
                tracking_stability=tracking_stability,
            )

        lap = laplacian_variance(gray)
        sharp = sharpness_score(lap)
        blur = blur_score(lap)
        bright = brightness_score(gray)
        contrast = contrast_score(gray)
        res = resolution_score(face_width, self.config.gates.min_face_width)

        # Pose is approximate without landmarks; refined in Stage B.
        pose = 0.7
        mouth_vis = heuristic_mouth_visibility(res, sharp)
        eye_vis = heuristic_mouth_visibility(res, sharp)
        occlusion = round(max(0.0, 1.0 - (0.5 * res + 0.5 * sharp)) * 0.5, 4)

        # Overall 0–100 quality: resolution + sharpness dominate, brightness &
        # contrast gate it, tracking stability contributes.
        composite = (
            0.32 * res
            + 0.30 * sharp
            + 0.15 * bright
            + 0.10 * contrast
            + 0.08 * pose
            + 0.05 * tracking_stability
        )
        score = round(100.0 * max(0.0, min(1.0, composite)), 2)

        return FaceQuality(
            score=score,
            face_width=face_width,
            face_height=face_height,
            sharpness=round(sharp, 4),
            blur=blur,
            brightness=round(bright, 4),
            contrast=round(contrast, 4),
            pose_score=pose,
            mouth_visibility=mouth_vis,
            eye_visibility=eye_vis,
            occlusion=occlusion,
            tracking_stability=round(tracking_stability, 4),
        )

    def _face_gray(self, frame: Any, bbox: BBox):
        if frame is None:
            return None
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore

            h, w = frame.shape[:2]
            x1 = max(0, int(bbox.x1))
            y1 = max(0, int(bbox.y1))
            x2 = min(w, int(bbox.x2))
            y2 = min(h, int(bbox.y2))
            if x2 <= x1 or y2 <= y1:
                return None
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                return None
            if crop.ndim == 3:
                return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            return np.asarray(crop)
        except Exception:
            return None


def get_quality_estimator(config: MLConfig | None = None) -> FaceQualityEstimator:
    return FaceQualityEstimator(config)
