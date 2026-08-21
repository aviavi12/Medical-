"""Lightweight, framework-free config for the ML layer.

Reads the same environment variables as the API settings, but has no dependency
on pydantic/FastAPI so ml/ stays importable on its own (for training, scripts,
and unit tests).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _models_dir() -> Path:
    raw = os.environ.get("MODELS_DIR", "./models")
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _s(name: str, default: str) -> str:
    return os.environ.get(name, default) or default


@dataclass
class ReadinessWeights:
    """Lip-reading readiness score weights (§15). Configurable, single source."""

    face_quality: float = field(default_factory=lambda: _f("READINESS_W_FACE_QUALITY", 0.25))
    mouth_visibility: float = field(default_factory=lambda: _f("READINESS_W_MOUTH_VISIBILITY", 0.20))
    face_resolution: float = field(default_factory=lambda: _f("READINESS_W_FACE_RESOLUTION", 0.20))
    tracking_stability: float = field(default_factory=lambda: _f("READINESS_W_TRACKING_STABILITY", 0.15))
    pose_quality: float = field(default_factory=lambda: _f("READINESS_W_POSE_QUALITY", 0.10))
    sharpness: float = field(default_factory=lambda: _f("READINESS_W_SHARPNESS", 0.10))

    def total(self) -> float:
        return (
            self.face_quality
            + self.mouth_visibility
            + self.face_resolution
            + self.tracking_stability
            + self.pose_quality
            + self.sharpness
        )

    def normalized(self) -> "ReadinessWeights":
        t = self.total()
        if t <= 0:
            return ReadinessWeights(1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6)
        return ReadinessWeights(
            self.face_quality / t,
            self.mouth_visibility / t,
            self.face_resolution / t,
            self.tracking_stability / t,
            self.pose_quality / t,
            self.sharpness / t,
        )


@dataclass
class QualityGates:
    """Thresholds that must be met before expensive lip reading runs (§65)."""

    min_face_width: int = field(default_factory=lambda: _i("MIN_FACE_WIDTH", 80))
    min_face_quality: float = field(default_factory=lambda: _f("MIN_FACE_QUALITY", 60))
    min_mouth_visibility: float = field(default_factory=lambda: _f("MIN_MOUTH_VISIBILITY", 0.60))
    min_tracking_stability: float = field(default_factory=lambda: _f("MIN_TRACKING_STABILITY", 0.60))


@dataclass
class MLConfig:
    device: str = field(default_factory=lambda: _s("DEVICE", "auto"))
    person_detector: str = field(default_factory=lambda: _s("PERSON_DETECTOR", "yolo"))
    face_detector: str = field(default_factory=lambda: _s("FACE_DETECTOR", "mediapipe"))
    tracker: str = field(default_factory=lambda: _s("TRACKER", "bytetrack"))
    lip_reading_model: str = field(default_factory=lambda: _s("LIP_READING_MODEL", "lipnet"))
    tts_provider: str = field(default_factory=lambda: _s("TTS_PROVIDER", "local"))
    yolo_img_size: int = field(default_factory=lambda: _i("YOLO_IMG_SIZE", 1280))
    models_dir: str = field(default_factory=lambda: str(_models_dir()))
    yolo_person_weights: str = field(default_factory=lambda: _s("YOLO_PERSON_WEIGHTS", ""))
    lip_reading_weights: str = field(default_factory=lambda: _s("LIP_READING_WEIGHTS", ""))
    dlib_landmarks: str = field(default_factory=lambda: _s("DLIB_LANDMARKS", ""))
    coarse_fps: int = field(default_factory=lambda: _i("COARSE_FPS", 8))
    analysis_fps: int = field(default_factory=lambda: _i("ANALYSIS_FPS", 25))
    allow_mock: bool = field(default_factory=lambda: _s("ALLOW_MOCK_INFERENCE", "0") in ("1", "true", "True"))
    gates: QualityGates = field(default_factory=QualityGates)
    weights: ReadinessWeights = field(default_factory=ReadinessWeights)

    def __post_init__(self) -> None:
        # Derive default artifact paths from models_dir when env vars are unset,
        # falling back to the file if it exists on disk.
        md = Path(self.models_dir)
        if not self.lip_reading_weights:
            cand = md / "lipnet_overlap.pt"
            self.lip_reading_weights = str(cand) if cand.exists() else ""
        if not self.dlib_landmarks:
            cand = md / "shape_predictor_68_face_landmarks.dat"
            self.dlib_landmarks = str(cand) if cand.exists() else ""
        if not self.yolo_person_weights:
            # Prefer a locally-downloaded weight (offline, deterministic). yolov8n
            # is compatible with the pinned ultralytics; yolo11n needs ultralytics>=8.3.
            for cand in (md / "yolov8n.pt", md / "yolo11n.pt"):
                if cand.exists():
                    self.yolo_person_weights = str(cand)
                    break
            else:
                self.yolo_person_weights = "yolov8n.pt"


def get_ml_config() -> MLConfig:
    """Fresh config read from the current environment (not cached, so tests can
    tweak env vars between calls)."""
    return MLConfig()
