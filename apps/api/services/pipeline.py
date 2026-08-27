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
from ml.common.types import BBox, PersonDetection
from ml.detection import get_face_detector, get_person_detector
from ml.gaze import get_gaze_estimator
from ml.landmarks import get_landmarker
from ml.lipreading import get_lip_reading_model
from ml.lipreading.inference import run_inference
from ml.mouth import MouthExtractor, build_sequence
from ml.quality import get_quality_estimator
from ml.quality.readiness import PersonAggregate, lip_reading_readiness, readiness_status
from ml.tracking import get_tracker

logger = get_logger("lipsight.pipeline")


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
    # Gate on the FACE detector: a visible, trackable face is what lip reading
    # needs (a person seen only from behind cannot be lip-read). Person detection
    # (YOLO) runs best-effort for context; it does not gate gallery creation, so
    # head-and-shoulders / close-up footage still yields selectable people.
    face_detector = get_face_detector(config)
    face_av = face_detector.availability()
    if not face_av.is_available:
        _set_job(db, job, status="FAILED", stage="DETECTING_FACES", error=face_av.detail)
        video.status = "FAILED"
        db.add(video)
        db.commit()
        logger.warning("face detector unavailable", extra={"video_id": video.id, "error": face_av.detail})
        return job

    person_available = detector.availability().is_available
    tracker = get_tracker(config)
    quality = get_quality_estimator(config)
    sampler = FrameSampler(config.coarse_fps)

    path = storage.local_path(video.storage_path) if not str(video.storage_path).startswith("/") else video.storage_path
    aggregates: dict[int, _Agg] = defaultdict(_Agg)
    pending_faces: list[tuple[int, models.FaceObservation]] = []
    total_samples = 0

    _set_job(db, job, status="DETECTING_FACES", stage="DETECTING_FACES", progress=0.05)

    try:
        for sf in sampler.iter_frames(str(path), video.id, decode=True):
            total_samples += 1
            faces = face_detector.detect(sf.image, sf.source_frame_index, sf.timestamp_seconds)
            # Each tracked face is treated as a person for the gallery.
            face_dets = [
                PersonDetection(bbox=f.bbox, confidence=f.confidence,
                                frame_index=sf.source_frame_index, timestamp=sf.timestamp_seconds)
                for f in faces
            ]
            tracks = tracker.update(face_dets, sf.source_frame_index, sf.timestamp_seconds)
            # Best-effort person detection (context/debug only; never gates).
            if person_available:
                try:
                    detector.detect(sf.image, sf.source_frame_index, sf.timestamp_seconds)
                except Exception:
                    pass

            for t in tracks:
                agg = aggregates[t.track_id]
                agg.frames_seen += 1
                agg.first_sample = sf.sample_index if agg.first_sample is None else agg.first_sample
                agg.last_sample = sf.sample_index
                agg.first_ts = sf.timestamp_seconds if agg.first_ts is None else agg.first_ts
                agg.last_ts = sf.timestamp_seconds
                agg.det_conf.append(t.confidence)

                fbbox = t.bbox  # the tracked face box
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
                    confidence=t.confidence,
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
        avg_mouth_vis = avg(agg.mouth_vis)
        avg_sharpness = avg(agg.sharpness)
        avg_pose = avg(agg.pose)
        avg_res = min(1.0, avg_face_width / 200.0) if avg_face_width else 0.0

        readiness = lip_reading_readiness(
            PersonAggregate(
                face_quality=avg_face_quality,
                mouth_visibility=avg_mouth_vis,
                face_resolution=avg_res,
                tracking_stability=tracking_stability,
                pose_quality=avg_pose,
                sharpness=avg_sharpness,
            ),
            config.weights,
        )

        screen_time = agg.frames_seen / max(1, config.coarse_fps)
        visible_ratio = agg.frames_seen / max(1, total_samples)
        usable_duration = (agg.last_ts - agg.first_ts) if (agg.first_ts is not None and agg.last_ts is not None) else screen_time

        # Combined-score status + full quality report (§10, §11, §25).
        report = readiness_status(
            readiness_score=readiness,
            avg_face_width_px=avg_face_width,
            avg_mouth_visibility=avg_mouth_vis,
            avg_sharpness=avg_sharpness,
            avg_pose_quality=avg_pose,
            tracking_stability=tracking_stability,
            usable_duration=usable_duration,
            face_quality_score=avg_face_quality,
            visible_ratio=visible_ratio,
            gates=config.gates,
        )

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
            readiness_status=report.status,
            usable_duration=round(usable_duration, 3),
            avg_face_width=round(avg_face_width, 1),
            avg_mouth_visibility=round(avg_mouth_vis, 4),
            avg_sharpness=round(avg_sharpness, 4),
            avg_pose_quality=round(avg_pose, 4),
            tracking_stability=round(tracking_stability, 4),
            quality_reasons=report.reasons,
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


