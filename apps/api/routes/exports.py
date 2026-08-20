"""Export endpoints (§41, §54, §82, §83)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.schemas import ExportListOut
from apps.api.services.exports import (
    Segment,
    build_analysis_report,
    to_csv,
    to_json,
    to_srt,
    to_txt,
)
from database import models

router = APIRouter(prefix="/api/videos/{video_id}", tags=["exports"])

FORMATS = ["srt", "txt", "json", "csv", "report"]


@router.get("/exports", response_model=ExportListOut)
def list_exports(video_id: str, person_id: str, db: Session = Depends(get_db_session)) -> ExportListOut:
    v = db.get(models.Video, video_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    urls = {
        fmt: f"/api/videos/{video_id}/people/{person_id}/export/{fmt}" for fmt in FORMATS
    }
    return ExportListOut(video_id=video_id, person_id=person_id, formats=FORMATS, urls=urls)


def _segments(db: Session, person_id: str) -> list[models.LipReadingSegment]:
    return (
        db.query(models.LipReadingSegment)
        .filter(models.LipReadingSegment.person_track_id == person_id)
        .order_by(models.LipReadingSegment.start_time)
        .all()
    )


@router.get("/people/{person_id}/export/{fmt}")
def export_person(
    video_id: str, person_id: str, fmt: str, db: Session = Depends(get_db_session)
):
    v = db.get(models.Video, video_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    pt = db.get(models.PersonTrack, person_id)
    if pt is None or pt.video_id != video_id:
        raise HTTPException(status_code=404, detail="Person not found for this video.")

    fmt = fmt.lower()
    if fmt not in FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported export format '{fmt}'.")

    rows = _segments(db, person_id)
    segs = [Segment(r.start_time, r.end_time, r.processed_text or r.text, r.confidence) for r in rows]

    if fmt == "srt":
        return PlainTextResponse(to_srt(segs), media_type="application/x-subrip",
                                 headers={"Content-Disposition": f'attachment; filename="{person_id}.srt"'})
    if fmt == "txt":
        return PlainTextResponse(to_txt(segs), media_type="text/plain",
                                 headers={"Content-Disposition": f'attachment; filename="{person_id}.txt"'})
    if fmt == "csv":
        return PlainTextResponse(to_csv(segs), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{person_id}.csv"'})

    # json + report share the structured payload.
    gaze = (
        db.query(models.GazeObservation)
        .filter(models.GazeObservation.person_track_id == person_id)
        .order_by(models.GazeObservation.timestamp)
        .all()
    )
    video_dict = {
        "id": v.id, "filename": v.filename, "duration": v.duration,
        "width": v.width, "height": v.height, "fps": v.fps, "codec": v.codec,
        "has_audio": v.has_audio,
    }
    person_dict = {
        "id": pt.id, "track_number": pt.track_number, "screen_time": pt.screen_time,
        "visibility": pt.visible_frame_ratio, "face_quality": pt.average_face_quality,
        "lip_readiness": pt.lip_readiness_score,
    }
    transcript_dict = {
        "segments": [
            {"start_time": r.start_time, "end_time": r.end_time, "text": r.text,
             "confidence": r.confidence, "raw_text": r.raw_text,
             "processed_text": r.processed_text, "model_version": r.model_version}
            for r in rows
        ]
    }
    gaze_dict = {
        "observations": [
            {"timestamp": g.timestamp, "direction": g.direction, "confidence": g.confidence,
             "yaw": g.yaw, "pitch": g.pitch, "roll": g.roll}
            for g in gaze
        ]
    }
    model_versions = sorted({r.model_version for r in rows if r.model_version})
    mv_list = [{"model_version": m} for m in model_versions]

    if fmt == "json":
        payload = {
            "video_id": video_id, "person_id": person_id,
            "video": video_dict, "person": person_dict,
            "transcript": transcript_dict, "gaze": gaze_dict,
            "model_versions": mv_list,
        }
        return PlainTextResponse(to_json(payload), media_type="application/json",
                                 headers={"Content-Disposition": f'attachment; filename="{person_id}.json"'})

    # report
    report = build_analysis_report(
        video=video_dict, person=person_dict, transcript=transcript_dict,
        gaze=gaze_dict, model_versions=mv_list,
    )
    return PlainTextResponse(to_json(report), media_type="application/json",
                             headers={"Content-Disposition": f'attachment; filename="{person_id}_report.json"'})
