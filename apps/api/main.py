"""SilentSpeak Lab FastAPI application (Milestone 1)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.config import get_settings
from apps.api.routes import evaluation, exports, health, media, people, videos
from apps.api.services.logging_setup import configure_logging, get_logger
from apps.api.services.video import VideoValidationError
from database.base import create_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    create_all()  # ensure tables exist (SQLite dev / first run)
    get_logger().info("SilentSpeak API started", extra={"stage": "startup"})
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="English silent-video lip reading + multi-person tracking + gaze + TTS.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(VideoValidationError)
    async def _validation_handler(request: Request, exc: VideoValidationError):
        return JSONResponse(status_code=400, content={"error": "validation_error", "detail": str(exc)})

    app.include_router(health.router)
    app.include_router(videos.router)
    app.include_router(people.router)
    app.include_router(exports.router)
    app.include_router(evaluation.router)
    app.include_router(media.router)
    return app


app = create_app()
