"""Frame sampling subsystem (§18).

Preserves original video timestamps. The *sampled* frame index is never
confused with the source frame index or the wall-clock timestamp — all three
travel together on every emitted frame.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


class FrameSamplingError(RuntimeError):
    pass


@dataclass
class SampledFrame:
    sample_index: int          # 0,1,2,... within the sampled sequence
    source_frame_index: int    # index within the original video
    timestamp_seconds: float   # true position in the source video
    source_video_id: str | None = None
    image: Optional[Any] = None  # np.ndarray (BGR) when decoded


def _require_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except Exception as exc:  # pragma: no cover
        raise FrameSamplingError(
            "OpenCV (cv2) is required for frame sampling. Install opencv-python-headless."
        ) from exc


class FrameSampler:
    """Yields frames from a video at a target FPS, keeping true timestamps."""

    def __init__(self, target_fps: float = 8.0) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be > 0")
        self.target_fps = float(target_fps)

    def iter_frames(
        self, path: str | Path, source_video_id: str | None = None, decode: bool = True
    ) -> Iterator[SampledFrame]:
        cv2 = _require_cv2()
        path = str(path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise FrameSamplingError(f"Could not open video: {Path(path).name}")
        try:
            native_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            if native_fps <= 0:
                native_fps = 30.0  # conservative default when unavailable
            # Sample every Nth source frame to approximate target_fps.
            step = max(1, round(native_fps / self.target_fps))

            source_idx = 0
            sample_idx = 0
            while True:
                grabbed = cap.grab()
                if not grabbed:
                    break
                if source_idx % step == 0:
                    image = None
                    if decode:
                        ok, frame = cap.retrieve()
                        if not ok:
                            break
                        image = frame
                    yield SampledFrame(
                        sample_index=sample_idx,
                        source_frame_index=source_idx,
                        timestamp_seconds=source_idx / native_fps,
                        source_video_id=source_video_id,
                        image=image,
                    )
                    sample_idx += 1
                source_idx += 1
        finally:
            cap.release()

    def frame_at(self, path: str | Path, timestamp_seconds: float):
        """Decode a single frame near ``timestamp_seconds`` (for thumbnails)."""
        cv2 = _require_cv2()
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise FrameSamplingError(f"Could not open video: {Path(path).name}")
        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_seconds) * 1000.0)
            ok, frame = cap.read()
            if not ok:
                return None
            return frame
        finally:
            cap.release()
