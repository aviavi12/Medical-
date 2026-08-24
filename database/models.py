"""SQLAlchemy models (§46–§53).

Authored for PostgreSQL; portable JSON/Float/String types keep them working on
the SQLite dev/test fallback. Every analysis result references the model version
used (§53, §99) for reproducibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Processing job states (§55) ─────────────────────────────────────────────
JOB_STATES = [
    "QUEUED",
    "UPLOADING",
    "VALIDATING",
    "EXTRACTING_METADATA",
    "DETECTING_PEOPLE",
    "DETECTING_FACES",
    "TRACKING",
    "QUALITY_ANALYSIS",
    "READY_FOR_SELECTION",
    "ANALYZING_PERSON",
    "EXTRACTING_MOUTH",
    "LIP_READING",
    "GAZE_ANALYSIS",
    "FINALIZING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
]


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), default="Untitled project")
    # Clean user relationship so auth can be added later (§63) without coupling.
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    videos: Mapped[list["Video"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(String(1024))
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship(back_populates="videos")
    jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    person_tracks: Mapped[list["PersonTrack"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"))
    kind: Mapped[str] = mapped_column(String(64), default="coarse_scan")
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    frames_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frames_done: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    video: Mapped["Video"] = relationship(back_populates="jobs")


class PersonTrack(Base):
    __tablename__ = "person_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"))
    track_number: Mapped[int] = mapped_column(Integer)
    first_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    screen_time: Mapped[float] = mapped_column(Float, default=0.0)
    visible_frame_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    average_detection_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    average_face_quality: Mapped[float] = mapped_column(Float, default=0.0)
    lip_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    # Per-person quality report aggregates (§25) — persisted at coarse-scan time.
    readiness_status: Mapped[str] = mapped_column(String(16), default="INSUFFICIENT")
    usable_duration: Mapped[float] = mapped_column(Float, default=0.0)
    avg_face_width: Mapped[float] = mapped_column(Float, default=0.0)
    avg_mouth_visibility: Mapped[float] = mapped_column(Float, default=0.0)
    avg_sharpness: Mapped[float] = mapped_column(Float, default=0.0)
    avg_pose_quality: Mapped[float] = mapped_column(Float, default=0.0)
    tracking_stability: Mapped[float] = mapped_column(Float, default=0.0)
    quality_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    video: Mapped["Video"] = relationship(back_populates="person_tracks")
    face_observations: Mapped[list["FaceObservation"]] = relationship(
        back_populates="person_track", cascade="all, delete-orphan"
    )
    segments: Mapped[list["LipReadingSegment"]] = relationship(
        back_populates="person_track", cascade="all, delete-orphan"
    )
    gaze_observations: Mapped[list["GazeObservation"]] = relationship(
        back_populates="person_track", cascade="all, delete-orphan"
    )


class FaceObservation(Base):
    __tablename__ = "face_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_track_id: Mapped[str] = mapped_column(ForeignKey("person_tracks.id"))
    timestamp: Mapped[float] = mapped_column(Float)
    frame_index: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[float] = mapped_column(Float, default=0.0)
    height: Mapped[float] = mapped_column(Float, default=0.0)
    blur_score: Mapped[float] = mapped_column(Float, default=0.0)
    brightness_score: Mapped[float] = mapped_column(Float, default=0.0)
    pose_score: Mapped[float] = mapped_column(Float, default=0.0)
    mouth_visibility: Mapped[float] = mapped_column(Float, default=0.0)
    eye_visibility: Mapped[float] = mapped_column(Float, default=0.0)
    occlusion_score: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)

    person_track: Mapped["PersonTrack"] = relationship(back_populates="face_observations")


class MouthObservation(Base):
    __tablename__ = "mouth_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_track_id: Mapped[str] = mapped_column(ForeignKey("person_tracks.id"))
    timestamp: Mapped[float] = mapped_column(Float)
    frame_index: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list] = mapped_column(JSON)
    crop_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    quality: Mapped[float] = mapped_column(Float, default=0.0)


class LipReadingSegment(Base):
    __tablename__ = "lip_reading_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_track_id: Mapped[str] = mapped_column(ForeignKey("person_tracks.id"))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    model_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    processed_text: Mapped[str] = mapped_column(Text, default="")
    alternatives: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Per-segment provenance + display metadata (§15, §17, §19).
    visual_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaking_activity: Mapped[str | None] = mapped_column(String(24), nullable=True)
    frame_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    person_track: Mapped["PersonTrack"] = relationship(back_populates="segments")
    words: Mapped[list["LipReadingWordRow"]] = relationship(
        back_populates="segment", cascade="all, delete-orphan"
    )


class LipReadingWordRow(Base):
    __tablename__ = "lip_reading_words"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    segment_id: Mapped[str] = mapped_column(ForeignKey("lip_reading_segments.id"))
    word: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    segment: Mapped["LipReadingSegment"] = relationship(back_populates="words")


class GazeObservation(Base):
    __tablename__ = "gaze_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_track_id: Mapped[str] = mapped_column(ForeignKey("person_tracks.id"))
    timestamp: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    yaw: Mapped[float | None] = mapped_column(Float, nullable=True)
    pitch: Mapped[float | None] = mapped_column(Float, nullable=True)
    roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    target_person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    person_track: Mapped["PersonTrack"] = relationship(back_populates="gaze_observations")


class TTSArtifact(Base):
    __tablename__ = "tts_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_track_id: Mapped[str] = mapped_column(ForeignKey("person_tracks.id"))
    path: Mapped[str] = mapped_column(String(1024))
    voice: Mapped[str] = mapped_column(String(128), default="generic")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    sample_rate: Mapped[int] = mapped_column(Integer, default=22050)
    label: Mapped[str] = mapped_column(String(255), default="Synthetic audio generated from visual transcript.")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    model_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(64), default="0.0.0")
    checkpoint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    framework: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device: Mapped[str | None] = mapped_column(String(32), nullable=True)
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), default="evaluation")
    wer: Mapped[float | None] = mapped_column(Float, nullable=True)
    cer: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentence_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
