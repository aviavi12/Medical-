#!/usr/bin/env python3
"""Benchmark the open-vocabulary VSR pipeline (Phase 19).

    python scripts/benchmark_open_vocabulary.py --video clip.mp4 [--device auto] [--report out.json]

Measures per-stage latency (face detect + crop, VSR inference), throughput,
device, and peak RAM. Works on CPU/CUDA/MPS (device auto-detected).
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Open-vocabulary VSR benchmark")
    ap.add_argument("--video", required=True)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--crop-mode", default="lower_face")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    os.environ["DEVICE"] = args.device
    os.environ["LIP_READING_MODEL"] = "syncvsr"
    os.environ["OPENVOCAB_CROP_MODE"] = args.crop_mode
    os.environ["ALLOW_MOCK_INFERENCE"] = "0"

    import cv2

    from ml.common.config import get_ml_config
    from ml.common.device import device_report
    from ml.lipreading import get_lip_reading_model

    config = get_ml_config()
    model = get_lip_reading_model(config)
    av = model.availability()
    dev = device_report(config.device)
    report = {"video": args.video, "device": dev, "availability": av.state.value}
    if not av.is_available:
        report["detail"] = av.detail
        print(json.dumps(report, indent=2))
        return 1

    t_load0 = time.time()
    model.load()
    report["model_load_seconds"] = round(time.time() - t_load0, 2)

    cap = cv2.VideoCapture(args.video)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append((len(frames) / 25.0, f, None))
    cap.release()
    report["frames"] = len(frames)

    # Stage: preprocessing (face detect + crop)
    t0 = time.time()
    crops, ts = model.preprocessor.build_crops(frames)
    report["preprocess_seconds"] = round(time.time() - t0, 2)
    report["usable_frames"] = len(crops)

    # Stage: VSR inference + decode
    t0 = time.time()
    result = model.transcribe_crops(crops, ts)
    report["vsr_inference_seconds"] = round(time.time() - t0, 2)

    total = report["preprocess_seconds"] + report["vsr_inference_seconds"]
    report["total_seconds"] = round(total, 2)
    report["fps"] = round(len(frames) / total, 1) if total > 0 else 0
    report["peak_ram_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    report["transcript"] = result.segments[0].text if result.segments else ""

    print(json.dumps(report, indent=2))
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
