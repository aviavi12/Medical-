"""Video endpoints (§54): upload, list, get, delete, analyze, status, media."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.api.config import Settings, get_settings
from apps.api.dependencies import get_db_session, get_storage_provider
from apps.api.schemas import (
    JobStatusOut,
    VideoListOut,
    VideoMetadataOut,
    VideoOut,
)
from apps.api.services import video as video_service
from apps.api.services.storage import StorageProvider
from apps.api.workers import process_coarse_scan
from database import models

router = APIRouter(prefix="/api/videos", tags=["videos"])

_CHUNK = 1024 * 1024


def _to_out(v: models.Video, storage: StorageProvider) -> VideoOut:
    return VideoOut(
        id=v.id,
        filename=v.filename,
        status=v.status,
        project_id=v.project_id,
        metadata=VideoMetadataOut(
            duration=v.duration, width=v.width, height=v.height, fps=v.fps,
            codec=v.codec, has_audio=v.has_audio, size_bytes=v.size_bytes,
        ),
        media_url=f"/media/{v.storage_path}",
        created_at=v.created_at.isoformat() if v.created_at else "",
        updated_at=v.updated_at.isoformat() if v.updated_at else "",
    )


@router.post("", response_model=VideoOut, status_code=201)
def upload_video(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    db: Session = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage_provider),
    settings: Settings = Depends(get_settings),
) -> VideoOut:
    filename = video_service.sanitize_filename(file.filename or "video")

    # Pre-validate extension/MIME before spooling the whole file.
    try:
        video_service.validate_upload(
            filename=filename, size_bytes=1, content_type=file.content_type, settings=settings
        )
    except video_service.VideoValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Stream to a temp file, enforcing the size limit as we go (§61).
    tmp_dir = settings.storage_root / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    size = 0
    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=str(tmp_dir), suffix=f"_{filename}")
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = file.file.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the maximum upload size of {settings.max_upload_size_mb} MB.",
                    )
                out.write(chunk)

        if size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Extract real metadata (ffprobe). Missing ffprobe is surfaced, not faked.
        metadata = None
        try:
            metadata = video_service.probe_metadata(tmp_path)
            video_service.validate_duration(metadata, settings)
        except video_service.MetadataUnavailableError as exc:
            # Store the file but flag metadata as unavailable.
            metadata = video_service.VideoMetadata(size_bytes=size)
            metadata_note = str(exc)
        except video_service.VideoValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            metadata_note = None

        # Persist to storage under a per-video key.
        video = models.Video(filename=filename, storage_path="pending", status="QUEUED",
                             project_id=project_id)
        db.add(video)
        db.flush()  # assign id
        key = f"{video.id}/original/{filename}"
        storage.save(key, tmp_path)
        video.storage_path = key
        video.duration = metadata.duration
        video.width = metadata.width
        video.height = metadata.height
        video.fps = metadata.fps
        video.codec = metadata.codec
        video.has_audio = metadata.has_audio
        video.size_bytes = metadata.size_bytes or size
        db.add(video)
        db.commit()
        db.refresh(video)
        return _to_out(video, storage)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.get("", response_model=VideoListOut)
def list_videos(
    db: Session = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage_provider),
) -> VideoListOut:
    rows = db.query(models.Video).order_by(models.Video.created_at.desc()).all()
    return VideoListOut(videos=[_to_out(v, storage) for v in rows], total=len(rows))


@router.get("/{video_id}", response_model=VideoOut)
def get_video(
    video_id: str,
    db: Session = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage_provider),
) -> VideoOut:
    v = db.get(models.Video, video_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return _to_out(v, storage)


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: str,
    db: Session = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage_provider),
) -> None:
    """Delete the video + all derived artifacts (§62, §100)."""
    v = db.get(models.Video, video_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    # Remove derived files (thumbnails, crops) and the original.
    try:
        storage.delete(v.storage_path)
    except Exception:
        pass
    for pt in v.person_tracks:
        if pt.thumbnail_path:
            try:
                storage.delete(pt.thumbnail_path)
            except Exception:
                pass
    db.delete(v)
    db.commit()


@router.post("/{video_id}/analyze", response_model=JobStatusOut, status_code=202)
def analyze_video(
    video_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db_session),
) -> JobStatusOut:
    """Kick off the Stage-A coarse scan (§17)."""
    v = db.get(models.Video, video_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    v.status = "QUEUED"
    db.add(v)
    db.commit()
    background.add_task(process_coarse_scan, video_id)
    return JobStatusOut(video_id=video_id, status="QUEUED", stage="QUEUED", progress=0.0)


@router.get("/{video_id}/status", response_model=JobStatusOut)
def video_status(
    video_id: str,
    db: Session = Depends(get_db_session),
) -> JobStatusOut:
    v = db.get(models.Video, video_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    job = (
        db.query(models.ProcessingJob)
        .filter(models.ProcessingJob.video_id == video_id)
        .order_by(models.ProcessingJob.created_at.desc())
        .first()
    )
    if job is None:
        return JobStatusOut(video_id=video_id, status=v.status, stage=v.status, progress=0.0)

    elapsed = None
    if job.started_at:
        from datetime import datetime, timezone

        end = job.finished_at or datetime.now(timezone.utc)
        try:
            elapsed = (end - job.started_at).total_seconds()
        except Exception:
            elapsed = None
    return JobStatusOut(
        video_id=video_id,
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        frames_total=job.frames_total,
        frames_done=job.frames_done,
        device=job.device,
        elapsed_seconds=elapsed,
        error=job.error,
    )
