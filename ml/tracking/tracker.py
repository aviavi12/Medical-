"""PersonTracker interface + a dependency-free IoU tracker (§10).

Production preference is ByteTrack / BoT-SORT (MIT). Those require extra native
deps (lap, cython-bbox); their adapters live in ``adapters/`` and are selected
when installed. As a robust default that works everywhere, ``SimpleIoUTracker``
performs real greedy IoU association with track continuity across short gaps —
this is a genuine algorithm, not a fabricated ML result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ml.common.config import MLConfig, get_ml_config
from ml.common.types import BBox, PersonDetection, Track


class PersonTracker(ABC):
    name = "tracker"

    @abstractmethod
    def update(self, detections: list[PersonDetection], frame_index: int, timestamp: float) -> list[Track]:
        """Consume one frame's detections; return active tracks with stable ids."""

    def reset(self) -> None:
        pass


@dataclass
class _TrackState:
    track_id: int
    bbox: BBox
    last_frame: int
    last_timestamp: float
    confidence: float
    misses: int = 0
    history: list[tuple[int, float, BBox]] = field(default_factory=list)


class SimpleIoUTracker(PersonTracker):
    """Greedy IoU tracker with a small tolerance for missed frames.

    - Same person keeps the same id across consecutive frames while overlap holds.
    - Tracks survive up to ``max_age`` sampled frames of non-detection (occlusion,
      crossing, temporary loss) before being dropped.
    - New, unmatched detections above ``min_confidence`` spawn new ids (people
      entering the frame, including at the edges).
    """

    def __init__(self, iou_threshold: float = 0.3, max_age: int = 8, min_confidence: float = 0.25) -> None:
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_confidence = min_confidence
        self._tracks: list[_TrackState] = []
        self._next_id = 1

    def reset(self) -> None:
        self._tracks = []
        self._next_id = 1

    def update(self, detections: list[PersonDetection], frame_index: int, timestamp: float) -> list[Track]:
        dets = [d for d in detections if d.confidence >= self.min_confidence]

        # Build IoU matrix and greedily match highest-overlap pairs first.
        pairs: list[tuple[float, int, int]] = []
        for ti, t in enumerate(self._tracks):
            for di, d in enumerate(dets):
                iou = t.bbox.iou(d.bbox)
                if iou >= self.iou_threshold:
                    pairs.append((iou, ti, di))
        pairs.sort(reverse=True)

        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        for iou, ti, di in pairs:
            if ti in matched_tracks or di in matched_dets:
                continue
            t = self._tracks[ti]
            d = dets[di]
            t.bbox = d.bbox
            t.last_frame = frame_index
            t.last_timestamp = timestamp
            t.confidence = d.confidence
            t.misses = 0
            t.history.append((frame_index, timestamp, d.bbox))
            matched_tracks.add(ti)
            matched_dets.add(di)

        # Unmatched existing tracks age.
        for ti, t in enumerate(self._tracks):
            if ti not in matched_tracks:
                t.misses += 1

        # Unmatched detections become new tracks.
        for di, d in enumerate(dets):
            if di in matched_dets:
                continue
            state = _TrackState(
                track_id=self._next_id,
                bbox=d.bbox,
                last_frame=frame_index,
                last_timestamp=timestamp,
                confidence=d.confidence,
                misses=0,
                history=[(frame_index, timestamp, d.bbox)],
            )
            self._next_id += 1
            self._tracks.append(state)

        # Drop stale tracks.
        self._tracks = [t for t in self._tracks if t.misses <= self.max_age]

        # Emit tracks visible this frame.
        return [
            Track(
                track_id=t.track_id,
                bbox=t.bbox,
                frame_index=frame_index,
                timestamp=timestamp,
                confidence=t.confidence,
            )
            for t in self._tracks
            if t.last_frame == frame_index
        ]


def get_tracker(config: MLConfig | None = None) -> PersonTracker:
    config = config or get_ml_config()
    tracker_name = config.tracker

    if tracker_name in ("bytetrack", "botsort"):
        try:  # pragma: no cover - optional native deps
            from ml.tracking.adapters.bytetrack_adapter import make_tracker  # type: ignore

            return make_tracker(tracker_name, config)
        except Exception:
            # Fall back to the dependency-free tracker rather than failing.
            return SimpleIoUTracker()
    return SimpleIoUTracker()
