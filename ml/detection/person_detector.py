"""PersonDetector interface + adapters (§8, §9).

Detects ALL reasonably visible people (never only the largest/centre/highest
confidence one). Real back-end is a YOLO-family detector; when its dependency or
weights are missing the factory returns an adapter that reports MODEL_UNAVAILABLE
with the exact gap — it never fabricates detections.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ml.common.config import MLConfig, get_ml_config
from ml.common.device import resolve_device
from ml.common.results import Availability, ModelInfo, available, model_unavailable
from ml.common.types import PersonDetection


class PersonDetector(ABC):
    name = "person_detector"

    @abstractmethod
    def availability(self) -> Availability: ...

    @abstractmethod
    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0) -> list[PersonDetection]:
        """Return all person detections in ``frame`` (BGR ndarray)."""


class UnavailablePersonDetector(PersonDetector):
    """Reports exactly what is missing instead of guessing (§64, §93)."""

    def __init__(self, reason: str, missing: list[str]) -> None:
        self._reason = reason
        self._missing = missing

    def availability(self) -> Availability:
        return model_unavailable(self._reason, self._missing)

    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0) -> list[PersonDetection]:
        return []


class YoloPersonDetector(PersonDetector):
    """Ultralytics YOLO person detector (loaded lazily via the registry)."""

    def __init__(self, config: MLConfig) -> None:
        self.config = config
        self.device = resolve_device(config.device)
        self._model = None
        from ml.common.registry import REGISTRY

        weights = config.yolo_person_weights or "yolo11n.pt"
        self._model = REGISTRY.get(
            f"yolo_person::{weights}", lambda: self._build(weights)
        )

    def _build(self, weights: str):  # pragma: no cover - requires ultralytics
        import os

        # Prevent ultralytics from hitting the network (blocked api.github.com) or
        # auto-installing packages, which can corrupt the environment.
        os.environ.setdefault("YOLO_OFFLINE", "true")
        os.environ.setdefault("YOLO_AUTOINSTALL", "false")
        from ultralytics import YOLO  # type: ignore

        model = YOLO(weights)  # loads a local .pt directly, no download
        return model

    def availability(self) -> Availability:  # pragma: no cover - requires ultralytics
        return available(
            ModelInfo(
                name="yolo-person",
                version=getattr(self._model, "version", "ultralytics"),
                framework="ultralytics/torch",
                device=self.device,
                checkpoint=self.config.yolo_person_weights or "yolo11n.pt",
                license="AGPL-3.0",
                configuration={"img_size": self.config.yolo_img_size},
            )
        )

    def detect(self, frame: Any, frame_index: int = 0, timestamp: float = 0.0):  # pragma: no cover
        results = self._model.predict(
            frame, imgsz=self.config.yolo_img_size, classes=[0], verbose=False, device=self.device
        )
        out: list[PersonDetection] = []
        from ml.common.types import BBox

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                out.append(
                    PersonDetection(
                        bbox=BBox(x1, y1, x2, y2),
                        confidence=float(box.conf[0]),
                        frame_index=frame_index,
                        timestamp=timestamp,
                        class_id=0,
                        class_name="person",
                    )
                )
        return out


def _yolo_available() -> tuple[bool, list[str]]:
    missing: list[str] = []
    try:
        import ultralytics  # type: ignore  # noqa: F401
    except Exception:
        missing.append("ultralytics")
    try:
        import torch  # type: ignore  # noqa: F401
    except Exception:
        missing.append("torch")
    return (len(missing) == 0, missing)


def get_person_detector(config: MLConfig | None = None) -> PersonDetector:
    config = config or get_ml_config()

    if config.allow_mock:
        from ml.detection.adapters.mock_adapter import MockPersonDetector

        return MockPersonDetector()

    ok, missing = _yolo_available()
    if not ok:
        return UnavailablePersonDetector(
            reason=(
                "YOLO person detector unavailable. Install ML dependencies "
                f"({', '.join(missing)}) and provide weights. See docs/model-selection.md."
            ),
            missing=missing + (["yolo weights"] if not config.yolo_person_weights else []),
        )
    try:  # pragma: no cover - requires ultralytics
        return YoloPersonDetector(config)
    except Exception as exc:  # pragma: no cover
        return UnavailablePersonDetector(
            reason=f"Failed to initialise YOLO person detector: {exc}",
            missing=["yolo weights"],
        )
