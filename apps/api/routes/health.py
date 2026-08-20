"""Health + system info endpoints (§94 M1)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from apps.api.config import get_settings
from apps.api.schemas import DeviceInfo, HealthResponse
from apps.api.services.video import ffmpeg_available, ffprobe_available
from ml.common.device import device_report

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    dev = device_report(settings.device)
    db_url = settings.database_url_resolved
    db_kind = "postgresql" if db_url.startswith("postgres") else ("sqlite" if db_url.startswith("sqlite") else "other")
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        database=db_kind,
        ffmpeg=ffmpeg_available(),
        ffprobe=ffprobe_available(),
        device=DeviceInfo(**dev),
        time=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/")
def root() -> dict:
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
