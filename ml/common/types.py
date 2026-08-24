"""Typed data structures shared across ML subsystems.

Plain dataclasses (not Pydantic) so the ML layer has no web-framework
dependency. API schemas in ``apps/api/schemas`` mirror these for transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ml.common.results import Availability


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def iou(self, other: "BBox") -> float:
        ix1, iy1 = max(self.x1, other.x1), max(self.y1, other.y1)
        ix2, iy2 = min(self.x2, other.x2), min(self.y2, other.y2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        inter = iw * ih
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def contains_fraction(self, other: "BBox") -> float:
        """Fraction of ``other``'s area contained within ``self``."""
        ix1, iy1 = max(self.x1, other.x1), max(self.y1, other.y1)
        ix2, iy2 = min(self.x2, other.x2), min(self.y2, other.y2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        return inter / other.area if other.area > 0 else 0.0

    def as_list(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]

    @classmethod
    def from_list(cls, v: list[float]) -> "BBox":
        return cls(v[0], v[1], v[2], v[3])


@dataclass
class PersonDetection:
    bbox: BBox
    confidence: float
    frame_index: int
    timestamp: float
    class_id: int = 0
    class_name: str = "person"

    def as_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox.as_list(),
            "confidence": self.confidence,
            "class": self.class_name,
            "class_id": self.class_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
        }


@dataclass
class FaceDetection:
    bbox: BBox
    confidence: float
    frame_index: int
    timestamp: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox.as_list(),
            "confidence": self.confidence,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
        }


@dataclass
class Track:
    """A tracked object (person) with a stable id across frames."""

    track_id: int
    bbox: BBox
    frame_index: int
    timestamp: float
    confidence: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "bbox": self.bbox.as_list(),
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }


@dataclass
class FaceQuality:
    """Per-face quality metrics; ``score`` is 0–100 (§14)."""

    score: float
    face_width: float
    face_height: float
    sharpness: float
    blur: float
    brightness: float
    contrast: float
    pose_score: float
    mouth_visibility: float
    eye_visibility: float
    occlusion: float
    tracking_stability: float = 0.0

    @property
    def label(self) -> str:
        s = self.score
        if s >= 90:
            return "Excellent"
        if s >= 75:
            return "Good"
        if s >= 60:
            return "Usable"
        if s >= 40:
            return "Poor"
        return "Insufficient"

    def as_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d["label"] = self.label
        return d


@dataclass
class FaceLandmarks:
    """Normalized facial landmarks plus named regions."""

    points: list[tuple[float, float]]
    mouth: list[int] = field(default_factory=list)
    lips: list[int] = field(default_factory=list)
    jaw: list[int] = field(default_factory=list)
    left_eye: list[int] = field(default_factory=list)
    right_eye: list[int] = field(default_factory=list)
    left_iris: list[int] = field(default_factory=list)
    right_iris: list[int] = field(default_factory=list)
    image_size: tuple[int, int] = (0, 0)

    def region_points(self, indices: list[int]) -> list[tuple[float, float]]:
        return [self.points[i] for i in indices if 0 <= i < len(self.points)]


@dataclass
class MouthCrop:
    """A normalized, temporally-tagged mouth ROI."""

    frame_index: int
    timestamp: float
    bbox: BBox
    image_shape: tuple[int, int]
    quality: float = 0.0
    data: Optional[Any] = None  # np.ndarray when a real frame is present

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "bbox": self.bbox.as_list(),
            "image_shape": list(self.image_shape),
            "quality": self.quality,
        }


@dataclass
class LipReadingWord:
    word: str
    start: float
    end: float
    confidence: float


@dataclass
class LipReadingSegment:
    start_time: float
    end_time: float
    text: str
    confidence: float
    raw_text: str = ""
    processed_text: str = ""
    words: list[LipReadingWord] = field(default_factory=list)
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    # Provenance + display metadata (§15, §17, §19).
    visual_quality: float | None = None       # 0..100 avg face quality over window
    speaking_activity: str | None = None      # SPEAKING_LIKELY / NOT_SPEAKING / UNCERTAIN
    frame_start: int | None = None            # source frame range (inclusive)
    frame_end: int | None = None
    window_index: int | None = None           # which model window produced this

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "confidence": self.confidence,
            "raw_text": self.raw_text,
            "processed_text": self.processed_text,
            "words": [w.__dict__ for w in self.words],
            "alternatives": [{"text": t, "confidence": c} for t, c in self.alternatives],
            "visual_quality": self.visual_quality,
            "speaking_activity": self.speaking_activity,
            "frame_start": self.frame_start,
            "frame_end": self.frame_end,
            "window_index": self.window_index,
        }


@dataclass
class LipReadingResult:
    """Output of the lip-reading model, always carrying its honesty state."""

    availability: Availability
    segments: list[LipReadingSegment] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability.as_dict(),
            "segments": [s.as_dict() for s in self.segments],
        }


@dataclass
class HeadPose:
    yaw: float
    pitch: float
    roll: float
    confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class GazeDirection(str, Enum):
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class GazeResult:
    timestamp: float
    direction: GazeDirection
    confidence: float
    head_pose: Optional[HeadPose] = None
    target_person_id: Optional[int] = None
    target_confidence: float = 0.0
    availability: Optional[Availability] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "head_pose": self.head_pose.as_dict() if self.head_pose else None,
            "target_person_id": self.target_person_id,
            "target_confidence": self.target_confidence,
            "availability": self.availability.as_dict() if self.availability else None,
        }


@dataclass
class AudioArtifact:
    """A generated synthetic-speech artifact (§43, §44)."""

    path: str
    duration: float
    sample_rate: int
    voice: str
    label: str = "Synthetic audio generated from visual transcript."
    availability: Optional[Availability] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "voice": self.voice,
            "label": self.label,
            "availability": self.availability.as_dict() if self.availability else None,
        }
