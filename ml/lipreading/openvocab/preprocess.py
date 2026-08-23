"""Open-vocabulary VSR preprocessing (Phase 5).

The SyncVSR checkpoint was trained on **lower-face** crops (a face-centred box,
shifted down toward the mouth, resized to 96x96 grayscale, normalised) — NOT a
tight mouth-only crop. This module reproduces that and supports three
configurable modes so the correct one for the checkpoint is used:

- LOWER_FACE  (default, matches SyncVSR): face box shifted down 0.2*height.
- FULL_FACE   : whole face box, no shift.
- MOUTH_ONLY  : tighter lower-face crop.

Face detection uses MediaPipe (already a project dependency). A per-person ROI
restricts detection to the selected person for multi-person videos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

MEAN, STD = 0.421, 0.165  # SyncVSR grayscale normalisation
OUT = 96


class CropMode(str, Enum):
    LOWER_FACE = "lower_face"
    FULL_FACE = "full_face"
    MOUTH_ONLY = "mouth_only"


@dataclass
class _Params:
    scale: float      # crop side = scale * max(face_w, face_h)
    shift_down: float  # vertical shift as a fraction of face height


_MODE_PARAMS = {
    CropMode.LOWER_FACE: _Params(scale=1.0, shift_down=0.20),
    CropMode.FULL_FACE: _Params(scale=1.2, shift_down=0.0),
    CropMode.MOUTH_ONLY: _Params(scale=0.7, shift_down=0.35),
}


class PreprocessorUnavailable(RuntimeError):
    pass


class OpenVocabPreprocessor:
    def __init__(self, mode: CropMode | str = CropMode.LOWER_FACE, out_size: int = OUT,
                 min_conf: float = 0.5) -> None:
        self.mode = CropMode(mode)
        self.params = _MODE_PARAMS[self.mode]
        self.out_size = out_size
        self.min_conf = min_conf
        self._face = None

    def _detector(self):
        if self._face is None:
            try:
                import mediapipe as mp  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise PreprocessorUnavailable("mediapipe is required for face detection.") from exc
            self._face = mp.solutions.face_detection.FaceDetection(
                model_selection=1, min_detection_confidence=self.min_conf
            )
        return self._face

    def _face_box(self, frame_bgr, roi_bbox):
        import cv2  # type: ignore

        h, w = frame_bgr.shape[:2]
        res = self._detector().process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        if not res.detections:
            return None
        best = None
        best_key = None
        for d in res.detections:
            b = d.location_data.relative_bounding_box
            fw, fh = b.width * w, b.height * h
            cx = (b.xmin + b.width / 2) * w
            cy = (b.ymin + b.height / 2) * h
            if roi_bbox is not None:
                rx = (roi_bbox[0] + roi_bbox[2]) / 2.0
                ry = (roi_bbox[1] + roi_bbox[3]) / 2.0
                key = -((cx - rx) ** 2 + (cy - ry) ** 2)  # nearest to ROI
            else:
                key = fw * fh  # largest
            if best_key is None or key > best_key:
                best_key, best = key, (cx, cy, fw, fh)
        return best

    def crop_frame(self, frame_bgr, roi_bbox=None):
        """Return a 96x96 grayscale uint8 crop for the face, or None."""
        import cv2  # type: ignore

        box = self._face_box(frame_bgr, roi_bbox)
        if box is None:
            return None
        cx, cy, fw, fh = box
        cy += self.params.shift_down * fh
        half = self.params.scale * max(fw, fh) / 2.0
        h, w = frame_bgr.shape[:2]
        x1, y1 = int(cx - half), int(cy - half)
        x2, y2 = int(cx + half), int(cy + half)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, (self.out_size, self.out_size))

    def to_tensor(self, gray_crops: list):
        """Stack grayscale crops → normalised (T, 1, 96, 96) float tensor."""
        import numpy as np  # type: ignore
        import torch  # type: ignore

        arr = np.stack(gray_crops).astype("float32") / 255.0
        arr = (arr - MEAN) / STD
        return torch.from_numpy(arr).unsqueeze(1)

    def build_crops(self, frames: list[tuple[float, Any, list | None]]):
        """[(timestamp, bgr_frame, roi_bbox), ...] → (gray_crops, timestamps).

        Frames without a detected face are skipped (their timestamps dropped).
        """
        crops = []
        tss = []
        for ts, frame, roi in frames:
            c = self.crop_frame(frame, roi)
            if c is not None:
                crops.append(c)
                tss.append(ts)
        return crops, tss
