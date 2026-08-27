#!/usr/bin/env python3
"""Pipeline benchmark (§67).

Measures per-stage latency, FPS, and the device in use, emitting a JSON report.
Stages whose models are unavailable are reported as such (never faked).

Usage:
    python scripts/benchmark_pipeline.py --video clip.mp4 --report out/bench.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Allow running as a standalone script: put the repo root on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - start) * 1000.0


def main() -> None:
    parser = argparse.ArgumentParser(description="LipSight pipeline benchmark")
    parser.add_argument("--video", required=True, help="Path to a test video")
    parser.add_argument("--report", default="bench.json", help="Output JSON path")
    parser.add_argument("--fps", type=float, default=8.0, help="Coarse sampling FPS")
    args = parser.parse_args()

    from ml.common.config import get_ml_config
    from ml.common.device import device_report
    from ml.common.sampling import FrameSampler
    from ml.detection import get_face_detector, get_person_detector
    from ml.quality import get_quality_estimator
    from ml.tracking import get_tracker

    config = get_ml_config()
    report: dict = {
        "video": args.video,
        "device": device_report(config.device),
        "stages": {},
        "availability": {},
    }

    person = get_person_detector(config)
    face = get_face_detector(config)
    tracker = get_tracker(config)
    quality = get_quality_estimator(config)
    report["availability"] = {
        "person_detector": person.availability().as_dict(),
        "face_detector": face.availability().as_dict(),
    }

    sampler = FrameSampler(args.fps)
    frames = 0
    det_ms = track_ms = face_ms = qual_ms = 0.0

    t0 = time.perf_counter()
    for sf in sampler.iter_frames(args.video, decode=True):
        frames += 1
        dets, dt = _timed(lambda: person.detect(sf.image, sf.source_frame_index, sf.timestamp_seconds))
        det_ms += dt
        _, tt = _timed(lambda: tracker.update(dets, sf.source_frame_index, sf.timestamp_seconds))
        track_ms += tt
        faces, ft = _timed(lambda: face.detect(sf.image, sf.source_frame_index, sf.timestamp_seconds))
        face_ms += ft
        if faces:
            _, qt = _timed(lambda: quality.score(sf.image, faces[0].bbox))
            qual_ms += qt
    total_s = time.perf_counter() - t0

    report["stages"] = {
        "frames_processed": frames,
        "total_seconds": round(total_s, 3),
        "fps": round(frames / total_s, 2) if total_s > 0 else 0,
        "person_detection_ms_total": round(det_ms, 2),
        "tracking_ms_total": round(track_ms, 2),
        "face_detection_ms_total": round(face_ms, 2),
        "quality_ms_total": round(qual_ms, 2),
        "person_detection_ms_avg": round(det_ms / frames, 3) if frames else 0,
    }

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nReport written to {out}")


if __name__ == "__main__":
    main()
