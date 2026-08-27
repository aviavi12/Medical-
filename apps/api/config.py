"""Application settings (pydantic-settings).

All values have safe defaults so the app boots with zero configuration. When
``DATABASE_URL`` is empty a local SQLite file is used (no external server).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("SILENTSPEAK_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "LipSight"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # Database — empty => SQLite fallback (see database_url_resolved)
    database_url: str = ""

    # Storage
    storage_backend: str = "local"
    storage_path: str = "./storage"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # Upload limits / validation
    max_video_duration_seconds: int = 300
    max_upload_size_mb: int = 2048
    allowed_video_extensions: str = "mp4,mov,webm,m4v"
    allowed_video_mime: str = "video/mp4,video/quicktime,video/webm,video/x-m4v"

    # Sampling
    coarse_fps: int = 8
    analysis_fps: int = 25

    # Device
    device: str = "auto"

    # Quality gates
    min_face_width: int = 80
    min_face_quality: float = 60
    min_mouth_visibility: float = 0.60
    min_tracking_stability: float = 0.60

    # Model selection
    person_detector: str = "yolo"
    face_detector: str = "mediapipe"
    tracker: str = "bytetrack"
    lip_reading_model: str = "syncvsr"
    tts_provider: str = "local"
    yolo_img_size: int = 1280

    # Safety
    allow_mock_inference: bool = False

    # Developer-only evaluation mode (§20–§22): exposes ground-truth WER/CER
    # scoring in the API/UI. Off in production; never shown to normal users.
    enable_evaluation_mode: bool = True

    # ── derived helpers ─────────────────────────────────────────────────────
    @property
    def database_url_resolved(self) -> str:
        if self.database_url:
            return self.database_url
        # SQLite fallback under the repo root.
        db_path = REPO_ROOT / "storage" / "silentspeak.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    @property
    def storage_root(self) -> Path:
        p = Path(self.storage_path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return p

    @property
    def allowed_extensions(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_video_extensions.split(",") if e.strip()}

    @property
    def allowed_mime(self) -> set[str]:
        return {m.strip().lower() for m in self.allowed_video_mime.split(",") if m.strip()}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
