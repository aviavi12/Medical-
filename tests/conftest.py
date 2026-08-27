"""Test configuration.

Sets up an isolated temp SQLite DB + temp storage and enables the mock ML
adapters BEFORE the app is imported, so the full pipeline runs in CI without
GPUs or model weights. Real video fixtures are generated with FFmpeg.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# ── Must run before any app/ml import: point config at temp resources ────────
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="lipsight_test_"))
_DB_PATH = _TMP_ROOT / "test.sqlite"
_STORAGE = _TMP_ROOT / "storage"
_STORAGE.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["STORAGE_PATH"] = str(_STORAGE)
os.environ["ALLOW_MOCK_INFERENCE"] = "1"
os.environ["MAX_VIDEO_DURATION_SECONDS"] = "300"
os.environ["COARSE_FPS"] = "8"


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _make_video(path: Path, with_audio: bool, size: str = "1280x720", duration: int = 2) -> bool:
    ff = _ffmpeg()
    if ff is None:
        return False
    cmd = [ff, "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=25:duration={duration}"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    cmd += ["-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-shortest"]
    cmd += [str(path)]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        return path.exists()
    except Exception:
        return False


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    return _TMP_ROOT


@pytest.fixture(scope="session")
def sample_video() -> Path:
    """A real 720p video with no audio (silent-video use case)."""
    path = _TMP_ROOT / "clear_720p.mp4"
    if not path.exists() and not _make_video(path, with_audio=False):
        pytest.skip("ffmpeg not available to generate fixture video")
    return path


@pytest.fixture(scope="session")
def sample_video_with_audio() -> Path:
    path = _TMP_ROOT / "clear_audio.mp4"
    if not path.exists() and not _make_video(path, with_audio=True):
        pytest.skip("ffmpeg not available to generate fixture video")
    return path


@pytest.fixture(scope="session")
def corrupted_video() -> Path:
    path = _TMP_ROOT / "corrupted.mp4"
    path.write_bytes(b"not a real video file" * 100)
    return path


@pytest.fixture()
def client():
    """A TestClient with fresh settings/engine bound to the temp DB."""
    from apps.api.config import get_settings
    from database.base import reset_engine_for_tests

    get_settings.cache_clear()
    reset_engine_for_tests()

    from fastapi.testclient import TestClient

    from apps.api.main import app

    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
