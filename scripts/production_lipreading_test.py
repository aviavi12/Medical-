#!/usr/bin/env python3
"""SilentSpeak production open-vocabulary lip-reading test (Phase 32).

    python scripts/production_lipreading_test.py \
        --video path/to/no_audio_english_video.mp4 \
        --person auto \
        --mode visual-only \
        [--ground-truth "..."]  [--device auto|cpu|cuda|mps]

Strips audio first (visual-only enforcement, Phase 7), runs the real pipeline
(detect → track → select → open-vocabulary VSR), and prints the production report.
If the model cannot run, it reports exactly what is missing — it never fakes a
result and never falls back to the GRID benchmark model.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Production open-vocabulary lip-reading test")
    ap.add_argument("--video", required=True)
    ap.add_argument("--person", default="auto", help="'auto' or person_NNN")
    ap.add_argument("--mode", default="visual-only", choices=["visual-only"])
    ap.add_argument("--ground-truth", default=None)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--crop-mode", default="lower_face", choices=["lower_face", "full_face", "mouth_only"])
    ap.add_argument("--coarse-fps", type=int, default=8)
    args = ap.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ERROR: video not found: {video_path}", file=sys.stderr)
        return 2

    work = Path(tempfile.mkdtemp(prefix="ssl_prod_"))
    os.environ["DATABASE_URL"] = f"sqlite:///{work}/db.sqlite"
    os.environ["STORAGE_PATH"] = f"{work}/storage"
    os.environ["ALLOW_MOCK_INFERENCE"] = "0"
    os.environ["LIP_READING_MODEL"] = "syncvsr"          # open-vocabulary production model
    os.environ["OPENVOCAB_CROP_MODE"] = args.crop_mode
    os.environ["DEVICE"] = args.device
    os.environ["COARSE_FPS"] = str(args.coarse_fps)
    os.environ.setdefault("ANALYSIS_FPS", "25")

    from apps.api.config import get_settings
    from apps.api.services import pipeline
    from apps.api.services.storage import get_storage
    from apps.api.services.video import probe_metadata
    from database import models
    from database.base import create_all, get_session_factory, reset_engine_for_tests
    from ml.common.config import get_ml_config
    from ml.common.device import device_report
    from ml.lipreading import get_lip_reading_model
    from ml.lipreading.registry import active_entry

    get_settings.cache_clear()
    reset_engine_for_tests()
    create_all()
    settings, config, storage = get_settings(), get_ml_config(), None
    from apps.api.services.storage import get_storage as _gs
    storage = _gs(settings)
    db = get_session_factory()()

    # Model availability first — never fake.
    model = get_lip_reading_model(config)
    av = model.availability()
    entry = active_entry(config)
    dev = device_report(config.device)["device"]

    meta = probe_metadata(video_path)

    # Enforce visual-only: strip the audio track (Phase 7/24).
    noaudio = work / "visual_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(video_path), "-an", "-c:v", "libx264",
                    "-r", "25", str(noaudio)], capture_output=True, check=True)
    astreams = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(noaudio)], capture_output=True, text=True).stdout.strip()

    print("=" * 53)
    print("SILENTSPEAK PRODUCTION TEST")
    print("=" * 53)
    print(f"Video:            {video_path.name}")
    print(f"Audio:            NONE / IGNORED  (audio streams after strip: {astreams or 'NONE'})")
    print(f"Resolution:       {meta.width}x{meta.height}")
    print(f"FPS:              {meta.fps}")
    print(f"Device:           {dev}")
    print(f"Model:            {entry.display_name if entry else config.lip_reading_model}")
    print(f"Vocabulary:       {'OPEN' if (entry and entry.open_vocabulary) else 'CLOSED'}")
    print(f"Visual-only:      TRUE")
    print(f"Model status:     {av.state.value}")
    if not av.is_available:
        print(f"\nMODEL NOT AVAILABLE — {av.detail}")
        print(f"Missing:          {', '.join(av.missing)}")
        print("=" * 53)
        return 1

    key = f"prod/original/{noaudio.name}"
    storage.save(key, noaudio)
    video = models.Video(filename=noaudio.name, storage_path=key, status="QUEUED",
                         duration=meta.duration, width=meta.width, height=meta.height,
                         fps=meta.fps, has_audio=False)
    db.add(video)
    db.commit()
    db.refresh(video)

    t0 = time.time()
    pipeline.run_coarse_scan(db, video, storage, settings, config)
    people = (db.query(models.PersonTrack)
              .filter(models.PersonTrack.video_id == video.id)
              .order_by(models.PersonTrack.lip_readiness_score.desc()).all())
    if not people:
        print("\nNo person with a usable face was detected.")
        print("=" * 53)
        return 1

    if args.person != "auto":
        num = int(args.person.replace("person_", ""))
        person = next((p for p in people if p.track_number == num), people[0])
    else:
        person = people[0]

    result = pipeline.run_person_analysis(db, video, person, storage, settings, config)
    elapsed = time.time() - t0

    segs = (db.query(models.LipReadingSegment)
            .filter(models.LipReadingSegment.person_track_id == person.id)
            .order_by(models.LipReadingSegment.start_time).all())
    transcript = " ".join(s.text for s in segs).strip()

    print(f"Selected person:  person_{person.track_number:03d} of {len(people)}")
    print(f"Face quality:     {person.average_face_quality:.0f}/100")
    print(f"Result state:     {result.get('state')}")
    print(f"\nTranscript:       {transcript!r}")
    for s in segs:
        if s.alternatives:
            print(f"  n-best @ {s.start_time:.1f}s: " +
                  " | ".join(f"{a['text']!r}({a['confidence']:.2f})" for a in s.alternatives))
    if args.ground_truth:
        from training.evaluation import alignment_ops, character_error_rate, word_error_rate
        wer = word_error_rate(transcript, args.ground_truth)
        cer = character_error_rate(transcript, args.ground_truth)
        ops = alignment_ops(transcript, args.ground_truth)
        print(f"\nGround truth:     {args.ground_truth!r}")
        print(f"WER:              {wer:.3f}")
        print(f"CER:              {cer:.3f}")
        print(f"S/D/I:            sub={ops['sub']} del={ops['del']} ins={ops['ins']} (ref {ops['ref_words']} words)")
    print(f"\nProcessing time:  {elapsed:.1f}s")
    print("=" * 53)
    return 0


if __name__ == "__main__":
    sys.exit(main())
