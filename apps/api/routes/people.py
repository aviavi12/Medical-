"""Person endpoints (§54): gallery, detail, analyze, transcript, gaze, tts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.config import Settings, get_settings
from apps.api.dependencies import get_db_session, get_storage_provider
from apps.api.schemas import (
    AnalyzePersonRequest,
    AvailabilityOut,
    DebugCropFrameOut,
    DebugCropsOut,
    GazeSegmentOut,
    GazeTimelineOut,
    PeopleListOut,
    PersonAnalysisResultOut,
    PersonEvalRequest,
    PersonEvalResultOut,
    PersonOut,
    PersonQualityReportOut,
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
    # Combined-score gate (§10, §11): READY and WARNING are selectable; only
    # INSUFFICIENT is blocked (but can still be overridden by advanced users).
    status = pt.readiness_status or "INSUFFICIENT"
    selectable = status != "INSUFFICIENT"
    reasons = pt.quality_reasons or []
    reason = None
    if reasons:
        reason = reasons[0]
    elif not selectable:
        reason = "Combined visual quality is insufficient for reliable lip reading."

    report = PersonQualityReportOut(
        status=status,
        readiness_score=round(pt.lip_readiness_score, 1),
        face_quality_score=round(pt.average_face_quality, 1),
        lip_readiness_score=round(pt.lip_readiness_score, 1),
        usable_duration=round(pt.usable_duration or 0.0, 2),
        visible_ratio=round(pt.visible_frame_ratio, 3),
        avg_face_width_px=round(pt.avg_face_width or 0.0, 1),
        avg_mouth_visibility_pct=round((pt.avg_mouth_visibility or 0.0) * 100, 1),
        avg_sharpness=round(pt.avg_sharpness or 0.0, 3),
        avg_pose_quality=round(pt.avg_pose_quality or 0.0, 3),
        tracking_stability=round(pt.tracking_stability or pt.visible_frame_ratio, 3),
        reasons=list(reasons),
    )
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
        status=status,
        reason=reason,
        quality_report=report,
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
    import time as _time

    _get_video(db, video_id)
    _get_person(db, video_id, person_id)
    override = bool(body and body.override_quality_gates)
    t0 = _time.perf_counter()
    result = process_person_analysis(video_id, person_id, override) or {}
    elapsed = round(_time.perf_counter() - t0, 2)
    from ml.common.config import get_ml_config
    from ml.common.device import resolve_device

    return PersonAnalysisResultOut(
        video_id=video_id,
        person_id=person_id,
        state=result.get("state", "MODEL_UNAVAILABLE"),
        detail=result.get("detail"),
        segments=result.get("segments", 0),
        gaze=result.get("gaze", 0),
        landmarks_available=result.get("landmarks_available", False),
        lipreading_available=result.get("lipreading_available", False),
        processing_seconds=elapsed,
        device=resolve_device(get_ml_config().device),
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
            visual_quality=s.visual_quality,
            speaking_activity=s.speaking_activity,
            frame_start=s.frame_start,
            frame_end=s.frame_end,
            window_index=s.window_index,
            person_id=person_id,
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


@router.get("/{person_id}/debug", response_model=DebugCropsOut)
def debug_crops(
    video_id: str,
    person_id: str,
    samples: int = 4,
    db: Session = Depends(get_db_session),
    storage: StorageProvider = Depends(get_storage_provider),
) -> DebugCropsOut:
    """Debug view (§12): the exact crops the model sees — original frame, face
    crop, lower-face crop (SyncVSR input), mouth crop, and a temporal strip — so
    a human can visually confirm the lips are captured."""
    video = _get_video(db, video_id)
    _get_person(db, video_id, person_id)
    config = get_ml_config()
    obs = (
        db.query(models.FaceObservation)
        .filter(models.FaceObservation.person_track_id == person_id)
        .order_by(models.FaceObservation.timestamp)
        .all()
    )
    if not obs:
        return DebugCropsOut(video_id=video_id, person_id=person_id, available=False,
                             note="No face observations for this person yet — run the scan first.")
    try:
        result = _build_debug_crops(video, person_id, obs, storage, config, max(1, min(samples, 8)))
        return result
    except Exception as exc:  # pragma: no cover - defensive
        return DebugCropsOut(video_id=video_id, person_id=person_id, available=False,
                             note=f"Could not build debug crops: {exc}")


def _build_debug_crops(video, person_id, obs, storage, config, samples) -> DebugCropsOut:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    from ml.common.sampling import FrameSampler
    from ml.lipreading.openvocab.preprocess import CropMode, OpenVocabPreprocessor

    path = storage.local_path(video.storage_path) if not str(video.storage_path).startswith("/") else video.storage_path
    sampler = FrameSampler(1.0)
    lower_pre = OpenVocabPreprocessor(mode=CropMode.LOWER_FACE)
    mouth_pre = OpenVocabPreprocessor(mode=CropMode.MOUTH_ONLY)

    # Evenly spaced sample observations.
    idxs = [int(round(i * (len(obs) - 1) / max(1, samples - 1))) for i in range(samples)] if samples > 1 else [len(obs) // 2]
    idxs = sorted(set(i for i in idxs if 0 <= i < len(obs)))

    def _save(key, img):
        ok, buf = cv2.imencode(".jpg", img)
        if not ok:
            return None
        storage.save_bytes(key, buf.tobytes())
        return f"/media/{key}"

    frames_out: list[DebugCropFrameOut] = []
    strip_crops: list = []
    for n, oi in enumerate(idxs):
        fo = obs[oi]
        frame = sampler.frame_at(str(path), fo.timestamp)
        if frame is None:
            continue
        h, w = frame.shape[:2]
        base = f"{video.id}/debug/person_{person_id}/f{n:02d}"

        # Original (downscaled for the panel) with the face box drawn.
        orig = frame.copy()
        x1, y1, x2, y2 = [int(v) for v in fo.bbox]
        cv2.rectangle(orig, (x1, y1), (x2, y2), (0, 200, 0), 2)
        scale = 480.0 / max(w, 1)
        if scale < 1.0:
            orig = cv2.resize(orig, (int(w * scale), int(h * scale)))
        original_url = _save(f"{base}_original.jpg", orig)

        # Face crop (padded bbox).
        px, py = int((x2 - x1) * 0.15), int((y2 - y1) * 0.15)
        fx1, fy1 = max(0, x1 - px), max(0, y1 - py)
        fx2, fy2 = min(w, x2 + px), min(h, y2 + py)
        face = frame[fy1:fy2, fx1:fx2]
        face_url = _save(f"{base}_face.jpg", face) if face.size else None

        # Lower-face (SyncVSR input) + mouth crops (grayscale 96x96).
        lower = lower_pre.crop_frame(frame, fo.bbox)
        mouth = mouth_pre.crop_frame(frame, fo.bbox)
        lower_url = _save(f"{base}_lower.jpg", lower) if lower is not None else None
        mouth_url = _save(f"{base}_mouth.jpg", mouth) if mouth is not None else None
        if lower is not None:
            strip_crops.append(lower)

        frames_out.append(DebugCropFrameOut(
            timestamp=round(fo.timestamp, 3),
            original_url=original_url, face_url=face_url,
            lower_face_url=lower_url, mouth_url=mouth_url,
        ))

    # Temporal strip: lower-face crops side by side (what the model sees in time).
    sequence_url = None
    if strip_crops:
        strip = np.hstack([cv2.copyMakeBorder(c, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=255)
                           for c in strip_crops])
        sequence_url = _save(f"{video.id}/debug/person_{person_id}/sequence.jpg", strip)

    return DebugCropsOut(
        video_id=video.id, person_id=person_id, available=bool(frames_out),
        note="Grayscale 96×96 lower-face crops are the exact SyncVSR model input.",
        crop_mode=config.openvocab_crop_mode, frames=frames_out, sequence_url=sequence_url,
    )


@router.post("/{person_id}/evaluate", response_model=PersonEvalResultOut)
def evaluate_person(
    video_id: str,
    person_id: str,
    body: PersonEvalRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> PersonEvalResultOut:
    """Developer-only evaluation (§20–§22): score the stored transcript against a
    pasted ground-truth string. Never exposed to normal users (gated by
    ``enable_evaluation_mode``); ground truth is provided by the developer, not
    stored, and never shown as a result."""
    if not settings.enable_evaluation_mode:
        return PersonEvalResultOut(video_id=video_id, person_id=person_id, enabled=False,
                                   note="Evaluation mode is disabled on this server.")
    _get_video(db, video_id)
    _get_person(db, video_id, person_id)
    from training.evaluation import alignment_ops, character_error_rate, word_error_rate

    segs = (
        db.query(models.LipReadingSegment)
        .filter(models.LipReadingSegment.person_track_id == person_id)
        .order_by(models.LipReadingSegment.start_time)
        .all()
    )
    parts, confs = [], []
    for s in segs:
        if s.text and s.text not in (UNCERTAIN, "[no speech evidence]"):
            parts.append(s.processed_text if body.use_processed and s.processed_text else s.text)
            confs.append(s.confidence)
    prediction = " ".join(parts).strip()
    reference = body.ground_truth.strip()
    if not reference:
        return PersonEvalResultOut(video_id=video_id, person_id=person_id, prediction=prediction,
                                   note="Provide a ground-truth transcript to score against.")
    if not prediction:
        return PersonEvalResultOut(video_id=video_id, person_id=person_id, prediction="",
                                   reference=reference,
                                   note="No transcript to evaluate — analyze this person first.")
    from training.evaluation import sentence_accuracy

    ops = alignment_ops(prediction, reference)
    avg_conf = round(sum(confs) / len(confs), 4) if confs else None
    sent_acc = round(sentence_accuracy([prediction], [reference]), 4)
    return PersonEvalResultOut(
        video_id=video_id, person_id=person_id, prediction=prediction, reference=reference,
        wer=round(word_error_rate(prediction, reference), 4),
        cer=round(character_error_rate(prediction, reference), 4),
        substitutions=ops["sub"], deletions=ops["del"], insertions=ops["ins"],
        ref_words=ops["ref_words"], hyp_words=ops["hyp_words"],
        sentence_accuracy=sent_acc,
        average_confidence=avg_conf,
        # Exactly what is done to BOTH strings before scoring — no cherry-picking.
        normalization="lowercased; surface punctuation .,!?;:\"'`()[]{} removed; whitespace "
                      "collapsed. Contractions, numbers-vs-words and spelling are NOT normalized.",
        note="Word-level WER/CER (substitution/deletion/insertion) on the raw model output vs "
             "your ground truth. average_confidence is a model-likelihood proxy, not accuracy.",
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
