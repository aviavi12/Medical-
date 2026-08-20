"""MouthExtractor (§21).

Builds a mouth ROI from mouth landmarks with padding, producing a temporally
tagged, standardized crop. The ROI follows the face (via landmarks), never a
fixed rectangle. Pure geometry; works with or without pixel data present.
"""

from __future__ import annotations

from typing import Any

from ml.common.types import BBox, FaceLandmarks, MouthCrop
from ml.mouth.normalization import normalize_crop


class MouthExtractor:
    def __init__(self, padding: float = 0.4, output_size: tuple[int, int] = (96, 96)) -> None:
        self.padding = padding
        self.output_size = output_size

    def mouth_bbox(self, landmarks: FaceLandmarks) -> BBox | None:
        pts = landmarks.region_points(landmarks.mouth or landmarks.lips)
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        w = x2 - x1
        h = y2 - y1
        pad_x = w * self.padding
        pad_y = h * self.padding
        return BBox(x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y)

    def extract(
        self, frame: Any, landmarks: FaceLandmarks, frame_index: int = 0, timestamp: float = 0.0,
        quality: float = 0.0,
    ) -> MouthCrop | None:
        bbox = self.mouth_bbox(landmarks)
        if bbox is None:
            return None

        data = None
        if frame is not None:
            data = self._crop(frame, bbox)

        return MouthCrop(
            frame_index=frame_index,
            timestamp=timestamp,
            bbox=bbox,
            image_shape=self.output_size,
            quality=quality,
            data=data,
        )

    def _crop(self, frame: Any, bbox: BBox):
        try:
            import cv2  # type: ignore

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
            resized = cv2.resize(crop, self.output_size, interpolation=cv2.INTER_AREA)
            return normalize_crop(resized)
        except Exception:
            return None
