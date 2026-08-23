#!/usr/bin/env python3
"""Download the real model weights + fixtures into MODELS_DIR (§4, §39, §93).

All sources are permissively licensed and fetched from reachable hosts (GitHub).
Nothing large is committed to git — this script reconstructs it. Idempotent:
existing files are left in place unless --force is given.

Artifacts:
  models/lipnet_overlap.pt            LipNet GRID weights (overlap split, WER 4.6%)  — Fengdalu/LipNet-PyTorch (MIT)
  models/lipnet_unseen.pt             LipNet GRID weights (unseen split,  WER 13.3%) — Fengdalu/LipNet-PyTorch (MIT)
  models/shape_predictor_68_face_landmarks.dat   dlib 68-landmark predictor (research-only license)
  models/yolov8n.pt                   YOLOv8n person detector — Ultralytics (AGPL-3.0)
  tests/fixtures/visual_speech/grid/  10 labeled GRID clips — rizkiarm/LipNet (MIT)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = Path(os.environ.get("MODELS_DIR", REPO_ROOT / "models"))
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "visual_speech" / "grid"

YOLO_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt"
SYNCVSR_URL = ("https://github.com/KAIST-AILab/SyncVSR/releases/download/"
               "weight-audio-v1/Vox%2BLRS2%2BLRS3.ckpt")
SYNCVSR_MIN_BYTES = 1_000_000_000  # ~1.14 GB expected


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _clone(repo: str, dst: Path) -> None:
    _run(["git", "clone", "--depth", "1", f"https://github.com/{repo}", str(dst)])


def _copy(src: Path, dst: Path, force: bool) -> None:
    if dst.exists() and not force:
        print(f"  ✓ {dst.name} already present")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"  ↓ {dst.name} ({dst.stat().st_size // 1024} KB)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Download SilentSpeak Lab model weights")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    ap.add_argument("--skip-fixtures", action="store_true", help="don't fetch GRID test clips")
    ap.add_argument("--skip-openvocab", action="store_true", help="don't fetch the 1.14GB SyncVSR checkpoint")
    args = ap.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Models dir: {MODELS_DIR}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        print("LipNet weights (Fengdalu/LipNet-PyTorch, MIT):")
        lipnet = tmp / "lipnet"
        _clone("Fengdalu/LipNet-PyTorch", lipnet)
        pts = sorted((lipnet / "pretrain").glob("*.pt"))
        overlap = next((p for p in pts if "overlap" in p.name), None)
        unseen = next((p for p in pts if "unseen" in p.name), None)
        if overlap:
            _copy(overlap, MODELS_DIR / "lipnet_overlap.pt", args.force)
        if unseen:
            _copy(unseen, MODELS_DIR / "lipnet_unseen.pt", args.force)

        print("dlib 68-landmark predictor (research-only license):")
        dlibrepo = tmp / "dlibmodels"
        _clone("italojs/facial-landmarks-recognition", dlibrepo)
        dat = next(dlibrepo.rglob("shape_predictor_68_face_landmarks.dat"), None)
        if dat:
            _copy(dat, MODELS_DIR / "shape_predictor_68_face_landmarks.dat", args.force)

        print("YOLOv8n person detector (Ultralytics, AGPL-3.0):")
        yolo_dst = MODELS_DIR / "yolov8n.pt"
        if yolo_dst.exists() and not args.force:
            print("  ✓ yolov8n.pt already present")
        else:
            _run(["curl", "-sSL", "-o", str(yolo_dst), YOLO_URL])
            print(f"  ↓ yolov8n.pt ({yolo_dst.stat().st_size // 1024} KB)")

        if not args.skip_openvocab:
            print("SyncVSR open-vocabulary VSR checkpoint (~1.14 GB, MIT):")
            ov_dst = MODELS_DIR / "syncvsr_vox_lrs2_lrs3.ckpt"
            if ov_dst.exists() and ov_dst.stat().st_size >= SYNCVSR_MIN_BYTES and not args.force:
                print("  ✓ syncvsr_vox_lrs2_lrs3.ckpt already present")
            else:
                print(f"  ↓ downloading from {SYNCVSR_URL} …")
                _run(["curl", "-sSL", "-o", str(ov_dst), SYNCVSR_URL])
                size = ov_dst.stat().st_size if ov_dst.exists() else 0
                if size < SYNCVSR_MIN_BYTES:
                    print(f"  ⚠ downloaded only {size} bytes — the host may be blocked. "
                          "Open-vocab VSR will report MODEL_UNAVAILABLE until provided.")
                else:
                    print(f"  ✓ syncvsr_vox_lrs2_lrs3.ckpt ({size // (1024*1024)} MB)")

        if not args.skip_fixtures:
            print("GRID test clips (rizkiarm/LipNet, MIT):")
            grid = tmp / "grid"
            _clone("rizkiarm/LipNet", grid)
            src_dir = grid / "evaluation" / "samples" / "GRID"
            FIXTURES.mkdir(parents=True, exist_ok=True)
            for mpg in sorted(src_dir.glob("*.mpg")):
                _copy(mpg, FIXTURES / mpg.name, args.force)

    print("\nDone. Verify with: python -m scripts.verify_models (or run the tests).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