def _interp_roi(roi_index: list[tuple[float, list]], ts: float) -> list | None:
    """Linear-interpolate a person's face bbox at time ``ts`` from coarse-scan
    observations, so Stage-B 25fps frames can be tied to the selected person."""
    if not roi_index:
        return None
    if ts <= roi_index[0][0]:
        return roi_index[0][1]
    if ts >= roi_index[-1][0]:
        return roi_index[-1][1]
    for i in range(1, len(roi_index)):
        t0, b0 = roi_index[i - 1]
        t1, b1 = roi_index[i]
        if t0 <= ts <= t1:
            if t1 == t0:
                return b0
            a = (ts - t0) / (t1 - t0)
            return [b0[j] + (b1[j] - b0[j]) * a for j in range(4)]
    return roi_index[-1][1]


def _stream_person_crops(path, face_obs, person, model, config):
    """Re-sample the selected person at analysis FPS (lip-reading models need
    their trained FPS, e.g. 25) and stream aligned mouth crops. Only the small
    128x64 crops are kept in memory, not full frames."""
    fps = float(config.analysis_fps or 25)
    roi_index = [(fo.timestamp, fo.bbox) for fo in face_obs]
    first_ts = person.first_timestamp if person.first_timestamp is not None else (roi_index[0][0] if roi_index else 0.0)
    last_ts = person.last_timestamp if person.last_timestamp is not None else (roi_index[-1][0] if roi_index else 0.0)
    crops: list = []
    tss: list[float] = []
    for sf in FrameSampler(fps).iter_frames(str(path), decode=True):
        ts = sf.timestamp_seconds
        if ts < first_ts - 0.2:
            continue
        if ts > last_ts + 0.2:
            break
        roi = _interp_roi(roi_index, ts)
        try:
            # Uniform, model-specific per-frame crop; only the small crop is kept
            # in memory (not the full frame), so long videos stay bounded.
            crop = model.crop_for_frame(sf.image, roi)
        except Exception:
            crop = None
        if crop is not None:
            crops.append(crop)
            tss.append(ts)
    return crops, tss


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
    avg_width = person.avg_face_width or ((sum(f.width for f in face_obs) / len(face_obs)) if face_obs else 0.0)
    avg_mouth = person.avg_mouth_visibility or ((sum(f.mouth_visibility for f in face_obs) / len(face_obs)) if face_obs else 0.0)
    passed, failures = passes_quality_gates(
        face_width=avg_width,
        face_quality=person.average_face_quality,
        mouth_visibility=avg_mouth,
        tracking_stability=person.tracking_stability or person.visible_frame_ratio,
        gates=config.gates,
        override=override_gates,
        readiness_score=person.lip_readiness_score,
        avg_sharpness=person.avg_sharpness or 1.0,
        avg_pose_quality=person.avg_pose_quality or 1.0,
        usable_duration=person.usable_duration or person.screen_time,
        visible_ratio=person.visible_frame_ratio,
    )
    if not passed:
        detail = " ".join(failures) or "Combined visual quality is insufficient for reliable lip reading."
        _set_job(db, job, status="FAILED", stage="QUALITY_ANALYSIS", error=detail)
        return {"state": "NO_SIGNAL", "detail": detail, "segments": 0}

    landmarker = get_landmarker(config)
    lm_av = landmarker.availability()
    model = get_lip_reading_model(config)
    gaze = get_gaze_estimator(config)
    extractor = MouthExtractor()

    _set_job(db, job, status="EXTRACTING_MOUTH", stage="EXTRACTING_MOUTH", progress=0.3)

    path = storage.local_path(video.storage_path) if not str(video.storage_path).startswith("/") else video.storage_path
    sampler = FrameSampler(1.0)

    # Other people's face boxes over time, for "possible gaze toward another
    # person" estimation (§35). Reported as possible, never as certainty.
    others_roi: list[tuple[str, list[tuple[float, list]]]] = []
    for other in (
        db.query(models.PersonTrack)
        .filter(models.PersonTrack.video_id == video.id, models.PersonTrack.id != person.id)
        .all()
    ):
        oobs = (
            db.query(models.FaceObservation)
            .filter(models.FaceObservation.person_track_id == other.id)
            .order_by(models.FaceObservation.timestamp)
            .all()
        )
        if oobs:
            others_roi.append((other.id, [(o.timestamp, o.bbox) for o in oobs]))

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

            target_id: str | None = None
            target_conf = 0.0
            if others_roi:
                others_now = []
                for oid, idx in others_roi:
                    b = _interp_roi(idx, fo.timestamp)
                    if b is not None:
                        others_now.append((oid, BBox.from_list(b)))
                if others_now:
                    target_id, target_conf = gaze.gaze_toward(bbox, g, others_now)

            gaze_rows.append(
                models.GazeObservation(
                    person_track_id=person.id,
                    timestamp=fo.timestamp,
                    direction=g.direction.value,
                    yaw=g.head_pose.yaw if g.head_pose else None,
                    pitch=g.head_pose.pitch if g.head_pose else None,
                    roll=g.head_pose.roll if g.head_pose else None,
                    confidence=g.confidence,
                    target_person_id=target_id,
                    target_confidence=target_conf,
                )
            )

    for gr in gaze_rows:
        db.add(gr)

    _set_job(db, job, status="LIP_READING", stage="LIP_READING", progress=0.6)

    contract = model.input_contract()
    lip_av = model.availability()
    segments_written = 0
    result = None
    if getattr(model, "supports_frame_transcription", False) and lip_av.is_available:
        # Real path (e.g. LipNet): re-sample the person at the model's FPS and run
        # the model's own mouth-ROI preprocessing over real frames.
        mouth_crops, mouth_ts = _stream_person_crops(path, face_obs, person, model, config)
        result = model.transcribe_crops(mouth_crops, mouth_ts)
    elif lip_av.is_available and crops:
        # Generic/mock path: prebuilt mouth sequence from landmarker + MouthExtractor.
        sequence = build_sequence(crops, contract.required_fps, contract.sequence_length)
        result = run_inference(model, [sequence])

    if result is not None and result.availability.is_available:
        mv = _persist_model_version(db, model)
        for seg in result.segments:
            # Fill per-segment visual quality (§15) + person provenance (§19) when
            # the model did not set them (e.g. LipNet path).
            vq = seg.visual_quality if seg.visual_quality is not None else round(person.average_face_quality, 1)
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
                visual_quality=vq,
                speaking_activity=seg.speaking_activity,
                frame_start=seg.frame_start,
                frame_end=seg.frame_end,
                window_index=seg.window_index,
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
    elif result is not None:
        # Real model ran but returned a non-real state (NO_SIGNAL / unavailable).
        state = result.availability.state.value
        detail = result.availability.detail
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
