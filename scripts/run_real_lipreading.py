#!/usr/bin/env python3
"""Real end-to-end visual lip reading on a video (§21).

    python scripts/run_real_lipreading.py --video input.mp4 [--person-id person_001] \
        [--output results/] [--weights overlap|unseen] [--ground-truth "..."]

Runs the real pipeline: validate → detect faces → track → select person →
align + mouth ROI → temporal sequence → real LipNet → timestamped transcript.
Saves transcript.json, transcript.srt, and debug mouth crops; reports timing.
No audio is ever read (visual-only, §13/§14).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Real visual lip reading")
    ap.add_argument("--video", required=True)
    ap.add_argument("--person-id", default=None, help="e.g. person_001; default = best readiness")
    ap.add_argument("--output", default="results")
    ap.add_argument("--weights", default="overlap", choices=["overlap", "unseen"])
    ap.add_argument("--ground-truth", default=None)
    ap.add_argument("--coarse-fps", type=int, default=8)
    ap.add_argument("--override-gates", action="store_true")
    args = ap.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ERROR: video not found: {video_path}", file=sys.stderr)
        return 2

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    # Isolated DB + storage so the CLI leaves no residue in the app DB.
    workdir = Path(tempfile.mkdtemp(prefix="ssl_cli_"))
    os.environ["DATABASE_URL"] = f"sqlite:///{workdir}/db.sqlite"
    os.environ["STORAGE_PATH"] = f"{workdir}/storage"
    os.environ["ALLOW_MOCK_INFERENCE"] = "0"
    os.environ["COARSE_FPS"] = str(args.coarse_fps)
    os.environ.setdefault("ANALYSIS_FPS", "25")
    os.environ["LIP_READING_WEIGHTS"] = str(REPO_ROOT / "models" / f"lipnet_{args.weights}.pt")

    from apps.api.config import get_settings
    from apps.api.services import pipeline
    from apps.api.services.storage import get_storage
    from apps.api.services.video import probe_metadata
    from database import models
    from database.base import create_all, get_session_factory, reset_engine_for_tests
    from ml.common.config import get_ml_config
    from ml.common.device import device_report

    get_settings.cache_clear()
    reset_engine_for_tests()
    create_all()
    settings = get_settings()
    config = get_ml_config()
    storage = get_storage(settings)
    db = get_session_factory()()

    print(f"Device: {device_report(config.device)['device']}")
    print(f"Lip-reading weights: {Path(config.lip_reading_weights).name}")

    meta = probe_metadata(video_path)
    print(f"Video: {meta.width}x{meta.height} @ {meta.fps}fps, {meta.duration}s, audio={meta.has_audio}")

    key = f"cli/original/{video_path.name}"
    storage.save(key, video_path)
    video = models.Video(filename=video_path.name, storage_path=key, status="QUEUED",
                         duration=meta.duration, width=meta.width, height=meta.height,
                         fps=meta.fps, has_audio=meta.has_audio)
    db.add(video)
    db.commit()
    db.refresh(video)

    t0 = time.time()
    print("\n[1/2] Coarse scan (faces → tracking → quality)…")
    pipeline.run_coarse_scan(db, video, storage, settings, config)
    people = (
        db.query(models.PersonTrack)
        .filter(models.PersonTrack.video_id == video.id)
        .order_by(models.PersonTrack.lip_readiness_score.desc())
        .all()
    )
    if not people:
        print("No people with a usable face were detected.")
        return 1
    print(f"Detected {len(people)} person(s):")
    for p in people:
        print(f"  person_{p.track_number:03d}: face_q={p.average_face_quality:.0f} "
              f"readiness={p.lip_readiness_score:.0f} screen={p.screen_time:.1f}s")

    if args.person_id:
        num = int(args.person_id.replace("person_", ""))
        person = next((p for p in people if p.track_number == num), None)
        if person is None:
            print(f"person {args.person_id} not found.")
            return 1
    else:
        person = people[0]
    print(f"\n[2/2] Analyzing person_{person.track_number:03d} with real LipNet…")

    result = pipeline.run_person_analysis(db, video, person, storage, settings, config,
                                          override_gates=args.override_gates)
    elapsed = time.time() - t0

    segs = (
        db.query(models.LipReadingSegment)
        .filter(models.LipReadingSegment.person_track_id == person.id)
        .order_by(models.LipReadingSegment.start_time)
        .all()
    )

    # Debug mouth crops (§32)
    _save_debug_crops(out, video_path, person, config, db)

    transcript_text = " ".join(s.text for s in segs).strip()
    print(f"\nState: {result.get('state')}")
    if result.get("detail"):
        print(f"Detail: {result['detail']}")
    print(f"TRANSCRIPT: {transcript_text!r}")
    if args.ground_truth:
        from training.evaluation import character_error_rate, word_error_rate
        wer = word_error_rate(transcript_text, args.ground_truth)
        cer = character_error_rate(transcript_text, args.ground_truth)
        print(f"GROUND TRUTH: {args.ground_truth!r}")
        print(f"WER={wer:.3f}  CER={cer:.3f}")

    # Save JSON + SRT
    payload = {
        "video": {"path": str(video_path), "width": meta.width, "height": meta.height,
                  "fps": meta.fps, "duration": meta.duration, "has_audio": meta.has_audio},
        "device": device_report(config.device),
        "person": {"id": f"person_{person.track_number:03d}",
                   "face_quality": person.average_face_quality,
                   "lip_readiness": person.lip_readiness_score},
        "state": result.get("state"),
        "model_version": segs[0].model_version if segs else None,
        "segments": [
            {"start_time": s.start_time, "end_time": s.end_time, "text": s.text,
             "confidence": s.confidence,
             "words": [{"word": w.word, "start": w.start_time, "end": w.end_time,
                        "confidence": w.confidence}
                       for w in db.query(models.LipReadingWordRow)
                       .filter(models.LipReadingWordRow.segment_id == s.id).all()]}
            for s in segs
        ],
        "processing_seconds": round(elapsed, 2),
    }
    (out / "transcript.json").write_text(json.dumps(payload, indent=2))

    from apps.api.services.exports import Segment, to_srt
    srt = to_srt([Segment(s.start_time, s.end_time, s.text, s.confidence) for s in segs])
    (out / "transcript.srt").write_text(srt)

    print(f"\nProcessing time: {elapsed:.2f}s")
    print(f"Saved: {out}/transcript.json, {out}/transcript.srt, {out}/debug/")
    return 0


def _save_debug_crops(out: Path, video_path: Path, person, config, db) -> None:
    """Save a few aligned mouth crops so the ROI can be visually inspected (§32)."""
    try:
        import cv2  # type: ignore

        from database import models
        from ml.lipreading import get_lip_reading_model

        model = get_lip_reading_model(config)
        if not getattr(model, "supports_frame_transcription", False) or not model.availability().is_available:
            return
        pre = model.preprocessor
        dbg = out / "debug" / f"person_{person.track_number:03d}"
        (dbg / "mouth_samples").mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(str(video_path))
        i = 0
        saved = 0
        while saved < 6:
            ok, frame = cap.read()
            if not ok:
                break
            if i % 5 == 0:
                m = pre.mouth_crop(frame, None)
                if m is not None:
                    cv2.imwrite(str(dbg / "mouth_samples" / f"{saved:02d}.jpg"), m.crop)
                    saved += 1
            i += 1
        cap.release()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
