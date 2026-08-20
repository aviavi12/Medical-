"""Person endpoints (§54): gallery, detail, analyze, transcript, gaze, tts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.config import Settings, get_settings
from apps.api.dependencies import get_db_session, get_storage_provider
from apps.api.schemas import (
    AnalyzePersonRequest,
    AvailabilityOut,
    GazeSegmentOut,
    GazeTimelineOut,
    PeopleListOut,
    PersonAnalysisResultOut,
    PersonOut,
    TranscriptOut,
    TranscriptSegmentOut,
    TTSArtifactOut,
    TTSRequest,
)
from apps.api.services.storage import StorageProvider
from apps.api.workers import process_person_analysis
from database import models
from ml.common.config import get_ml_config
from ml.common.results import Availability, AvailabilityState
from ml.landmarks import get_landmarker
from ml.lipreading import get_lip_reading_model
from ml.lipreading.postprocessing import UNCERTAIN
from ml.tts import get_tts_provider
from ml.tts.base import VoicePermissionError

router = APIRouter(prefix="/api/videos/{video_id}/people", tags=["people"])


def _availability_out(av: Availability) -> AvailabilityOut:
    return AvailabilityOut(state=av.state.value, detail=av.detail, missing=av.missing,
                           model=av.model.as_dict() if av.model else None)


def _person_out(pt: models.PersonTrack, settings: Settings) -> PersonOut:
    selectable = (
        pt.average_face_quality >= settings.min_face_quality
        and pt.lip_readiness_score >= 40.0
    )
    reason = None
    if not selectable:
        reason = "Insufficient visual quality for reliable lip reading."
    return PersonOut(
        id=pt.id,
        track_number=pt.track_number,
        label=f"Person {pt.track_number:02d}",
        screen_time=pt.screen_time,
        visibility=round(pt.visible_frame_ratio * 100, 1),
        face_quality=pt.average_face_quality,
        lip_readiness=pt.lip_readiness_score,
        average_detection_confidence=pt.average_detection_confidence,
        first_timestamp=pt.first_timestamp,
        last_timestamp=pt.last_timestamp,
        thumbnail_url=f"/media/{pt.thumbnail_path}" if pt.thumbnail_path else None,
        selectable=selectable,
        reason=reason,
    )


def _get_video(db: Session, video_id: str) -> models.Video:
    v = db.get(models.Video, video_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return v


def _get_person(db: Session, video_id: str, person_id: str) -> models.PersonTrack:
    pt = db.get(models.PersonTrack, person_id)
    if pt is None or pt.video_id != video_id:
        raise HTTPException(status_code=404, detail="Person not found for this video.")
    return pt


@router.get("", response_model=PeopleListOut)
def list_people(
    video_id: str,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> PeopleListOut:
    v = _get_video(db, video_id)
    rows = (
        db.query(models.PersonTrack)
        .filter(models.PersonTrack.video_id == video_id)
        .order_by(models.PersonTrack.lip_readiness_score.desc())
        .all()
    )
    return PeopleListOut(video_id=video_id, status=v.status,
                         people=[_person_out(pt, settings) for pt in rows])


@router.get("/{person_id}", response_model=PersonOut)
def get_person(
    video_id: str,
    person_id: str,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> PersonOut:
    pt = _get_person(db, video_id, person_id)
    return _person_out(pt, settings)


@router.post("/{person_id}/analyze", response_model=PersonAnalysisResultOut)
def analyze_person(
    video_id: str,
    person_id: str,
    body: AnalyzePersonRequest | None = None,
    db: Session = Depends(get_db_session),
) -> PersonAnalysisResultOut:
    """Run Stage B for a person. Runs synchronously; honest availability state."""
    _get_video(db, video_id)
    _get_person(db, video_id, person_id)
    override = bool(body and body.override_quality_gates)
    result = process_person_analysis(video_id, person_id, override) or {}
    return PersonAnalysisResultOut(
        video_id=video_id,
        person_id=person_id,
        state=result.get("state", "MODEL_UNAVAILABLE"),
        detail=result.get("detail"),
        segments=result.get("segments", 0),
        gaze=result.get("gaze", 0),
        landmarks_available=result.get("landmarks_available", False),
        lipreading_available=result.get("lipreading_available", False),
    )


@router.get("/{person_id}/transcript", response_model=TranscriptOut)
def get_transcript(
    video_id: str,
    person_id: str,
    db: Session = Depends(get_db_session),
) -> TranscriptOut:
    _get_video(db, video_id)
    pt = _get_person(db, video_id, person_id)
    segs = (
        db.query(models.LipReadingSegment)
        .filter(models.LipReadingSegment.person_track_id == person_id)
        .order_by(models.LipReadingSegment.start_time)
        .all()
    )
    config = get_ml_config()
    if segs:
        model_version = segs[0].model_version
        availability = Availability(state=AvailabilityState.REAL_RESULT)
    else:
        # No transcript yet — report the precise reason honestly.
        lm = get_landmarker(config).availability()
        lip = get_lip_reading_model(config).availability()
        availability = lip if not lip.is_available else lm
        model_version = None

    out_segs = [
        TranscriptSegmentOut(
            start_time=s.start_time,
            end_time=s.end_time,
            text=s.text,
            confidence=s.confidence,
            raw_text=s.raw_text,
            processed_text=s.processed_text,
            uncertain=(s.text == UNCERTAIN),
            alternatives=s.alternatives or [],
        )
        for s in segs
    ]
    return TranscriptOut(
        video_id=video_id,
        person_id=person_id,
        availability=_availability_out(availability),
        model_version=model_version,
        segments=out_segs,
    )


@router.get("/{person_id}/gaze", response_model=GazeTimelineOut)
def get_gaze(
    video_id: str,
    person_id: str,
    db: Session = Depends(get_db_session),
) -> GazeTimelineOut:
    _get_video(db, video_id)
    _get_person(db, video_id, person_id)
    rows = (
        db.query(models.GazeObservation)
        .filter(models.GazeObservation.person_track_id == person_id)
        .order_by(models.GazeObservation.timestamp)
        .all()
    )
    config = get_ml_config()
    if rows:
        availability = Availability(state=AvailabilityState.REAL_RESULT)
    else:
        availability = get_landmarker(config).availability()

    # Coalesce consecutive same-direction observations into timeline segments (§36).
    segments: list[GazeSegmentOut] = []
    for r in rows:
        if segments and segments[-1].direction == r.direction:
            segments[-1].end = r.timestamp
        else:
            segments.append(
                GazeSegmentOut(
                    start=r.timestamp,
                    end=r.timestamp,
                    direction=r.direction,
                    confidence=r.confidence,
                    target_person_id=r.target_person_id,
                    target_confidence=r.target_confidence,
                )
            )
    return GazeTimelineOut(
        video_id=video_id,
        person_id=person_id,
        availability=_availability_out(availability),
        segments=segments,
    )


@router.post("/{person_id}/tts", response_model=TTSArtifactOut)
def synthesize_tts(
    video_id: str,
    person_id: str,
    body: TTSRequest | None = None,
    db: Session = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage_provider),
) -> TTSArtifactOut:
    """Generate optional generic synthetic speech from the transcript (§42–§44)."""
    _get_video(db, video_id)
    _get_person(db, video_id, person_id)
    body = body or TTSRequest()

    segs = (
        db.query(models.LipReadingSegment)
        .filter(models.LipReadingSegment.person_track_id == person_id)
        .order_by(models.LipReadingSegment.start_time)
        .all()
    )
    text_parts = [
        (s.processed_text if body.use_processed_transcript and s.processed_text else s.text)
        for s in segs
        if s.text and s.text != UNCERTAIN
    ]
    text = " ".join(text_parts).strip()

    provider = get_tts_provider(get_ml_config())
    av = provider.availability()
    if not text:
        return TTSArtifactOut(
            voice=body.voice, duration=0.0, sample_rate=0,
            label="Synthetic audio generated from visual transcript.",
            availability=_availability_out(
                Availability(state=AvailabilityState.NO_SIGNAL,
                             detail="No confident transcript text available to synthesize.")
            ),
        )
    if not av.is_available:
        return TTSArtifactOut(
            voice=body.voice, duration=0.0, sample_rate=0,
            label="Synthetic audio generated from visual transcript.",
            availability=_availability_out(av),
        )

    key = f"{video_id}/tts/person_{person_id}.wav"
    out_path = storage.local_path(key)
    try:
        artifact = provider.synthesize(
            text, out_path, voice=body.voice,
            authorized_voice_confirmation=body.authorized_voice_confirmation,
        )
    except VoicePermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = models.TTSArtifact(
        person_track_id=person_id, path=key, voice=artifact.voice,
        duration=artifact.duration, sample_rate=artifact.sample_rate, label=artifact.label,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return TTSArtifactOut(
        id=row.id, path=key, url=f"/media/{key}", voice=artifact.voice,
        duration=artifact.duration, sample_rate=artifact.sample_rate,
        label=artifact.label, availability=_availability_out(artifact.availability or av),
    )
