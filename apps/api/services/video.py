"""Video validation + metadata extraction (§47, §61, §64).

Uploaded video is untrusted input: extension, MIME, size, and duration are all
validated, filenames are sanitised, and processing stays inside safe dirs.
Metadata is extracted with ffprobe (real). If ffprobe is missing, a clear error
is returned rather than fabricated metadata.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from apps.api.config import Settings


class VideoValidationError(ValueError):
    """Raised for any rejected upload; message is user-safe."""


class MetadataUnavailableError(RuntimeError):
    """ffprobe/ffmpeg not available — metadata cannot be extracted."""


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def sanitize_filename(name: str) -> str:
    """Strip directory components and unsafe characters (§61)."""
    base = Path(name).name  # drops any path traversal segments
    base = base.replace("\x00", "")
    base = _SAFE_NAME_RE.sub("_", base).strip("._-")
    return base or "video"


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def validate_upload(
    *,
    filename: str,
    size_bytes: int,
    content_type: str | None,
    settings: Settings,
) -> None:
    """Validate an upload before it is stored. Raises VideoValidationError."""
    ext = extension_of(filename)
    if ext not in settings.allowed_extensions:
        raise VideoValidationError(
            f"Unsupported video format '.{ext}'. Allowed: "
            f"{', '.join(sorted(settings.allowed_extensions))}."
        )

    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        # Some browsers send application/octet-stream; accept when extension is ok.
        if ct not in settings.allowed_mime and ct != "application/octet-stream":
            raise VideoValidationError(f"Unsupported MIME type '{ct}'.")

    if size_bytes <= 0:
        raise VideoValidationError("Uploaded file is empty.")
    if size_bytes > settings.max_upload_size_bytes:
        raise VideoValidationError(
            f"File exceeds the maximum upload size of {settings.max_upload_size_mb} MB."
        )


@dataclass
class VideoMetadata:
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    has_audio: bool = False
    size_bytes: int | None = None
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "codec": self.codec,
            "has_audio": self.has_audio,
            "size_bytes": self.size_bytes,
        }


def _parse_fps(rate: str | None) -> float | None:
    if not rate or rate in ("0/0", "0"):
        return None
    try:
        if "/" in rate:
            num, den = rate.split("/")
            den_f = float(den)
            return float(num) / den_f if den_f else None
        return float(rate)
    except (ValueError, ZeroDivisionError):
        return None


def probe_metadata(path: str | Path) -> VideoMetadata:
    """Extract real metadata via ffprobe. Raises MetadataUnavailableError if
    ffprobe is not installed (never fabricates values)."""
    path = Path(path)
    if not path.exists():
        raise VideoValidationError(f"File not found: {path.name}")
    if not ffprobe_available():
        raise MetadataUnavailableError(
            "ffprobe (FFmpeg) is not installed. Install FFmpeg to extract video metadata."
        )

    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
    except subprocess.CalledProcessError as exc:
        raise VideoValidationError(
            "Could not read the video. It may be corrupted or use an unsupported codec."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoValidationError("Timed out while reading the video metadata.") from exc

    data = json.loads(out.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise VideoValidationError("No video stream found in the uploaded file.")

    duration = None
    for src in (video_stream.get("duration"), fmt.get("duration")):
        try:
            if src is not None:
                duration = float(src)
                break
        except (TypeError, ValueError):
            continue

    fps = _parse_fps(video_stream.get("avg_frame_rate")) or _parse_fps(
        video_stream.get("r_frame_rate")
    )

    size_bytes = None
    try:
        size_bytes = int(fmt.get("size")) if fmt.get("size") else path.stat().st_size
    except (TypeError, ValueError):
        size_bytes = path.stat().st_size

    return VideoMetadata(
        duration=duration,
        width=video_stream.get("width"),
        height=video_stream.get("height"),
        fps=fps,
        codec=video_stream.get("codec_name"),
        has_audio=audio_stream is not None,
        size_bytes=size_bytes,
        raw=data,
    )


def validate_duration(metadata: VideoMetadata, settings: Settings) -> None:
    """Reject over-long videos (§64). Called after metadata is known."""
    if metadata.duration is not None and metadata.duration > settings.max_video_duration_seconds:
        raise VideoValidationError(
            f"Video exceeds the maximum duration of "
            f"{settings.max_video_duration_seconds} seconds."
        )
