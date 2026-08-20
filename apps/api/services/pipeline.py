"""Two-stage pipeline orchestration (§17).

Stage A (coarse scan): detect people → track → detect faces → associate →
quality-score, all at COARSE_FPS, persisting per-person aggregates + face
observations + thumbnails. Expensive lip reading is NOT run here.

Stage B (selected person): reuse cached face observations → landmarks → mouth
ROI → temporal sequence → lip reading → gaze, persisting results with their
honesty state. Never fabricates ML output: if a required model is unavailable,
the job records the exact missing dependency.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from apps.api.config import Settings
from apps.api.services.logging_setup import get_logger
from apps.api.services.storage import StorageProvider
from database import models
from ml.association import associate
from ml.common.config import MLConfig
from ml.common.sampling import FrameSampler
from ml.common.types import BBox
from ml.detection import get_face_detector, get_person_detector
from ml.gaze import get_gaze_estimator
from ml.landmarks import get_landmarker
from ml.lipreading import get_lip_reading_model
from ml.lipreading.inference import run_inference
from ml.mouth import MouthExtractor, build_sequence
from ml.quality import get_quality_estimator
from ml.quality.readiness import PersonAggregate, lip_reading_readiness
from ml.tracking import get_tracker

logger = get_logger("silentspeak.pipeline")


@dataclass
class _Agg:
    frames_seen: int = 0
    first_sample: int | None = None
    last_sample: int | None = None
    first_ts: float | None = None
    last_ts: float | None = None
    det_conf: list[float] = field(default_factory=list)
    face_quality: list[float] = field(default_factory=list)
    face_width: list[float] = field(default_factory=list)
    mouth_vis: list[float] = field(default_factory=list)
    sharpness: list[float] = field(default_factory=list)
    pose: list[float] = field(default_factory=list)
    best_quality: float = -1.0
    best_ts: float = 0.0
    best_face_bbox: list[float] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_job(db: Session, job: models.ProcessingJob, *, status=None, stage=None,
             progress=None, error=None, device=None) -> None:
    if status is not None:
        job.status = status
    if stage is not None:
        job.stage = stage
    if progress is not None:
        job.progress = progress
    if error is not None:
        job.error = error
    if device is not None:
        job.device = device
    db.add(job)
    db.commit()


def run_coarse_scan(
    db: Session,
    video: models.Video,
    storage: StorageProvider,
    settings: Settings,
    config: MLConfig,
) -> models.ProcessingJob:
    """Execute Stage A. Returns the job row (status COMPLETED/READY or FAILED)."""
    from ml.common.device import resolve_device

    job = models.ProcessingJob(video_id=video.id, kind="coarse_scan", status="QUEUED",
                               device=resolve_device(config.device), started_at=_now())
    db.add(job)
    db.commit()

    detector = get_person_detector(config)
    av = detector.availability()
    if not av.is_available:
        # Honest failure: name the exact missing dependency (§64, §93).
        _set_job(db, job, status="FAILED", stage="DETECTING_PEOPLE", error=av.detail)
        video.status = "FAILED"
        db.add(video)
        db.commit()
        logger.warning("person detector unavailable", extra={"video_id": video.id, "error": av.detail})
        return job

    face_detector = get_face_detector(config)
    face_available = face_detector.availability().is_available
    tracker = get_tracker(config)
    quality = get_quality_estimator(config)
    sampler = FrameSampler(config.coarse_fps)

    path = storage.local_path(video.storage_path) if not str(video.storage_path).startswith("/") else video.storage_path
    aggregates: dict[int, _Agg] = defaultdict(_Agg)
    pending_faces: list[tuple[int, models.FaceObservation]] = []
    total_samples = 0

    _set_job(db, job, status="DETECTING_PEOPLE", stage="DETECTING_PEOPLE", progress=0.05)

    try:
        for sf in sampler.iter_frames(str(path), video.id, decode=True):
            total_samples += 1
            persons = detector.detect(sf.image, sf.source_frame_index, sf.timestamp_seconds)
            tracks = tracker.update(persons, sf.source_frame_index, sf.timestamp_seconds)
            faces = face_detector.detect(sf.image, sf.source_frame_index, sf.timestamp_seconds) if face_available else []
            assoc = associate(faces, tracks)

            # Map track_id -> associated face bbox (if any).
            track_face: dict[int, BBox] = {}
            for a in assoc:
                if a.person_track_id is not None and not a.uncertain:
                    track_face[a.person_track_id] = faces[a.face_index].bbox

            for t in tracks:
                agg = aggregates[t.track_id]
                agg.frames_seen += 1
                agg.first_sample = sf.sample_index if agg.first_sample is None else agg.first_sample
                agg.last_sample = sf.sample_index
                agg.first_ts = sf.timestamp_seconds if agg.first_ts is None else agg.first_ts
                agg.last_ts = sf.timestamp_seconds
                agg.det_conf.append(t.confidence)

                fbbox = track_face.get(t.track_id)
                if fbbox is not None:
                    fq = quality.score(sf.image, fbbox)
                    agg.face_quality.append(fq.score)
                    agg.face_width.append(fq.face_width)
                    agg.mouth_vis.append(fq.mouth_visibility)
                    agg.sharpness.append(fq.sharpness)
                    agg.pose.append(fq.pose_score)
                    if fq.score > agg.best_quality:
                        agg.best_quality = fq.score
                        agg.best_ts = sf.timestamp_seconds
                        agg.best_face_bbox = fbbox.as_list()
                    obs = models.FaceObservation(
                        person_track_id="",  # filled after tracks persisted
                        timestamp=sf.timestamp_seconds,
                        frame_index=sf.source_frame_index,
                        bbox=fbbox.as_list(),
                        confidence=faces_conf(faces, fbbox),
                        width=fq.face_width,
                        height=fq.face_height,
                        blur_score=fq.blur,
                        brightness_score=fq.brightness,
                        pose_score=fq.pose_score,
                        mouth_visibility=fq.mouth_visibility,
                        eye_visibility=fq.eye_visibility,
                        occlusion_score=fq.occlusion,
                        quality_score=fq.score,
                    )
                    pending_faces.append((t.track_id, obs))
    except Exception as exc:  # pragma: no cover - defensive
        _set_job(db, job, status="FAILED", stage="DETECTING_PEOPLE", error=str(exc))
        video.status = "FAILED"
        db.add(video)
        db.commit()
        logger.error("coarse scan failed", extra={"video_id": video.id, "error": str(exc)})
        return job

    _set_job(db, job, status="QUALITY_ANALYSIS", stage="QUALITY_ANALYSIS", progress=0.7)

    # Persist person tracks + readiness.
    track_row_by_id: dict[int, models.PersonTrack] = {}
    for track_id, agg in sorted(aggregates.items()):
        if agg.frames_seen == 0:
            continue
        span = (agg.last_sample - agg.first_sample + 1) if agg.first_sample is not None else 1
        tracking_stability = min(1.0, agg.frames_seen / span) if span else 0.0
        avg = lambda xs: (sum(xs) / len(xs)) if xs else 0.0  # noqa: E731
        avg_face_quality = avg(agg.face_quality)
        avg_face_width = avg(agg.face_width)
        avg_res = min(1.0, avg_face_width / 200.0) if avg_face_width else 0.0

        readiness = lip_reading_readiness(
            PersonAggregate(
                face_quality=avg_face_quality,
                mouth_visibility=avg(agg.mouth_vis),
                face_resolution=avg_res,
                tracking_stability=tracking_stability,
                pose_quality=avg(agg.pose),
                sharpness=avg(agg.sharpness),
            ),
            config.weights,
        )

        screen_time = agg.frames_seen / max(1, config.coarse_fps)
        visible_ratio = agg.frames_seen / max(1, total_samples)

        pt = models.PersonTrack(
            video_id=video.id,
            track_number=track_id,
            first_timestamp=agg.first_ts,
            last_timestamp=agg.last_ts,
            screen_time=round(screen_time, 3),
            visible_frame_ratio=round(visible_ratio, 4),
            average_detection_confidence=round(avg(agg.det_conf), 4),
            average_face_quality=round(avg_face_quality, 2),
            lip_readiness_score=readiness,
        )
        db.add(pt)
        db.flush()  # get pt.id
        track_row_by_id[track_id] = pt

        # Thumbnail from the best-quality frame.
        if agg.best_face_bbox is not None:
            thumb_key = _save_thumbnail(storage, str(path), video.id, track_id, agg.best_ts, agg.best_face_bbox)
            if thumb_key:
                pt.thumbnail_path = thumb_key
                db.add(pt)

    # Link + persist face observations.
    for tid, row in pending_faces:
        pt = track_row_by_id.get(tid)
        if pt is None:
            continue
        row.person_track_id = pt.id
        db.add(row)

    video.status = "READY_FOR_SELECTION"
    db.add(video)
    _set_job(db, job, status="READY_FOR_SELECTION", stage="READY_FOR_SELECTION", progress=1.0)
    db.commit()
    logger.info("coarse scan complete",
                extra={"video_id": video.id, "stage": "READY_FOR_SELECTION"})
    return job


def faces_conf(faces, bbox: BBox) -> float:
    for f in faces:
        if f.bbox is bbox:
            return f.confidence
    return 0.0


def _save_thumbnail(storage, video_path, video_id, track_id, timestamp, face_bbox) -> str | None:
    try:
        import cv2  # type: ignore

        sampler = FrameSampler(1.0)
        frame = sampler.frame_at(video_path, timestamp)
        if frame is None:
            return None
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = face_bbox
        # Pad the face box for a nicer thumbnail.
        pad_x = (x2 - x1) * 0.4
        pad_y = (y2 - y1) * 0.4
        x1 = max(0, int(x1 - pad_x)); y1 = max(0, int(y1 - pad_y))
        x2 = min(w, int(x2 + pad_x)); y2 = min(h, int(y2 + pad_y))
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        ok, buf = cv2.imencode(".jpg", crop)
        if not ok:
            return None
        key = f"{video_id}/persons/person_{track_id:03d}.jpg"
        storage.save_bytes(key, buf.tobytes())
        return key
    except Exception:
        return None


def run_person_analysis(
    db: Session,
    video: models.Video,
    person: models.PersonTrack,
    storage: StorageProvider,
    settings: Settings,
    config: MLConfig,
    override_gates: bool = False,
) -> dict:
    """Execute Stage B for one person. Persists segments + gaze with honesty
    state. Returns a dict summarising availability."""
    from ml.quality.readiness import passes_quality_gates

    job = models.ProcessingJob(video_id=video.id, kind="person_analysis", status="ANALYZING_PERSON",
                               stage="ANALYZING_PERSON", started_at=_now())
    db.add(job)
    db.commit()

    # Quality gates (§65): don't run expensive models on insufficient input.
    face_obs = (
        db.query(models.FaceObservation)
        .filter(models.FaceObservation.person_track_id == person.id)
        .order_by(models.FaceObservation.timestamp)
        .all()
    )
    avg_width = (sum(f.width for f in face_obs) / len(face_obs)) if face_obs else 0.0
    avg_mouth = (sum(f.mouth_visibility for f in face_obs) / len(face_obs)) if face_obs else 0.0
    passed, failures = passes_quality_gates(
        face_width=avg_width,
        face_quality=person.average_face_quality,
        mouth_visibility=avg_mouth,
        tracking_stability=person.visible_frame_ratio,
        gates=config.gates,
        override=override_gates,
    )
    if not passed:
        _set_job(db, job, status="FAILED", stage="QUALITY_ANALYSIS", error=" ".join(failures))
        return {"state": "NO_SIGNAL", "detail": " ".join(failures), "segments": 0}

    landmarker = get_landmarker(config)
    lm_av = landmarker.availability()
    model = get_lip_reading_model(config)
    gaze = get_gaze_estimator(config)
    extractor = MouthExtractor()

    _set_job(db, job, status="EXTRACTING_MOUTH", stage="EXTRACTING_MOUTH", progress=0.3)

    path = storage.local_path(video.storage_path) if not str(video.storage_path).startswith("/") else video.storage_path
    sampler = FrameSampler(1.0)

    crops = []
    gaze_rows: list[models.GazeObservation] = []
    if lm_av.is_available:
        for fo in face_obs:
            frame = sampler.frame_at(str(path), fo.timestamp)
            if frame is None:
                continue
            bbox = BBox.from_list(fo.bbox)
            landmarks = landmarker.landmarks(frame, bbox)
            if landmarks is None:
                continue
            crop = extractor.extract(frame, landmarks, fo.frame_index, fo.timestamp, fo.quality_score)
            if crop is not None:
                crops.append(crop)
            g = gaze.estimate(landmarks, fo.timestamp)
            gaze_rows.append(
                models.GazeObservation(
                    person_track_id=person.id,
                    timestamp=fo.timestamp,
                    direction=g.direction.value,
                    yaw=g.head_pose.yaw if g.head_pose else None,
                    pitch=g.head_pose.pitch if g.head_pose else None,
                    roll=g.head_pose.roll if g.head_pose else None,
                    confidence=g.confidence,
                )
            )

    for gr in gaze_rows:
        db.add(gr)

    _set_job(db, job, status="LIP_READING", stage="LIP_READING", progress=0.6)

    contract = model.input_contract()
    lip_av = model.availability()
    segments_written = 0
    if lip_av.is_available and crops:
        sequence = build_sequence(crops, contract.required_fps, contract.sequence_length)
        result = run_inference(model, [sequence])
        mv = _persist_model_version(db, model)
        for seg in result.segments:
            row = models.LipReadingSegment(
                person_track_id=person.id,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                confidence=seg.confidence,
                model_version=mv,
                raw_text=seg.raw_text,
                processed_text=seg.processed_text,
                alternatives=[{"text": t, "confidence": c} for t, c in seg.alternatives],
            )
            db.add(row)
            db.flush()
            for w in seg.words:
                db.add(models.LipReadingWordRow(segment_id=row.id, word=w.word,
                                                start_time=w.start, end_time=w.end,
                                                confidence=w.confidence))
            segments_written += 1
        state = "REAL_RESULT"
        detail = None
    else:
        state = "MODEL_UNAVAILABLE"
        detail = lip_av.detail or (lm_av.detail if not lm_av.is_available else "No mouth crops available.")

    _set_job(db, job, status="COMPLETED", stage="COMPLETED", progress=1.0)
    db.commit()
    logger.info("person analysis complete",
                extra={"video_id": video.id, "person_id": person.id, "stage": "COMPLETED"})
    return {"state": state, "detail": detail, "segments": segments_written,
            "gaze": len(gaze_rows), "landmarks_available": lm_av.is_available,
            "lipreading_available": lip_av.is_available}


def _persist_model_version(db: Session, model) -> str:
    info = model.get_model_info()
    mv = models.ModelVersion(
        model_name=info.name,
        version=info.version,
        checkpoint=info.checkpoint,
        framework=info.framework,
        device=info.device,
        configuration=info.configuration,
    )
    db.add(mv)
    db.flush()
    return f"{info.name}:{info.version}"
