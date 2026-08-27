"""All API DTOs. Kept in one module for a clear transport contract."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorOut(BaseModel):
    error: str
    detail: str | None = None


class DeviceInfo(BaseModel):
    preference: str
    device: str
    torch: bool = False
    torch_version: str | None = None
    cuda_device_name: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    env: str
    database: str
    ffmpeg: bool
    ffprobe: bool
    device: DeviceInfo
    time: str


class VideoMetadataOut(BaseModel):
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    has_audio: bool = False
    size_bytes: int | None = None


class VideoOut(BaseModel):
    id: str
    filename: str
    status: str
    project_id: str | None = None
    metadata: VideoMetadataOut
    media_url: str | None = None
    created_at: str
    updated_at: str


class VideoListOut(BaseModel):
    videos: list[VideoOut]
    total: int


class JobStatusOut(BaseModel):
    video_id: str
    job_id: str | None = None
    status: str
    stage: str | None = None
    progress: float = 0.0
    frames_total: int | None = None
    frames_done: int | None = None
    device: str | None = None
    elapsed_seconds: float | None = None
    eta_seconds: float | None = None
    error: str | None = None


class AvailabilityOut(BaseModel):
    state: str
    detail: str | None = None
    missing: list[str] = Field(default_factory=list)
    model: dict[str, Any] | None = None


class PersonQualityReportOut(BaseModel):
    """Full per-person quality report (§25)."""

    status: str = "INSUFFICIENT"            # READY / WARNING / INSUFFICIENT
    readiness_score: float = 0.0            # combined 0..100 (the gate signal)
    face_quality_score: float = 0.0         # 0..100
    lip_readiness_score: float = 0.0        # 0..100
    usable_duration: float = 0.0            # seconds
    visible_ratio: float = 0.0              # 0..1
    avg_face_width_px: float = 0.0
    avg_mouth_visibility_pct: float = 0.0
    avg_sharpness: float = 0.0
    avg_pose_quality: float = 0.0
    tracking_stability: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class PersonOut(BaseModel):
    id: str
    track_number: int
    label: str
    screen_time: float
    visibility: float
    face_quality: float
    lip_readiness: float
    average_detection_confidence: float
    first_timestamp: float | None = None
    last_timestamp: float | None = None
    thumbnail_url: str | None = None
    selectable: bool
    # Combined-score gate status (§10): READY / WARNING / INSUFFICIENT.
    status: str = "INSUFFICIENT"
    reason: str | None = None
    quality_report: PersonQualityReportOut | None = None


class PeopleListOut(BaseModel):
    video_id: str
    people: list[PersonOut]
    status: str


class TranscriptWordOut(BaseModel):
    word: str
    start: float
    end: float
    confidence: float


class TranscriptSegmentOut(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: float
    raw_text: str = ""
    processed_text: str = ""
    uncertain: bool = False
    words: list[TranscriptWordOut] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    # Per-segment display + provenance metadata (§15, §17, §19).
    visual_quality: float | None = None        # 0..100 avg face quality over the window
    speaking_activity: str | None = None       # SPEAKING_LIKELY / NOT_SPEAKING / UNCERTAIN
    frame_start: int | None = None             # source frame range
    frame_end: int | None = None
    window_index: int | None = None            # which model window produced this
    person_id: str | None = None


class TranscriptOut(BaseModel):
    video_id: str
    person_id: str
    availability: AvailabilityOut
    model_version: str | None = None
    segments: list[TranscriptSegmentOut] = Field(default_factory=list)


class GazeSegmentOut(BaseModel):
    start: float
    end: float
    direction: str
    confidence: float
    target_person_id: str | None = None
    target_confidence: float = 0.0


class GazeTimelineOut(BaseModel):
    video_id: str
    person_id: str
    availability: AvailabilityOut
    segments: list[GazeSegmentOut] = Field(default_factory=list)


class AnalyzePersonRequest(BaseModel):
    override_quality_gates: bool = False
    analysis_fps: int | None = None


class PersonAnalysisResultOut(BaseModel):
    video_id: str
    person_id: str
    state: str
    detail: str | None = None
    segments: int = 0
    gaze: int = 0
    landmarks_available: bool = False
    lipreading_available: bool = False
    processing_seconds: float | None = None  # measured wall-clock for Stage B (§11)
    device: str | None = None                # cpu / cuda / mps


class DebugCropFrameOut(BaseModel):
    """One debug sample: the crops the model actually sees (§12)."""

    timestamp: float
    original_url: str | None = None
    face_url: str | None = None
    lower_face_url: str | None = None
    mouth_url: str | None = None


class DebugCropsOut(BaseModel):
    video_id: str
    person_id: str
    available: bool = False
    note: str = ""
    crop_mode: str | None = None
    frames: list[DebugCropFrameOut] = Field(default_factory=list)
    sequence_url: str | None = None      # horizontal temporal strip of lower-face crops


class PersonEvalRequest(BaseModel):
    """Developer-only evaluation against a pasted ground-truth transcript (§20–§22)."""

    ground_truth: str
    use_processed: bool = True


class PersonEvalResultOut(BaseModel):
    video_id: str
    person_id: str
    enabled: bool = True
    prediction: str = ""
    reference: str = ""
    wer: float | None = None
    cer: float | None = None
    substitutions: int | None = None
    deletions: int | None = None
    insertions: int | None = None
    ref_words: int | None = None
    hyp_words: int | None = None
    sentence_accuracy: float | None = None   # exact-match after normalization (0 or 1 per sample)
    average_confidence: float | None = None  # mean model-likelihood proxy, NOT accuracy
    normalization: str = ""                  # exactly what was done to both strings before scoring
    note: str = ""


class TTSRequest(BaseModel):
    # Explicit safety confirmation is required for any non-generic voice (§43).
    use_processed_transcript: bool = True
    voice: str = "generic"
    authorized_voice_confirmation: bool = False


class TTSArtifactOut(BaseModel):
    id: str | None = None
    path: str | None = None
    url: str | None = None
    voice: str
    duration: float
    sample_rate: int
    label: str
    availability: AvailabilityOut


class ExportListOut(BaseModel):
    video_id: str
    person_id: str
    formats: list[str]
    urls: dict[str, str]


class EvaluationRequest(BaseModel):
    name: str = "evaluation"
    predictions: list[str]
    references: list[str]
    model_version: str | None = None


class EvaluationResultOut(BaseModel):
    id: str | None = None
    name: str
    wer: float
    cer: float
    sentence_accuracy: float
    n: int
    details: dict[str, Any] | None = None
